"""The Tainacan of a test machine through a real browser (Playwright,
Chromium), the way a visitor and an administrator use it.

    python3 tests/e2e/tainacan_browser.py STEP URL OUTDIR

STEP:
  look    without a login: the home page, the collections address and the
          login page; then the administrator logs in and opens the
          Tainacan admin page. Screenshots only, nothing is changed.
  seed    the administrator (logged in through the login page) creates a
          public collection, an item with metadata and an image, both
          published, and a private collection with an item, through the
          plugin's REST API from the logged-in browser page (the nonce of
          the admin page), then opens them in the admin.
  public  without a login: the published collection and item can be found
          from the home page and by search; the private ones cannot.

The administrator's user and password come from KN_USER and KN_PASS (the
test machine's own, never printed). Each screenshot is written to OUTDIR
and also printed as base64 between "@@shot NAME" and "@@end" lines, so
the CI log carries it. Facts are printed as "fact NAME=VALUE" lines; a
failed check prints "FAIL ..." and the script exits 1 at the end.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import textwrap
from pathlib import Path

from playwright.sync_api import sync_playwright

STEP, URL, OUT = sys.argv[1], sys.argv[2].rstrip("/"), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
FAILS: list[str] = []
STATE = OUT / "seed.json"


def fact(name: str, value) -> None:
    print(f"fact {name}={' '.join(str(value).split())[:500]}", flush=True)


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what, flush=True)
    if not ok:
        FAILS.append(what)


def shot(page, name: str, full: bool = True) -> None:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=full)
    data = base64.b64encode(path.read_bytes()).decode()
    print(f"@@shot {name}")
    for line in textwrap.wrap(data, 8000):
        print(line)
    print("@@end", flush=True)


def visible_text(page) -> str:
    return " ".join(page.inner_text("body").split())


def login(page) -> None:
    page.goto(f"{URL}/wp-login.php", wait_until="networkidle")
    page.fill("#user_login", os.environ["KN_USER"])
    page.fill("#user_pass", os.environ["KN_PASS"])
    page.click("#wp-submit")
    page.wait_for_load_state("networkidle")


def rest(page, method: str, path: str, body=None):
    """A REST call from the logged-in admin page, with its nonce."""
    return page.evaluate(
        """async ([method, path, body]) => {
            const nonce = (window.wpApiSettings && wpApiSettings.nonce) ||
                          (window.tainacan_plugin && tainacan_plugin.nonce) || "";
            const r = await fetch("/wp-json" + path, {method, credentials: "same-origin",
                headers: {"X-WP-Nonce": nonce, "Content-Type": "application/json"},
                body: body === null ? undefined : JSON.stringify(body)});
            let data = null; try { data = await r.json(); } catch (e) {}
            return {status: r.status, data};
        }""",
        [method, path, body],
    )


def upload_image(page) -> dict:
    """A small PNG made in the page, uploaded to the media library."""
    return page.evaluate(
        """async () => {
            const nonce = (window.wpApiSettings && wpApiSettings.nonce) ||
                          (window.tainacan_plugin && tainacan_plugin.nonce) || "";
            const c = document.createElement("canvas"); c.width = 320; c.height = 240;
            const g = c.getContext("2d");
            g.fillStyle = "#2d6a4f"; g.fillRect(0, 0, 320, 240);
            g.fillStyle = "#ffffff"; g.font = "28px sans-serif"; g.fillText("Koha.Nexus E2E", 40, 130);
            const blob = await new Promise(res => c.toBlob(res, "image/png"));
            const r = await fetch("/wp-json/wp/v2/media", {method: "POST", credentials: "same-origin",
                headers: {"X-WP-Nonce": nonce, "Content-Disposition": "attachment; filename=e2e-capa.png",
                          "Content-Type": "image/png"}, body: blob});
            return {status: r.status, data: await r.json()};
        }"""
    )


def step_look(page) -> None:
    page.goto(f"{URL}/", wait_until="networkidle")
    fact("home.title", page.title())
    fact("home.text", visible_text(page)[:400])
    shot(page, "01-home-anonymous")
    links = page.eval_on_selector_all("a", "els => els.map(e => e.textContent.trim() + ' -> ' + e.href)")
    fact("home.links", " | ".join(links[:40]))
    login(page)
    fact("admin.after_login_url", page.url)
    shot(page, "02-admin-dashboard", full=False)
    page.goto(f"{URL}/wp-admin/admin.php?page=tainacan_admin", wait_until="networkidle")
    page.wait_for_timeout(3000)
    fact("admin.tainacan_title", page.title())
    shot(page, "03-tainacan-admin", full=False)


def step_seed(page) -> None:
    login(page)
    page.goto(f"{URL}/wp-admin/admin.php?page=tainacan_admin", wait_until="networkidle")
    page.wait_for_timeout(2000)
    seed: dict = {}
    for key, name, status in (("public", "Acervo E2E Público", "publish"), ("private", "Acervo E2E Restrito", "private")):
        r = rest(page, "POST", "/tainacan/v2/collections", {"name": name, "status": status,
                                                            "description": f"Coleção de teste ({status})"})
        check(r["status"] in (200, 201), f"collection {key} created ({r['status']})")
        cid = (r["data"] or {}).get("id")
        seed[f"{key}_collection"] = cid
        md = rest(page, "GET", f"/tainacan/v2/collection/{cid}/metadata?perpage=50", None)
        meta = {m.get("name"): m.get("id") for m in (md["data"] or []) if isinstance(m, dict)}
        fact(f"seed.{key}.metadata", json.dumps(meta, ensure_ascii=False))
        title = "Item E2E Público: Mapa antigo" if key == "public" else "Item E2E Restrito: Documento interno"
        r = rest(page, "POST", f"/tainacan/v2/collection/{cid}/items", {"title": title, "status": "draft"})
        check(r["status"] in (200, 201), f"item {key} created ({r['status']})")
        iid = (r["data"] or {}).get("id")
        seed[f"{key}_item"] = iid
        # The core metadata (title, description) through the metadata route.
        for mname, value in (("Título", title), ("Title", title),
                             ("Descrição", "Descrição de teste com palavra-chave cartografia"),
                             ("Description", "Descrição de teste com palavra-chave cartografia")):
            if mname in meta:
                r = rest(page, "PATCH", f"/tainacan/v2/item/{iid}/metadata/{meta[mname]}", {"values": value})
                check(r["status"] in (200, 201), f"item {key} metadata {mname} ({r['status']})")
        if key == "public":
            media = upload_image(page)
            check(media["status"] in (200, 201), f"image uploaded ({media['status']})")
            mid = (media["data"] or {}).get("id")
            seed["image"] = mid
            r = rest(page, "PATCH", f"/tainacan/v2/items/{iid}",
                     {"document_type": "attachment", "document": str(mid), "_thumbnail_id": str(mid)})
            check(r["status"] in (200, 201), f"image set as the item's document ({r['status']})")
        r = rest(page, "PATCH", f"/tainacan/v2/items/{iid}", {"status": "publish" if key == "public" else "private"})
        check(r["status"] in (200, 201), f"item {key} status set ({r['status']})")
        fact(f"seed.{key}.item_status", (r["data"] or {}).get("status"))
    STATE.write_text(json.dumps(seed))
    fact("seed", json.dumps(seed))
    page.goto(f"{URL}/wp-admin/admin.php?page=tainacan_admin#/collections/{seed['public_collection']}/items",
              wait_until="networkidle")
    page.wait_for_timeout(4000)
    shot(page, "04-admin-collection-items", full=False)


def step_public(page) -> None:
    seed = json.loads(STATE.read_text())
    page.goto(f"{URL}/", wait_until="networkidle")
    home = visible_text(page)
    fact("public.home_text", home[:500])
    shot(page, "05-home-after-seed")
    # From the home page: a link to the collections, then the public collection.
    found = page.get_by_role("link", name="Acervo E2E Público")
    if not found.count():
        for name in ("Coleções", "Collections", "Acervo", "Itens", "Items"):
            link = page.get_by_role("link", name=name, exact=False)
            if link.count():
                fact("public.entry_link", name)
                link.first.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
                break
        shot(page, "06-collections-page")
        found = page.get_by_role("link", name="Acervo E2E Público")
    check(found.count() > 0, "public collection reachable from the home page without a login")
    if found.count():
        found.first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(4000)
        shot(page, "07-public-collection")
    text = visible_text(page)
    check("Mapa antigo" in text, "published item listed in the public collection")
    check("Documento interno" not in text and "Acervo E2E Restrito" not in text,
          "private collection and item not shown without a login")
    item = rest_anonymous(page, f"/tainacan/v2/items/{seed['private_item']}")
    check(item["status"] in (401, 403, 404), f"private item refused by the API without a login ({item['status']})")
    col = rest_anonymous(page, f"/tainacan/v2/collections/{seed['private_collection']}")
    check(col["status"] in (401, 403, 404), f"private collection refused by the API without a login ({col['status']})")
    page.goto(f"{URL}/?s=cartografia", wait_until="networkidle")
    page.wait_for_timeout(2000)
    shot(page, "08-search")
    fact("public.search_text", visible_text(page)[:400])
    link = page.get_by_role("link", name="Mapa antigo", exact=False)
    if link.count():
        link.first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        shot(page, "09-public-item")
        body = visible_text(page)
        check("Mapa antigo" in body, "the item page opens without a login")
        imgs = page.eval_on_selector_all("img", "els => els.map(e => e.currentSrc || e.src)")
        check(any("e2e-capa" in i for i in imgs), "the item's image is shown")


def rest_anonymous(page, path: str):
    return page.evaluate(
        """async (path) => { const r = await fetch("/wp-json" + path, {credentials: "omit"});
            return {status: r.status}; }""", path)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1366, "height": 900}, locale="pt-BR")
        page = context.new_page()
        {"look": step_look, "seed": step_seed, "public": step_public}[STEP](page)
        browser.close()
    for f in FAILS:
        print(f"FAILED: {f}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
