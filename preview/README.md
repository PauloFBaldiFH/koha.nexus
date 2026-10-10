# Interactive Preview and Manual

A static page for koha.nexus: a simulator of the control panel with a guide
for every screen, card and screen part, in the site's language. No build step.

```
preview/
  index.html            the page (data-src points at the JSON)
  assets/preview.css    styles
  assets/preview.js     the app; window.KohaPreview.setLanguage('br')
  data/preview.json     generated: never edit by hand
  manual/en.json        the guide in English (the reference)
  manual/pt-BR.json     the guide in Brazilian Portuguese
  img/                  optional pictures: <item-id>.webp or <item-id>--N.webp
```

## Regenerate

```
python3 export_docs_preview.py            # writes preview/data/preview.json
python3 export_docs_preview.py --report   # coverage per language
python3 export_docs_preview.py --check    # exit 1 if the JSON is stale
```

The script reads the panel's code (`panel/kei_panel/menus.py`, the screen
files) and the dictionaries in `lang/` and the installer. Panel texts are
translated by those dictionaries, so the simulator follows the panel's own
wording. Each screen part listed in `FEATURES` is checked against its source
file: if a text is no longer there, the item is marked "pending".

## Add a language to the guide

1. `python3 export_docs_preview.py --scaffold es` creates `manual/es.json`
   with every item copied from English and marked `"_todo": true` (items
   marked so are shown in English).
2. Translate the `ui` block and each item's texts. Keep ids, `**bold**`,
   `` `code` `` and `[links](#item-id)` as they are; the panel labels should
   match the panel's own translation (see `strings` in the JSON). Delete
   `_todo` from each item you finish.
3. `python3 export_docs_preview.py --stamp es` records which English each
   item was translated from. When the English changes later, the item shows
   an "outdated" notice until it is updated and stamped again.
4. Regenerate the JSON.

Until a language has its file, the page shows the panel texts in that
language and the guide in English, with a notice.

## Language sync with the site

The page reads `?lang=`, then `localStorage.koha_lang` (the site's key), then
the browser. It writes back both, listens to `storage` events, and accepts
`postMessage({type: "koha-nexus:lang", lang: "br"})` from a parent page when
embedded in an iframe.

## Paths on the live site

The site's home page links here as `preview/` (menu and the Panel section).
`assets/preview.js` resolves `data-src` and `data-asset-base` from the
preview folder (the parent of `assets/`), not from the page URL, and a small
script in `index.html` adds the trailing slash when a host serves `/preview`
without one. The page therefore works at `/preview`, `/preview/` and
`/preview/index.html`, at the domain root or under a subpath.
