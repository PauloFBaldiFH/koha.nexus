import { describe, expect, it } from "vitest";
import { HttpError, readBodyLimited } from "../src/http";

function streamOf(chunks: number, size: number): ReadableStream<Uint8Array> {
  let sent = 0;
  return new ReadableStream({
    pull(c) {
      if (sent++ < chunks) c.enqueue(new Uint8Array(size).fill(97));
      else c.close();
    },
  });
}

function post(body: BodyInit | null, headers: Record<string, string> = {}): Request {
  return new Request("https://broker.example/v1/x", { method: "POST", body, headers, duplex: "half" } as RequestInit);
}

async function status(p: Promise<unknown>): Promise<number> {
  try {
    await p;
    return 200;
  } catch (e) {
    return e instanceof HttpError ? e.status : -1;
  }
}

describe("readBodyLimited", () => {
  it("returns a body under the limit", async () => {
    const body = await readBodyLimited(post('{"a":1}'), 1024);
    expect(new TextDecoder().decode(body)).toBe('{"a":1}');
  });
  it("returns an empty body for a GET", async () => {
    const body = await readBodyLimited(new Request("https://broker.example/v1/x"), 1024);
    expect(body.byteLength).toBe(0);
  });
  it("refuses a declared length over the limit", async () => {
    expect(await status(readBodyLimited(post("x", { "Content-Length": "999999" }), 1024))).toBe(413);
  });
  it("stops a stream without Content-Length once it passes the limit", async () => {
    const req = post(streamOf(100, 1000));
    expect(req.headers.get("Content-Length")).toBeNull();
    expect(await status(readBodyLimited(req, 4096))).toBe(413);
  });
  it("reads a stream without Content-Length under the limit", async () => {
    const body = await readBodyLimited(post(streamOf(3, 1000)), 4096);
    expect(body.byteLength).toBe(3000);
  });
});
