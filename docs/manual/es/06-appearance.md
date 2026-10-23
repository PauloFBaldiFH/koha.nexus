# 6. Apariencia del OPAC y del staff

[Índice](README.md)

Abra **OPAC and Staff Appearance**, o `o`. OPAC público y staff/intranet tienen configuraciones propias.

## Aplicar con revisión

1. **Sync current OPAC settings** lee las preferencias actuales antes de editar; no aplica tema.
2. Cambie un grupo a la vez y compruebe colores, imágenes y legibilidad.
3. **Preview** muestra CSS, JavaScript y contenido a escribir, no una página renderizada completa.
4. **Apply**, resumen y confirmación; se hace backup de la base antes de aplicar.
5. Revise en navegador páginas iniciales, búsqueda, registros y acceso, también en pantalla pequeña.

Escribe bloques en `OpacUserCSS`/`OpacUserJS` y `IntranetUserCSS`/`IntranetUserJS` para staff cuando corresponde. Conserva los bloques propios, pero no garantiza ausencia de conflictos visuales con otras personalizaciones.

## Colores e imágenes

Puede ajustar textura, desenfoque, opacidad, esquinas, acentos y fondos; modo claro/oscuro y tema inicial tienen controles propios. Evite poco contraste con imágenes o transparencias. Staff añade barra superior, búsqueda rápida, módulos, densidad de tablas, texto y contraste. Active **Apply color theme to Staff Client**. **Copy OPAC preset** sólo rellena campos; **Apply** los graba.

Elija archivo accesible al servidor, servicio de imágenes ofrecido o URL HTTPS directa. Acepta PNG, JPEG, GIF, WebP e ICO; rechaza SVG. Un archivo sólo en su ordenador debe ponerse al alcance del servidor. Use imágenes autorizadas y descripción para lectores de pantalla en login; una página de alojamiento no siempre es una URL directa. Revise configuración del servicio externo y no publique información privada.

## Carrusel, botones y contenido

El carrusel muestra novedades o lista Koha. Para lista indique el número `shelfnumber=` de su dirección. Ajuste título, cantidad, estilo, velocidad y autoplay; **Refresh carousel** actualiza. Las novedades dependen de registros y cubiertas disponibles: sin cubierta no implica registro eliminado; servicios externos requieren red.

Los accesos OPAC y staff se configuran por separado: texto, dirección, destino y orden. **Add a button** añade y el botón de la fila elimina antes de aplicar.

Login admite imagen, descripción y HTML; se filtran scripts, estilos y manejadores de eventos. No publique instrucciones internas. Noticias OPAC/staff tienen título, texto y botones propios; las entradas del panel no sustituyen noticias existentes de la biblioteca.

El pie usa líneas `Field: value` con los campos indicados. Enlaces adicionales: texto, `|`, dirección; máximo seis. Incluya sólo información pública.

## Quitar el tema

**Remove** confirma y hace backup antes de retirar bloques del tema y volver a la apariencia Koha conservando personalizaciones propias. No es restore completo ni revierte administración ajena al tema. Si un elemento es incorrecto, corrija su grupo y aplique; conserve el error si falla para diagnóstico.

## Fuentes comprobadas

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
