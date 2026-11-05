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
  direct  the pages Tainacan serves (/colecoes/, /itens/, the collection,
          its search, the item) opened by their address, not from the home.
  blog    without a login: the home page is WordPress's blog (an existing
          installation whose home page was not prepared). Screenshot only.

The administrator's user and password come from KN_USER and KN_PASS (the
test machine's own, never printed). Each screenshot is written to OUTDIR
(the workflow publishes them for review). Facts are printed as "fact NAME=VALUE" lines; a
failed check prints "FAIL ..." and the script exits 1 at the end.
"""

from __future__ import annotations

import json
import os
import sys
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
    """A screenshot in OUT (the workflow keeps them and publishes them for
    review); never printed in the log."""
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    print(f"shot {name}.png", flush=True)


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


SEARCH_BOX = ("#tainacan-items-page input[type=search], #tainacan-items-page input[type=text], "
              "[data-module=faceted-search] input[type=search], [data-module=faceted-search] input[type=text]")


def faceted_search(page, words: str) -> str:
    """Types WORDS in Tainacan's faceted search of this page and returns
    the visible text after it answers ("" when the page has no search)."""
    box = page.locator(SEARCH_BOX)
    fact("search.boxes", box.count())
    if not box.count():
        return ""
    box.first.fill(words)
    box.first.press("Enter")
    page.wait_for_timeout(6000)
    return visible_text(page)


def step_look(page) -> None:
    page.goto(f"{URL}/", wait_until="networkidle")
    page.wait_for_timeout(4000)
    fact("home.title", page.title())
    fact("home.text", visible_text(page)[:400])
    shot(page, "01-home-anonymous")
    links = page.eval_on_selector_all("a", "els => els.map(e => e.textContent.trim() + ' -> ' + e.href)")
    fact("home.links", " | ".join(links[:40]))
    # A new installation: the home page of the collection, not the blog.
    text = visible_text(page)
    check("Olá, mundo!" not in text and "Hello world!" not in text, "the home page is not WordPress's sample blog")
    check(any(n in " ".join(links) for n in ("Coleções", "Collections")), "the home page links to the collections")
    check(any(n in " ".join(links) for n in ("Todos os itens", "All items")), "the home page links to all the items")
    check(page.locator(SEARCH_BOX).count() > 0, "the home page has the search of the collection")
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
    # The search of the home page (Tainacan's faceted search): by a word of
    # the description, the published item only.
    page.goto(f"{URL}/", wait_until="networkidle")
    page.wait_for_timeout(4000)
    found_text = faceted_search(page, "cartografia")
    shot(page, "08-search")
    fact("public.search_text", found_text[:400])
    check("Mapa antigo" in found_text, "the search of the home page finds the published item by its description")
    restricted = faceted_search(page, "interno")
    check("Documento interno" not in restricted, "the search of the home page does not show the private item")
    # WordPress's own search (?s=) does not search Tainacan's items: a fact.
    page.goto(f"{URL}/?s=cartografia", wait_until="networkidle")
    page.wait_for_timeout(2000)
    fact("public.wp_search_text", visible_text(page)[:300])
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
            let body = null; try { body = await r.json(); } catch (e) {}
            return {status: r.status, body}; }""", path)


def step_direct(page) -> None:
    """The public pages Tainacan itself serves, opened by their address
    (not from the home page): do they work when the address is known?"""
    seed = json.loads(STATE.read_text())
    page.goto(f"{URL}/", wait_until="networkidle")
    col = rest_anonymous(page, f"/tainacan/v2/collections/{seed['public_collection']}")
    col_url = (col.get("body") or {}).get("url") or ""
    fact("direct.collection_api_status", col["status"])
    fact("direct.collection_url", col_url)
    items = rest_anonymous(page, f"/tainacan/v2/collection/{seed['public_collection']}/items?fetch_only=title,url")
    body = items.get("body") or {}
    rows = body.get("items") if isinstance(body, dict) else body
    item_url = ""
    for row in rows or []:
        if isinstance(row, dict) and "Mapa" in str(row.get("title")):
            item_url = row.get("url") or ""
    fact("direct.item_url", item_url)
    for name, path in (("10-collections-archive", "/colecoes/"), ("11-items-repository", "/itens/")):
        resp = page.goto(f"{URL}{path}", wait_until="networkidle")
        page.wait_for_timeout(4000)
        shot(page, name)
        text = visible_text(page)
        fact(f"direct.{name}.http", resp.status if resp else 0)
        fact(f"direct.{name}.text", text[:400])
        if name.startswith("10"):
            check("Acervo E2E Público" in text, "the collections page (/colecoes/) lists the public collection")
            check("Acervo E2E Restrito" not in text, "the collections page hides the private collection")
        else:
            check("Mapa antigo" in text, "the items page (/itens/) lists the published item")
            check("Documento interno" not in text, "the items page hides the private item")
    if col_url:
        page.goto(col_url, wait_until="networkidle")
        page.wait_for_timeout(5000)
        shot(page, "12-collection-page")
        text = visible_text(page)
        fact("direct.collection_text", text[:400])
        check("Mapa antigo" in text, "the collection page lists the published item")
        found_text = faceted_search(page, "cartografia")
        check(bool(found_text), "the collection page has Tainacan's faceted search")
        if found_text:
            shot(page, "13-collection-search")
            check("Mapa antigo" in found_text, "the collection's own search finds the item by its description")
    if item_url:
        page.goto(item_url, wait_until="networkidle")
        page.wait_for_timeout(4000)
        shot(page, "14-item-page")
        text = visible_text(page)
        fact("direct.item_text", text[:400])
        check("Mapa antigo" in text, "the item page opens without a login")
        imgs = page.eval_on_selector_all("img", "els => els.map(e => e.currentSrc || e.src)")
        check(any("e2e-capa" in i for i in imgs), "the item's image is shown on its page")


def step_blog(page) -> None:
    page.goto(f"{URL}/", wait_until="networkidle")
    fact("blog.text", visible_text(page)[:300])
    shot(page, "00-home-existing-blog")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1366, "height": 900}, locale="pt-BR")
        page = context.new_page()
        {"look": step_look, "seed": step_seed, "public": step_public, "direct": step_direct,
         "blog": step_blog}[STEP](page)
        browser.close()
    for f in FAILS:
        print(f"FAILED: {f}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
