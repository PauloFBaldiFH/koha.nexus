// HTTP helpers: JSON responses, errors that become JSON responses, and
// input validation for request bodies.

export class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly headers?: Record<string, string>,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

const SECURITY_HEADERS: Record<string, string> = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
};

export function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...SECURITY_HEADERS, ...headers },
  });
}

export function errorResponse(e: HttpError): Response {
  return json({ error: e.message }, e.status, e.headers);
}

const MAX_BODY_BYTES = 16 * 1024;
const dec = new TextDecoder("utf-8", { fatal: true, ignoreBOM: false });

/** Parses a JSON object body. An empty body counts as `{}`. */
export function parseJson<T extends object>(body: ArrayBuffer): T {
  if (body.byteLength === 0) return {} as T;
  if (body.byteLength > MAX_BODY_BYTES) throw new HttpError(413, "request body too large");
  let v: unknown;
  try {
    v = JSON.parse(dec.decode(body));
  } catch {
    throw new HttpError(400, "body must be valid JSON");
  }
  if (typeof v !== "object" || v === null || Array.isArray(v)) throw new HttpError(400, "body must be a JSON object");
  return v as T;
}

export interface StrOptions {
  min?: number;
  max?: number;
  re?: RegExp;
  optional?: boolean;
}

/**
 * Validates a text field: trimmed, length-checked and optionally matched.
 * A missing optional field returns "".
 */
export function str(v: unknown, name: string, opts: StrOptions = {}): string {
  if (v === undefined || v === null || (typeof v === "string" && v.trim() === "")) {
    if (opts.optional) return "";
    throw new HttpError(400, `${name} is required`);
  }
  if (typeof v !== "string") throw new HttpError(400, `${name} must be text`);
  const s = v.trim();
  if (/[\u0000-\u001f\u007f]/.test(s)) throw new HttpError(400, `${name} has invalid characters`);
  if (opts.min !== undefined && s.length < opts.min) throw new HttpError(400, `${name} must have at least ${opts.min} characters`);
  if (opts.max !== undefined && s.length > opts.max) throw new HttpError(400, `${name} must have at most ${opts.max} characters`);
  if (opts.re && !opts.re.test(s)) throw new HttpError(400, `${name} is not valid`);
  return s;
}
