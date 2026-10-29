/**
 * Date, time, and numeric formatting utilities configured for SENTRIX DevSecOps UI.
 */

const IST_DATE_FORMATTER = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Asia/Kolkata",
  hour12: false,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

const IST_TIME_FORMATTER = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  hour12: false,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

/**
 * Format a timestamp into ISO-style YYYY-MM-DD HH:mm:ss in IST (Asia/Kolkata)
 */
export function formatISTDateTime(input?: string | number | Date | null): string {
  if (!input) return "Just now";
  try {
    const d = new Date(input);
    if (isNaN(d.getTime())) return String(input);
    return IST_DATE_FORMATTER.format(d);
  } catch {
    return String(input);
  }
}

/**
 * Format a timestamp into HH:mm:ss in IST (Asia/Kolkata)
 */
export function formatISTTime(input?: string | number | Date | null): string {
  if (!input) return "--:--:--";
  try {
    const d = new Date(input);
    if (isNaN(d.getTime())) return "--:--:--";
    return IST_TIME_FORMATTER.format(d);
  } catch {
    return "--:--:--";
  }
}

/**
 * Format raw packets-per-second with thousand separators
 */
export function formatPPS(pps: number): string {
  return `${Math.round(pps).toLocaleString()} PPS`;
}

/**
 * Format bytes to human readable throughput
 */
export function formatThroughput(bps: number): string {
  if (bps >= 1_000_000_000) {
    return `${(bps / 1_000_000_000).toFixed(1)} Gbps`;
  }
  if (bps >= 1_000_000) {
    return `${(bps / 1_000_000).toFixed(1)} Mbps`;
  }
  if (bps >= 1_000) {
    return `${(bps / 1_000).toFixed(1)} Kbps`;
  }
  return `${Math.round(bps)} bps`;
}

