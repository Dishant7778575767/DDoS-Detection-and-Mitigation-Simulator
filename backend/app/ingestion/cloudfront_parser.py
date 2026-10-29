"""CloudFront Real-Time Access Log Parser & Normalizer for SENTRIX.

Parses tab-delimited records delivered by Amazon CloudFront to Amazon Kinesis Data Streams.
CloudFront real-time logs emit tab-separated values in the exact field order configured
in the CloudFront real-time log configuration.

Reference:
https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/real-time-logs.html
"""

from __future__ import annotations

import datetime as dt
import logging

from app.ingestion.log_parser import anonymize_ip
from app.ingestion.telemetry_schemas import RequestTelemetryItem

logger = logging.getLogger("sentrix.ingestion.cloudfront")

# Standard recommended field order for CloudFront real-time log configurations
DEFAULT_CLOUDFRONT_LOG_FIELDS: list[str] = [
    "timestamp",
    "c-ip",
    "time-to-first-byte",
    "sc-status",
    "sc-bytes",
    "cs-method",
    "cs-protocol",
    "cs-host",
    "cs-uri-stem",
    "cs-uri-query",
    "c-port",
    "x-edge-location",
    "x-edge-request-id",
    "x-host-header",
    "time-taken",
    "cs-protocol-version",
    "c-ip-version",
    "cs-user-agent",
    "cs-referer",
    "cs-cookie",
    "cs-headers",
    "asn",
]


def parse_cloudfront_timestamp(raw_value: str | float) -> str:
    """Parse CloudFront real-time log timestamp (epoch float seconds with ms precision).

    CloudFront real-time logs emit Unix epoch in seconds (e.g. 1730200000.123).
    Converts to ISO 8601 UTC string format (e.g. '2026-10-29T12:00:00.123000+00:00').
    """
    if isinstance(raw_value, (int, float)):
        epoch = float(raw_value)
    elif isinstance(raw_value, str):
        cleaned = raw_value.strip()
        try:
            epoch = float(cleaned)
        except ValueError:
            # Handle possible ISO 8601 fallback string
            parsed = dt.datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc).isoformat()
    else:
        raise TypeError(f"Invalid timestamp type: {type(raw_value)}")

    # Guard against unit anomalies (nanoseconds or milliseconds)
    if abs(epoch) >= 1e17:
        epoch /= 1_000_000_000
    elif abs(epoch) >= 1e14:
        epoch /= 1_000_000
    elif abs(epoch) >= 1e11:
        epoch /= 1_000

    parsed_dt = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc)
    return parsed_dt.isoformat()


class CloudFrontRealTimeLogParser:
    """Parser and normalizer for CloudFront real-time logs streamed via Kinesis."""

    def __init__(
        self,
        configured_fields: list[str] | None = None,
        field_names: list[str] | None = None,
        anonymize_ips: bool = False,
    ) -> None:
        self.fields = (
            configured_fields or field_names or list(DEFAULT_CLOUDFRONT_LOG_FIELDS)
        )
        self.anonymize_ips = anonymize_ips
        # Build index mapping for O(1) field lookup
        self._field_indices: dict[str, int] = {
            field.lower().strip(): idx for idx, field in enumerate(self.fields)
        }

    def parse_line(self, line: str) -> tuple[str, RequestTelemetryItem] | None:
        """Parse a single tab-separated CloudFront real-time log line.

        Returns (request_id, RequestTelemetryItem) or None if malformed.
        """
        raw_line = line.strip("\r\n")
        if not raw_line or raw_line.startswith("#"):
            return None

        columns = raw_line.split("\t")
        if len(columns) < len(self.fields) and len(columns) < 7:
            return None

        def get_val(field_name: str, default: str = "") -> str:
            idx = self._field_indices.get(field_name.lower())
            if idx is not None and idx < len(columns):
                val = columns[idx].strip()
                return "" if val == "-" else val
            return default

        # 1. Request ID (x-edge-request-id)
        request_id = get_val("x-edge-request-id")
        if not request_id:
            # Fallback if x-edge-request-id is omitted from custom configuration
            request_id = f"cf_{get_val('timestamp', '0')}_{get_val('c-ip', 'unknown')}_{get_val('c-port', '0')}"

        # 2. Timestamp
        raw_ts = get_val("timestamp")
        if not raw_ts:
            return None
        try:
            iso_timestamp = parse_cloudfront_timestamp(raw_ts)
        except (ValueError, OSError):
            return None

        # 3. Client Viewer IP
        client_ip = get_val("c-ip")
        if not client_ip:
            return None
        if self.anonymize_ips:
            client_ip = anonymize_ip(client_ip)

        # 4. HTTP Method & Path
        method = (get_val("cs-method") or "GET").upper()
        # Privacy guard: Do NOT append cs-uri-query to URI path. Query strings
        # frequently leak credentials, session tokens, and personal parameters.
        path = get_val("cs-uri-stem") or "/"

        # 5. Status Code
        raw_status = get_val("sc-status", "200")
        try:
            status_code = int(raw_status)
            if not (100 <= status_code <= 599):
                return None
        except ValueError:
            return None

        # 6. Latency / TTFB
        # CloudFront time-to-first-byte is float seconds (e.g. 0.045 = 45ms)
        raw_ttfb = get_val("time-to-first-byte", "0")
        try:
            ttfb_seconds = float(raw_ttfb)
            latency_ms = max(0.0, round(ttfb_seconds * 1000.0, 2))
        except ValueError:
            latency_ms = 0.0

        # 7. Bytes sent
        raw_bytes = get_val("sc-bytes", "0")
        try:
            bytes_sent = max(0, int(raw_bytes))
        except ValueError:
            bytes_sent = 0

        # 8. User-Agent
        user_agent = get_val("cs-user-agent") or None

        item = RequestTelemetryItem(
            timestamp=iso_timestamp,
            client_ip=client_ip,
            method=method,
            uri=path,
            status_code=status_code,
            latency_ms=latency_ms,
            bytes_sent=bytes_sent,
            user_agent=user_agent,
            request_id=request_id,
        )
        return request_id, item

    def parse_payload(
        self, payload: str | bytes
    ) -> tuple[list[tuple[str, RequestTelemetryItem]], int]:
        """Parse multi-line CloudFront Kinesis record payload.

        Returns (accepted_records, dropped_count).
        """
        if isinstance(payload, bytes):
            try:
                text = payload.decode("utf-8", errors="replace")
            except (UnicodeDecodeError, AttributeError):
                return [], 1
        else:
            text = payload

        accepted: list[tuple[str, RequestTelemetryItem]] = []
        dropped = 0

        for line in text.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            parsed = self.parse_line(line_str)
            if parsed is not None:
                accepted.append(parsed)
            else:
                dropped += 1

        return accepted, dropped

    def parse_batch(self, lines: list[str]) -> tuple[list[RequestTelemetryItem], int]:
        """Convenience method to parse a list of log lines into RequestTelemetryItems and poison count."""
        items: list[RequestTelemetryItem] = []
        poison = 0
        for line in lines:
            res = self.parse_line(line)
            if res is not None:
                items.append(res[1])
            else:
                poison += 1
        return items, poison
