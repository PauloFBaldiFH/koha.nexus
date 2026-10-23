# 6. OPAC and staff interface appearance

[Manual index](README.md) · [Previous: enrichment](05-enrichment.md)

Open **OPAC and Staff Appearance** from the sidebar or press **o**. This screen configures the public catalogue and professional interface, called staff or intranet. Each side has its own settings.

## A safe procedure

1. Use **Sync current OPAC settings** to load Koha's current settings before editing. Sync reads settings; it does not apply a new theme.
2. Adjust one group of options at a time. Check colours, legibility and images before adding more changes.
3. Use **Preview**. It shows the CSS, JavaScript and content that will be written into Koha; it is not a full browser rendering of the page.
4. Use **Apply**, read the summary and confirm. The flow backs up the database before application.
5. Open the OPAC and staff interface in a browser. Check search, record and login pages as well as home pages. Check readability on a small screen too.

The panel writes its blocks to `OpacUserCSS` and `OpacUserJS`; staff appearance uses `IntranetUserCSS` and, when needed, `IntranetUserJS`. The theme mechanism preserves the library's own blocks. This does not guarantee freedom from visual conflicts with external customisations: check the browser result.

## Colours, material and legibility

Controls include texture, blur, opacity, corners, accent colours and backgrounds. Light/dark switching and the default theme have separate controls. Avoid low contrast between text and background, especially with images or transparency.

The staff area has controls for colours, top bar, quick search, module cards, table density, text size and contrast. Enable **Apply color theme to Staff Client** to use these choices. **Copy OPAC preset** fills the staff fields; **Apply** writes the changes.

## Images

Choose a server file, one of the image hosting services offered on screen, or a direct HTTPS URL. The selector accepts PNG, JPEG, GIF, WebP and ICO; SVG is refused. A file on the librarian's computer must be accessible to the server before it can be selected as a local file.

Use images you own or are authorised to use. For login pages, provide the image description for screen readers. An image hosting page address is not necessarily a direct image address.

If using an external image service, check its configuration through the screen. Do not publish private information in login or OPAC images.

## Carousel and buttons

The carousel can show new arrivals or a Koha list. For a list, enter its number as shown in `shelfnumber=` in the list's address. Adjust title, count, style, speed and autoplay. **Refresh carousel** updates the carousel.

New arrivals depend on available records and covers; an absent cover does not mean a record has disappeared from the catalogue. External cover services require network access.

OPAC quick access buttons and staff home page buttons are configured separately. Check text, address, target and order. Use **Add a button** to add an entry and the row's remove button to delete it before applying.

## Login, news and footer

OPAC and staff login boxes allow an image, description and HTML text. The flow filters unsafe elements, including scripts, styles and event handlers. Do not publish internal instructions there that visitors should not see.

OPAC and staff news each have their own title, text and buttons. They are published as panel-managed entries in Koha; news already created by the library is not replaced by this mechanism.

Enter footer credits as `Field: value` lines, using the fields indicated on screen. Additional links use text, a `|` separator and an address, with a maximum of six links. Enter only public library information.

## Remove the appearance

**Remove** requests confirmation and makes a backup before removing the panel's theme blocks. Its purpose is to return to Koha's appearance while retaining the library's own customisations. This is not a full database restore and does not undo other administrative operations.

If an image, colour or button is wrong, correct the relevant group and apply again. Keep the error message if application fails, for investigation using the troubleshooting chapter.

## Checked sources

- [Appearance screen](../../../panel/kei_panel/views/opac.py), composition, collection and validation, sync, preview, application and removal.
- [Panel menus](../../../panel/kei_panel/menus.py), the `opac` section and shortcut.
