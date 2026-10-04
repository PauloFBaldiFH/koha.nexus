import { describe, expect, it } from "vitest";
import { normalizeRecoveryCode, recoveryCode, recoveryHash, slugFromAddress } from "../src/recovery";

const prod = { NAME_PREFIX: "", STAFF_SUFFIX: "-admin", ZONE_NAME: "koha.nexus" };
const test = { NAME_PREFIX: "t-", STAFF_SUFFIX: "-admin", ZONE_NAME: "example.org" };

describe("recoveryCode", () => {
  it("has four groups of four unambiguous symbols and does not repeat", () => {
    const seen = new Set<string>();
    for (let i = 0; i < 200; i++) {
      const c = recoveryCode();
      expect(c).toMatch(/^[B-DF-HJ-NP-TV-XZ2-9]{4}(-[B-DF-HJ-NP-TV-XZ2-9]{4}){3}$/);
      seen.add(c);
    }
    expect(seen.size).toBe(200);
  });
});

describe("normalizeRecoveryCode", () => {
  it("accepts lower case, spaces and missing hyphens", () => {
    const c = recoveryCode();
    const n = c.replace(/-/g, "");
    expect(normalizeRecoveryCode(c)).toBe(n);
    expect(normalizeRecoveryCode(` ${c.toLowerCase().replace(/-/g, " ")} `)).toBe(n);
  });
  it("rejects wrong length and lookalike symbols", () => {
    expect(normalizeRecoveryCode("BCDF-GHJK")).toBeNull();
    expect(normalizeRecoveryCode("BCDF-GHJK-LMNP-QRS0")).toBeNull();
    expect(normalizeRecoveryCode("BCDF-GHJK-LMNP-QRSA")).toBeNull();
  });
  it("hashes the normalized form, so formatting does not matter", async () => {
    expect(await recoveryHash(normalizeRecoveryCode("bcdf ghjk lmnp qrst")!)).toBe(
      await recoveryHash(normalizeRecoveryCode("BCDF-GHJK-LMNP-QRST")!),
    );
  });
});

describe("slugFromAddress", () => {
  it("takes the slug, either hostname or a URL", () => {
    expect(slugFromAddress("palotina-pr", prod)).toBe("palotina-pr");
    expect(slugFromAddress("Palotina-PR.koha.nexus", prod)).toBe("palotina-pr");
    expect(slugFromAddress("https://palotina-pr-admin.koha.nexus/cgi-bin/koha/mainpage.pl", prod)).toBe("palotina-pr");
    expect(slugFromAddress("t-palotina-pr-admin.example.org", test)).toBe("palotina-pr");
  });
  it("refuses other domains and junk", () => {
    expect(slugFromAddress("palotina.example.com", prod)).toBe("");
    expect(slugFromAddress("a b", prod)).toBe("");
    expect(slugFromAddress("", prod)).toBe("");
  });
});
