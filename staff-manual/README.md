# Koha staff interface: interactive English manual

Open `index.html` through a static HTTP server or use the **Koha staff manual
(English)** link on the website homepage. This is separate from the existing
Koha.Nexus panel manual, whose appearance and guides are preserved.

Twenty operational guides cover staff navigation, patron entry, checkouts,
checkins, catalog search, bibliographic and item entry, holds, authorities,
saved reports, acquisitions, serials, inventory, MARC staging, lists, system
preferences, administration, tools, course reserves and interlibrary loans.

Each guide has an explanation, three workflow steps, local-configuration
cautions and a guided exercise with fictional examples. Exercises let a learner
enter example values, receive validation feedback, review and complete the task,
restart, or move between guides. Completion IDs alone are stored in the browser;
exercise entries are discarded when changing/restarting guides. Search, deep
links and completion tracking work without a Koha installation. If browser
storage is blocked the exercises still work for the current visit.

## Source and scope

The guide was checked against the user-supplied `modules.zip` staff templates.
`lessons.json` records the archive SHA-256 and the path and SHA-256 of each
referenced template. No archive, source tree, real patron records, cookies or
credentials are distributed. Labels and workflows are described in original
English instructional text, without redistributing the templates or Koha assets.

The exact Koha version of the archive is not established. Templates show forms
and conditional interface states, not the backend business rules. All forms are
simplified training representations. Required fields, permissions, lending
rules, due dates, MARC frameworks, budgets, provider workflows and enabled
modules must be verified on the institution's Koha. Practice controls are labeled
as such and are not additional buttons claimed to exist in Koha.

This first English edition is an operational introduction, not exhaustive
coverage of every staff screen. In particular, advanced renewals, fines,
receiving/order accounting, serial predictions, authority merging, batch
editing, recalls, bookings, preservation, ERM, plugins, offline circulation,
labels and patron-card design need further dedicated exercises. These features
must not be represented as simulated here. Follow the official Koha manual for
complete version-specific documentation. No real SQL, import, email, purchase,
loan, preference or destructive operation is executed.

## Maintenance

Edit `lessons.json` for guides and `manual.js` / `manual.css` for simulator
behavior. New lessons need a checked template reference and clear limitations.
The home link lives in `site/templates/home.html`; regenerate localized
homepages with `python3 export_site.py`. The manual itself is English only.

Validation:

```sh
python3 -m pytest -q panel/tests/test_staff_manual.py panel/tests/test_staff_manual_browser.py panel/tests/test_site_languages.py panel/tests/test_docs_preview.py
node --check staff-manual/manual.js
python3 export_site.py --check
```
