"""HTTP Access Log Parser for SENTRIX Telemetry Ingress.

Supports:
- Nginx / Apache Combined Log Format (with optional response time in seconds)
- Apache Common Log Format (CLF)
- JSON structured access logs (Caddy, Traefik, Nginx JSON, Docker logs)
- IP anonymization for privacy compliance (IPv4 /24, IPv6 /48)
"""

from __future__ import annotations

import datetime
import ipaddress
import json
import re
from typing import Any

from app.ingestion.telemetry_schemas import RequestTelemetryItem

# Combined log format with optional request_time at the end:
# 192.0.2.1 - user [28/Oct/2026:20:00:00 +0000] "GET /api/v1/health HTTP/1.1" 200 45 "https://ref.com" "Mozilla/5.0" 0.015
COMBINED_LOG_REGEX = re.compile(
    r"^(?P<ip>\S+)\s+"  # client IP
    r"(?P<ident>\S+)\s+"  # ident / remote logname
    r"(?P<user>\S+)\s+"  # auth user
    r"\[(?P<time>[^\]]+)\]\s+"  # timestamp [10/Oct/2000:13:55:36 -0700]
    r'"(?P<method>[A-Z]+)\s+(?P<uri>\S+)(?:\s+HTTP\/[0-9.]+)?(?:.*)?"\s+'  # Request line
    r"(?P<status>\d{3})\s+"  # HTTP status code
    r"(?P<bytes>\d+|-)"  # Bytes sent (or -)
    r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<agent>[^"]*)")?'  # Optional referer & user-agent
    r"(?:\s+(?P<duration>[0-9.]+))?"  # Optional request duration in seconds (Nginx $request_time)
)

# Common Log Format (CLF):
# 127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326
CLF_LOG_REGEX = re.compile(
    r"^(?P<ip>\S+)\s+"
    r"(?P<ident>\S+)\s+"
    r"(?P<user>\S+)\s+"
    r"\[(?P<time>[^\]]+)\]\s+"
    r'"(?P<method>[A-Z]+)\s+(?P<uri>\S+)(?:\s+HTTP\/[0-9.]+)?(?:.*)?"\s+'
    r"(?P<status>\d{3})\s+"
    r"(?P<bytes>\d+|-)"
)


def anonymize_ip(ip_str: str) -> str:
    """Anonymize IPv4 to /24 (e.g. 198.51.100.0) and IPv6 to /48 to preserve subnet locality

    while protecting client identity under privacy regulations.
    """
    clean_ip = ip_str.strip()
    if not clean_ip:
        return "0.0.0.0"

    try:
        addr = ipaddress.ip_address(clean_ip)
        if addr.version == 4:
            net = ipaddress.ip_network(f"{clean_ip}/24", strict=False)
            return str(net.network_address)
        elif addr.version == 6:
            net = ipaddress.ip_network(f"{clean_ip}/48", strict=False)
            return str(net.network_address)
    except ValueError:
        # If client string is already anonymized, a hostname, or subnet string
        pass

    return clean_ip


def _parse_apache_timestamp(time_str: str) -> str:
    """Parse Apache/Nginx format `10/Oct/2000:13:55:36 -0700` into ISO 8601 UTC string."""
    try:
        dt = datetime.datetime.strptime(time_str, "%d/%b/%Y:%H:%M:%S %z")
        return dt.astimezone(datetime.timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _parse_json_log(line: str) -> RequestTelemetryItem | None:
    """Parse a single line of JSON-formatted access log."""
    try:
        data: dict[str, Any] = json.loads(line)
        if not isinstance(data, dict):
            return None

        # Client IP extraction
        ip = str(
            data.get("client_ip")
            or data.get("remote_addr")
            or data.get("client")
            or data.get("ip")
            or data.get("host")
            or "127.0.0.1"
        )

        # HTTP method
        method = str(data.get("method") or data.get("request_method") or "GET").upper()

        # Request URI / path
        uri = str(
            data.get("uri")
            or data.get("path")
            or data.get("request_uri")
            or data.get("url")
            or "/"
        )

        # Status code
        raw_status = data.get("status") or data.get("status_code") or 200
        try:
            status_code = int(raw_status)
        except (ValueError, TypeError):
            status_code = 200

        # Latency extraction (handles ms, seconds, or duration strings)
        latency_ms = 0.0
        if "latency_ms" in data:
            latency_ms = float(data["latency_ms"])
        elif "duration_ms" in data:
            latency_ms = float(data["duration_ms"])
        elif "request_time" in data:
            # Nginx request_time is in seconds with millisecond resolution
            latency_ms = float(data["request_time"]) * 1000.0
        elif "duration" in data:
            val = float(data["duration"])
            # If duration is in seconds (< 60.0 with decimal), convert to ms
            latency_ms = val * 1000.0 if val < 60.0 else val

        # Bytes sent
        raw_bytes = (
            data.get("bytes_sent")
            or data.get("body_bytes_sent")
            or data.get("bytes")
            or data.get("size")
            or 0
        )
        try:
            bytes_sent = int(raw_bytes)
        except (ValueError, TypeError):
            bytes_sent = 0

        # User agent
        user_agent = (
            str(data.get("user_agent") or data.get("http_user_agent") or "") or None
        )

        # Timestamp
        raw_time = data.get("timestamp") or data.get("time") or data.get("time_iso8601")
        if raw_time and isinstance(raw_time, str):
            timestamp = raw_time
        else:
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Request ID
        request_id = data.get("request_id") or data.get("x_request_id")
        if request_id is not None:
            request_id = str(request_id)

        return RequestTelemetryItem(
            timestamp=timestamp,
            client_ip=ip,
            method=method,
            uri=uri,
            status_code=status_code,
            latency_ms=max(0.0, latency_ms),
            bytes_sent=max(0, bytes_sent),
            user_agent=user_agent,
            request_id=request_id,
        )
    except (json.JSONDecodeError, ValueError, KeyError, TypeError):
        return None


def parse_access_log_line(line: str) -> RequestTelemetryItem | None:
    """Parse a single line of web server access log into a standardized RequestTelemetryItem.

    Supports JSON, Nginx/Apache Combined, and Common Log Format (CLF).
    """
    cleaned = line.strip()
    if not cleaned or cleaned.startswith("#"):
        return None

    # Try JSON format if line starts and ends with braces
    if cleaned.startswith("{") and cleaned.endswith("}"):
        item = _parse_json_log(cleaned)
        if item is not None:
            return item

    # Try Combined Log Format
    match = COMBINED_LOG_REGEX.match(cleaned)
    if match:
        d = match.groupdict()
        status_code = int(d["status"])
        bytes_sent = int(d["bytes"]) if d["bytes"] != "-" else 0
        duration_s = float(d["duration"]) if d.get("duration") else 0.0
        latency_ms = duration_s * 1000.0
        ts = _parse_apache_timestamp(d["time"])

        return RequestTelemetryItem(
            timestamp=ts,
            client_ip=d["ip"],
            method=d["method"].upper(),
            uri=d["uri"],
            status_code=status_code,
            latency_ms=max(0.0, latency_ms),
            bytes_sent=max(0, bytes_sent),
            user_agent=d.get("agent"),
        )

    # Try CLF (Common Log Format)
    match_clf = CLF_LOG_REGEX.match(cleaned)
    if match_clf:
        d = match_clf.groupdict()
        status_code = int(d["status"])
        bytes_sent = int(d["bytes"]) if d["bytes"] != "-" else 0
        ts = _parse_apache_timestamp(d["time"])

        return RequestTelemetryItem(
            timestamp=ts,
            client_ip=d["ip"],
            method=d["method"].upper(),
            uri=d["uri"],
            status_code=status_code,
            latency_ms=0.0,
            bytes_sent=max(0, bytes_sent),
            user_agent=None,
        )

    return None


def parse_access_logs(lines: list[str]) -> tuple[list[RequestTelemetryItem], int]:
    """Batch-parses multiple access log lines.

    Returns:
        tuple[list[RequestTelemetryItem], int]: (parsed_items, dropped_or_unparseable_count)
    """
    parsed: list[RequestTelemetryItem] = []
    dropped: int = 0

    for line in lines:
        item = parse_access_log_line(line)
        if item is not None:
            parsed.append(item)
        else:
            dropped += 1

    return parsed, dropped
