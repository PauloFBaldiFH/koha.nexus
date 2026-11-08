// Name policy for library addresses.
//
// Flat names only, because the free edge certificate covers one level:
//   OPAC        <prefix><slug>.<zone>                     (Koha)
//   staff       <prefix><slug><staffSuffix>.<zone>        (Koha)
//   collection  <prefix><slug><collectionSuffix>.<zone>   (Tainacan)
// Technical names are always reserved. The phishing-word blocklist (with
// look-alike spellings) only applies to manual approval: automatic approval
// passes allowBlocked = true.

export interface NameOptions {
  prefix: string;
  staffSuffix: string;
  /** Tainacan's address (TAINACAN_SUFFIX); "" = no such address. */
  collectionSuffix?: string;
  repositorySuffix?: string;
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

/** What a library publishes through its address. */
export interface Services {
  koha: boolean;
  tainacan: boolean;
  dspace?: boolean;
}

export const SERVICE_NAMES = ["koha", "tainacan", "dspace"] as const;

/** "koha", "tainacan", "koha,tainacan" (the column); anything else counts as Koha only. */
export function parseServices(text: string | null | undefined): Services {
  const parts = new Set((text ?? "koha").split(",").map((x) => x.trim()));
  const s = { koha: parts.has("koha"), tainacan: parts.has("tainacan") };
  if (parts.has("dspace")) return { ...s, dspace:true };
  return s.koha || s.tainacan ? s : { koha: true, tainacan: false };
}

export function servicesText(s: Services): string {
  return SERVICE_NAMES.filter((n) => s[n]).join(",");
}

export interface CollectionEnv extends HostEnv {
  DSPACE_SUFFIX?: string;
  TAINACAN_SUFFIX?: string;
}

export const DEFAULT_COLLECTION_SUFFIX = "-acervo";

export function collectionSuffix(env: { TAINACAN_SUFFIX?: string }): string {
  return env.TAINACAN_SUFFIX ?? DEFAULT_COLLECTION_SUFFIX;
}

/** Tainacan's address: <prefix><slug><suffix>.<zone>. */
export function collectionHostname(slug: string, env: CollectionEnv): string {
  return `${env.NAME_PREFIX}${slug}${collectionSuffix(env)}.${env.ZONE_NAME}`;
}

/** Every name of a library, published or not (the steps keep or drop each by service). */
export function libraryHosts(slug: string, env: CollectionEnv): Hostnames & { collection: string; repository: string } {
  return { ...hostnamesFor(slug, env), collection: collectionHostname(slug, env), repository: repositoryHostname(slug,env) };
}

/** The names a library publishes, by service (the API answers and the DNS records). */
export function publishedHostnames(slug: string, env: CollectionEnv, s: Services): Partial<Hostnames> & { collection?: string; repository?:string } {
  return { ...(s.koha ? hostnamesFor(slug, env) : {}), ...(s.tainacan ? { collection: collectionHostname(slug, env) } : {}), ...(s.dspace ? {repository:repositoryHostname(slug,env)} : {}) };
}

/** True when the collection label of `slug` still fits one DNS label. */
export function collectionFits(slug: string, env: CollectionEnv): boolean {
  return `${env.NAME_PREFIX}${slug}${collectionSuffix(env)}`.length <= DNS_LABEL_MAX;
}

const DNS_LABEL_MAX = 63;
export const MIN_SLUG_LENGTH = 3;

/** Longest slug whose longest label (prefix + slug + a suffix) still fits one DNS label. */
export function maxSlugLength(prefix: string, staffSuffix: string, collectionSuffix = "", repositorySuffix = ""): number {
  return DNS_LABEL_MAX - prefix.length - Math.max(staffSuffix.length, collectionSuffix.length, repositorySuffix.length);
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
  const max = maxSlugLength(opts.prefix, opts.staffSuffix, opts.collectionSuffix ?? "", opts.repositorySuffix ?? "");
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
  // "<x>-acervo" would be the collection hostname of library "<x>".
  if (opts.collectionSuffix && slug.endsWith(opts.collectionSuffix)) {
    return { ok: false, reason: `names ending in "${opts.collectionSuffix}" are reserved for collection addresses` };
  }
  if (opts.repositorySuffix && slug.endsWith(opts.repositorySuffix)) return {ok:false,reason:"names ending in the repository suffix are reserved"};
  if (RESERVED.has(slug)) return { ok: false, reason: "reserved name" };
  if (!opts.allowBlocked) {
    for (const v of foldLookalikes(slug)) {
      const word = BLOCKED_WORDS.find((w) => v.includes(w));
      if (word) return { ok: false, reason: `contains a blocked word (${word})` };
    }
  }
  return { ok: true };
}


export const REPOSITORY_SUFFIX = "-repositorio";
export const DSPACE_ORIGIN_PORT = 18102;
export function repositoryHostname(slug:string,env:CollectionEnv):string {
  return `${env.NAME_PREFIX}${slug}${env.DSPACE_SUFFIX ?? REPOSITORY_SUFFIX}.${env.ZONE_NAME}`;
}
export function repositoryFits(slug:string,env:CollectionEnv):boolean {
  return `${env.NAME_PREFIX}${slug}${env.DSPACE_SUFFIX ?? REPOSITORY_SUFFIX}`.length <= DNS_LABEL_MAX;
}
