/**
 * Safe error message normalization across async handlers and API calls.
 */

export function getErrorMessage(err: unknown, fallback = "An unexpected error occurred"): string {
  if (!err) return fallback;

  if (typeof err === "string") {
    return err;
  }

  if (err instanceof Error) {
    return err.message || fallback;
  }

  if (typeof err === "object") {
    if ("message" in err && typeof (err as { message: unknown }).message === "string") {
      return (err as { message: string }).message;
    }
    if ("detail" in err) {
      const detail = (err as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        return detail.map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : JSON.stringify(d))).join(", ");
      }
    }
    if ("code" in err && typeof (err as { code: unknown }).code === "string") {
      return `Error (${(err as { code: string }).code})`;
    }
  }

  try {
    return JSON.stringify(err);
  } catch {
    return fallback;
  }
}

