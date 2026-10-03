// IPv4/IPv6 addresses and CIDR ranges, for the staff gate's allowlist.

export interface Cidr {
  version: 4 | 6;
  bytes: Uint8Array; // 4 or 16 bytes
  prefix: number;
}

export function parseIpv4(s: string): Uint8Array | null {
  const parts = s.split(".");
  if (parts.length !== 4) return null;
  const out = new Uint8Array(4);
  for (let i = 0; i < 4; i++) {
    const p = parts[i]!;
    if (!/^(0|[1-9]\d{0,2})$/.test(p)) return null;
    const n = Number(p);
    if (n > 255) return null;
    out[i] = n;
  }
  return out;
}

export function parseIpv6(s: string): Uint8Array | null {
  if (!/^[0-9A-Fa-f:.]+$/.test(s) || s.length > 45) return null;
  let tail4: Uint8Array | null = null;
  let str = s;
  // Embedded IPv4 in the last 32 bits (::ffff:192.0.2.1).
  const lastColon = str.lastIndexOf(":");
  if (str.includes(".")) {
    tail4 = parseIpv4(str.slice(lastColon + 1));
    if (!tail4) return null;
    str = `${str.slice(0, lastColon + 1)}0:0`;
  }
  const halves = str.split("::");
  if (halves.length > 2) return null;
  const parse = (h: string): number[] | null => {
    if (h === "") return [];
    const groups = h.split(":");
    const out: number[] = [];
    for (const g of groups) {
      if (!/^[0-9A-Fa-f]{1,4}$/.test(g)) return null;
      out.push(parseInt(g, 16));
    }
    return out;
  };
  const head = parse(halves[0]!);
  const rest = halves.length === 2 ? parse(halves[1]!) : [];
  if (!head || !rest) return null;
  let groups: number[];
  if (halves.length === 2) {
    const missing = 8 - head.length - rest.length;
    if (missing < 1) return null;
    groups = [...head, ...new Array<number>(missing).fill(0), ...rest];
  } else {
    groups = head;
  }
  if (groups.length !== 8) return null;
  const out = new Uint8Array(16);
  groups.forEach((g, i) => {
    out[i * 2] = g >> 8;
    out[i * 2 + 1] = g & 0xff;
  });
  if (tail4) out.set(tail4, 12);
  return out;
}

export function parseIp(s: string): Uint8Array | null {
  return s.includes(":") ? parseIpv6(s) : parseIpv4(s);
}

/** "10.0.0.0/8", "2001:db8::/32", or a bare address (one host). */
export function parseCidr(s: string): Cidr | null {
  if (typeof s !== "string") return null;
  const t = s.trim();
  const slash = t.indexOf("/");
  const addr = slash < 0 ? t : t.slice(0, slash);
  const bytes = parseIp(addr);
  if (!bytes) return null;
  const version = bytes.length === 4 ? 4 : 6;
  const bits = bytes.length * 8;
  let prefix = bits;
  if (slash >= 0) {
    const p = t.slice(slash + 1);
    if (!/^\d{1,3}$/.test(p)) return null;
    prefix = Number(p);
    if (prefix > bits) return null;
  }
  return { version, bytes, prefix };
}

function prefixMatch(a: Uint8Array, b: Uint8Array, prefix: number): boolean {
  const full = Math.floor(prefix / 8);
  for (let i = 0; i < full; i++) if (a[i] !== b[i]) return false;
  const rem = prefix % 8;
  if (rem === 0) return true;
  const mask = (0xff << (8 - rem)) & 0xff;
  return ((a[full]! ^ b[full]!) & mask) === 0;
}

// IPv4-mapped IPv6 (::ffff:a.b.c.d) is compared as IPv4.
function unmap(b: Uint8Array): Uint8Array {
  if (b.length === 16 && b.slice(0, 10).every((x) => x === 0) && b[10] === 0xff && b[11] === 0xff) return b.slice(12);
  return b;
}

export function ipInCidr(ip: string, cidr: string | Cidr): boolean {
  const c = typeof cidr === "string" ? parseCidr(cidr) : cidr;
  const raw = parseIp(ip.trim());
  if (!c || !raw) return false;
  const a = unmap(raw);
  if (a.length !== c.bytes.length) return false;
  return prefixMatch(a, c.bytes, c.prefix);
}

export function ipInAny(ip: string, cidrs: readonly string[]): boolean {
  return cidrs.some((c) => ipInCidr(ip, c));
}
