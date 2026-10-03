import { describe, expect, it } from "vitest";
import { ipInAny, ipInCidr, parseCidr, parseIp } from "../src/netaddr";

describe("parseCidr", () => {
  it("parses IPv4 and IPv6 ranges and bare addresses", () => {
    expect(parseCidr("10.0.0.0/8")).toMatchObject({ version: 4, prefix: 8 });
    expect(parseCidr("200.10.1.2")).toMatchObject({ version: 4, prefix: 32 });
    expect(parseCidr("2001:db8::/32")).toMatchObject({ version: 6, prefix: 32 });
    expect(parseCidr("::1")).toMatchObject({ version: 6, prefix: 128 });
    expect(parseCidr("::ffff:192.0.2.1/128")).toMatchObject({ version: 6, prefix: 128 });
  });
  it("rejects invalid input", () => {
    for (const s of ["", "10.0.0.0/33", "256.1.1.1", "1.2.3", "01.2.3.4", "10.0.0.0/", "2001:db8::/129", "1::2::3", "g::1", "1:2:3:4:5:6:7:8:9", "abc"]) {
      expect(parseCidr(s), s).toBeNull();
    }
  });
});

describe("parseIp", () => {
  it("expands IPv6", () => {
    expect([...parseIp("2001:db8::1")!]).toEqual([0x20, 0x01, 0x0d, 0xb8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]);
    expect([...parseIp("1:2:3:4:5:6:7:8")!].length).toBe(16);
  });
});

describe("ipInCidr", () => {
  it("matches IPv4", () => {
    expect(ipInCidr("200.10.5.6", "200.10.0.0/16")).toBe(true);
    expect(ipInCidr("200.11.5.6", "200.10.0.0/16")).toBe(false);
    expect(ipInCidr("192.168.1.130", "192.168.1.128/25")).toBe(true);
    expect(ipInCidr("192.168.1.127", "192.168.1.128/25")).toBe(false);
    expect(ipInCidr("1.2.3.4", "0.0.0.0/0")).toBe(true);
    expect(ipInCidr("1.2.3.4", "1.2.3.4")).toBe(true);
  });
  it("matches IPv6 and keeps families apart", () => {
    expect(ipInCidr("2001:db8:abcd::5", "2001:db8::/32")).toBe(true);
    expect(ipInCidr("2001:db9::5", "2001:db8::/32")).toBe(false);
    expect(ipInCidr("2001:db8::1", "10.0.0.0/8")).toBe(false);
    expect(ipInCidr("10.1.1.1", "::/0")).toBe(false);
  });
  it("treats IPv4-mapped IPv6 as IPv4", () => {
    expect(ipInCidr("::ffff:10.1.2.3", "10.0.0.0/8")).toBe(true);
  });
  it("ipInAny", () => {
    expect(ipInAny("10.0.0.1", ["192.168.0.0/16", "10.0.0.0/24"])).toBe(true);
    expect(ipInAny("unknown", ["10.0.0.0/8"])).toBe(false);
    expect(ipInAny("10.0.0.1", [])).toBe(false);
  });
});
