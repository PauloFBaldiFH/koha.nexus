// Name policy for library addresses.
//
// Flat names only, because the free edge certificate covers one level:
//   OPAC   <prefix><slug>.<zone>
//   staff  <prefix><slug><staffSuffix>.<zone>
// Technical names are always reserved. The phishing-word blocklist (with
// look-alike spellings) only applies to manual approval: automatic approval
// passes allowBlocked = true.

export interface NameOptions {
  prefix: string;
  staffSuffix: string;
  allowBlocked?: boolean;
}

export interface Hostnames {
  opac: string;
  staff: string;
}

export interface HostEnv {
  NAME_PREFIX: string;
  STAFF_SUFFIX: string;
  ZONE_NAME: string;
}

export function hostnamesFor(slug: string, env: HostEnv): Hostnames {
  const label = `${env.NAME_PREFIX}${slug}`;
  return { opac: `${label}.${env.ZONE_NAME}`, staff: `${label}${env.STAFF_SUFFIX}.${env.ZONE_NAME}` };
}

const DNS_LABEL_MAX = 63;
export const MIN_SLUG_LENGTH = 3;

/** Longest slug whose staff label (prefix + slug + suffix) still fits one DNS label. */
export function maxSlugLength(prefix: string, staffSuffix: string): number {
  return DNS_LABEL_MAX - prefix.length - staffSuffix.length;
}

/** "Biblioteca Pública de Palotina" -> "biblioteca-publica-de-palotina". */
export function slugify(s: string): string {
  return s
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function fit(slug: string, max: number): string {
  return slug.slice(0, max).replace(/-+$/, "");
}

/**
 * Names tried, in order, by automatic approval: the requested name (else
 * the institution name), then numbered variants of it (`palotina-pr-2` ..
 * `-9`), then the institution name and its variants when a name was
 * requested. Duplicates and empty names are dropped; validity is checked
 * by the caller.
 */
export function slugCandidates(requested: string, institution: string, max: number): string[] {
  const bases = [slugify(requested), slugify(institution)].filter(Boolean);
  const out: string[] = [];
  const add = (s: string) => {
    if (s && !out.includes(s)) out.push(s);
  };
  for (const base of bases) {
    add(fit(base, max));
    for (let n = 2; n <= 9; n++) add(`${fit(base, max - String(n).length - 1)}-${n}`);
  }
  return out;
}

// Never handed out: infrastructure, mail, well-known service names.
export const RESERVED = new Set([
  "abuse", "account", "accounts", "admin", "administrator", "api", "app", "apps", "assets", "auth",
  "autoconfig", "autodiscover", "billing", "blog", "broker", "cdn", "cloudflare", "cpanel", "dashboard",
  "dev", "dns", "docs", "email", "ftp", "help", "hostmaster", "imap", "info", "join", "kei", "koha",
  "koha-broker", "localhost", "login", "mail", "mx", "ns", "ns1", "ns2", "ns3", "ns4", "pop", "pop3",
  "portal", "postmaster", "root", "security", "smtp", "sso", "stage", "staging", "static", "status",
  "support", "test", "tunnel", "vpn", "webmail", "webmaster", "whois", "www",
]);

// Words used in phishing hostnames. Matched after look-alike folding, as
// substrings, so "l0g1n" and "secure-login-x" are caught too.
export const BLOCKED_WORDS = [
  "login", "logon", "signin", "signup", "verify", "verific", "password", "senha", "account", "conta",
  "secure", "seguro", "update", "atualiza", "wallet", "bank", "banco", "paypal", "bradesco",
  "santander", "nubank", "caixaeconomica", "bancodobrasil", "pix", "boleto", "receita", "inss", "detran",
  "correios", "apple", "icloud", "google", "gmail", "microsoft", "office365", "outlook", "facebook",
  "instagram", "whatsapp", "netflix", "amazon", "mercadopago", "mercadolivre",
];

const LOOKALIKE: Record<string, string[]> = {
  "0": ["o"],
  "1": ["i", "l"],
  "3": ["e"],
  "4": ["a"],
  "5": ["s"],
  "7": ["t"],
  "8": ["b"],
  "9": ["g"],
};

/** Spellings of a slug with digits read as letters ("l0g1n" -> "login", "logln"). */
export function foldLookalikes(slug: string): string[] {
  const base = slug.replace(/-/g, "");
  const variants = new Set<string>([base]);
  for (const [digit, letters] of Object.entries(LOOKALIKE)) {
    for (const v of [...variants]) {
      if (!v.includes(digit)) continue;
      for (const l of letters) variants.add(v.split(digit).join(l));
    }
  }
  // "rn" looks like "m", "vv" like "w".
  for (const v of [...variants]) {
    variants.add(v.replace(/rn/g, "m").replace(/vv/g, "w"));
  }
  return [...variants];
}

export type SlugCheck = { ok: true } | { ok: false; reason: string };

export function validateSlug(slug: string, opts: NameOptions): SlugCheck {
  const max = maxSlugLength(opts.prefix, opts.staffSuffix);
  if (slug.length < MIN_SLUG_LENGTH) return { ok: false, reason: `use at least ${MIN_SLUG_LENGTH} characters` };
  if (slug.length > max) return { ok: false, reason: `use at most ${max} characters` };
  if (!/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(slug)) {
    return { ok: false, reason: "use lowercase letters, digits and hyphens, starting and ending with a letter or digit" };
  }
  if (slug.includes("--")) return { ok: false, reason: "two hyphens in a row are not allowed" };
  if (/^\d+$/.test(slug)) return { ok: false, reason: "a name made only of digits is not allowed" };
  // "<x>-admin" would be the staff hostname of library "<x>".
  if (opts.staffSuffix && slug.endsWith(opts.staffSuffix)) {
    return { ok: false, reason: `names ending in "${opts.staffSuffix}" are reserved for staff addresses` };
  }
  if (RESERVED.has(slug)) return { ok: false, reason: "reserved name" };
  if (!opts.allowBlocked) {
    for (const v of foldLookalikes(slug)) {
      const word = BLOCKED_WORDS.find((w) => v.includes(w));
      if (word) return { ok: false, reason: `contains a blocked word (${word})` };
    }
  }
  return { ok: true };
}
