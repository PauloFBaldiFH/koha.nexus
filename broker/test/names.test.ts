import { describe, expect, it } from "vitest";
import { foldLookalikes, hostnamesFor, maxSlugLength, slugCandidates, slugify, validateSlug } from "../src/names";

const prod = { prefix: "", staffSuffix: "-admin" };
const test = { prefix: "t-", staffSuffix: "-admin" };

describe("slugify", () => {
  it("strips accents, lowercases and joins with hyphens", () => {
    expect(slugify("Biblioteca Pública Municipal de Palotina")).toBe("biblioteca-publica-municipal-de-palotina");
    expect(slugify("  Palotina PR ")).toBe("palotina-pr");
    expect(slugify("São João d'Aliança — Ç")).toBe("sao-joao-d-alianca-c");
    expect(slugify("***")).toBe("");
  });
});

describe("hostnamesFor", () => {
  it("builds flat OPAC and staff names", () => {
    expect(hostnamesFor("palotina-pr", { NAME_PREFIX: "", STAFF_SUFFIX: "-admin", ZONE_NAME: "koha.nexus" })).toEqual({
      opac: "palotina-pr.koha.nexus",
      staff: "palotina-pr-admin.koha.nexus",
    });
    expect(hostnamesFor("palotina-pr", { NAME_PREFIX: "t-", STAFF_SUFFIX: "-admin", ZONE_NAME: "example.org" })).toEqual({
      opac: "t-palotina-pr.example.org",
      staff: "t-palotina-pr-admin.example.org",
    });
  });
});

describe("maxSlugLength", () => {
  it("keeps the staff label within 63 characters", () => {
    expect(maxSlugLength("", "-admin")).toBe(57);
    expect(maxSlugLength("t-", "-admin")).toBe(55);
  });
});

describe("slugCandidates", () => {
  it("tries the requested name, its numbered variants, then the institution", () => {
    const c = slugCandidates("Palotina PR", "Biblioteca de Palotina", 57);
    expect(c.slice(0, 3)).toEqual(["palotina-pr", "palotina-pr-2", "palotina-pr-3"]);
    expect(c).toContain("biblioteca-de-palotina");
    expect(c.indexOf("palotina-pr-9")).toBeLessThan(c.indexOf("biblioteca-de-palotina"));
  });
  it("uses the institution name when no name is requested", () => {
    expect(slugCandidates("", "Biblioteca X", 57)[0]).toBe("biblioteca-x");
  });
  it("keeps variants within the maximum length", () => {
    const long = "a".repeat(80);
    for (const c of slugCandidates(long, "", 20)) expect(c.length).toBeLessThanOrEqual(20);
  });
});

describe("validateSlug", () => {
  it("accepts ordinary names", () => {
    expect(validateSlug("palotina-pr", prod)).toEqual({ ok: true });
    expect(validateSlug("bib-123", test)).toEqual({ ok: true });
  });
  it("rejects bad syntax and lengths", () => {
    for (const s of ["ab", "-abc", "abc-", "a_b-c", "Abc", "ab--cd", "xn--abc", "12345", "a".repeat(56)]) {
      expect(validateSlug(s, test).ok, s).toBe(false);
    }
    expect(validateSlug("a".repeat(55), test).ok).toBe(true);
  });
  it("always rejects technical names, even with allowBlocked", () => {
    for (const s of ["www", "join", "broker", "mail", "api", "admin", "koha-broker"]) {
      expect(validateSlug(s, { ...prod, allowBlocked: true }).ok, s).toBe(false);
    }
  });
  it("rejects names that would collide with a staff hostname", () => {
    expect(validateSlug("palotina-admin", { ...prod, allowBlocked: true }).ok).toBe(false);
  });
  it("applies the phishing blocklist with look-alikes only without allowBlocked", () => {
    for (const s of ["secure-login", "l0g1n-portal", "paypa1", "meu-banco", "s3nha", "verificacao"]) {
      expect(validateSlug(s, prod).ok, s).toBe(false);
      expect(validateSlug(s, { ...prod, allowBlocked: true }).ok, s).toBe(true);
    }
  });
  it("folds digits into letters", () => {
    expect(foldLookalikes("l0g1n")).toContain("login");
  });
});
