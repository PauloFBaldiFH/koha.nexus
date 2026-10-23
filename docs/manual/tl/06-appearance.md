# 6. Hitsura ng OPAC at staff

[Nilalaman](README.md)

**OPAC and Staff Appearance**, `o`, hiwalay ang pampublikong OPAC at staff/intranet.

**Sync current OPAC settings** nagbabasa, hindi apply. Isang grupo muna. **Preview** CSS/JavaScript/laman, hindi buong rendering. **Apply** summary/kumpirma at backup muna. Suriin home/search/record/login, maliit na screen din.

Blocks sa `OpacUserCSS/OpacUserJS`, kung kailangan `IntranetUserCSS/IntranetUserJS`. Sariling blocks nananatili, posible pa rin visual conflict sa ibang customization.

Texture/blur/opacity/sulok/kulay/background, maliwanag/madilim/initial theme: panatilihin contrast sa image/transparency. Staff top bar/quick search/modules/table density/text/contrast. **Apply color theme to Staff Client**, **Copy OPAC preset** pagpuno lang, **Apply** nagsusulat.

File sa server, iniaalok na image service o direktang HTTPS-URL. PNG/JPEG/GIF/WebP/ICO tanggap, SVG hindi. File lang sa sariling computer kailangan munang maaabot server. Karapatan sa larawan/accessibility description login; hosting page hindi laging direktang image. Ayusin external service nang walang pribadong inilalathala.

Carousel bago/Koha-list `shelfnumber=`, titulo/bilang/style/bilis/autoplay/**Refresh carousel**. Walang cover hindi ibig sabihing buradong record, depende sa data/cover/network. OPAC/staff buttons hiwalay, text/address/target/order, **Add a button**, alisin row bago apply.

Login image/description/HTML na sinasala scripts/styles/events, hindi lihim na instruksyon. Bawat balita sariling titulo/text/buttons, hindi pinapalitan balita ng aklatan. Footer `Field: value`, dagdag link text `|` address, hanggang anim, pampubliko lang.

**Remove** kumpirma/backup bago alisin tema, balik Koha kasama sariling customization. Hindi buong restore/undo ibang pamamahala. Itama grupo/apply, itago error para diagnosis.

## Sinuring sanggunian

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
