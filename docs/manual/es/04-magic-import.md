# 4. Importación mágica

[Índice](README.md)

## Preparar la entrada

Magic Import lee bibliografía, ejemplares, lectores y autoridades. Reconocer el formato no garantiza interpretar bien cada campo, especialmente sin cabeceras o en etiquetas locales. Conserve original y backup comprobado. Pruebe una muestra representativa con varios ejemplares, acentos, vacíos y excepciones; compare cantidades con el sistema anterior. No publique exportaciones de lectores.

Abra **Magic Import Tool** con `i` y su tarjeta. Elija archivo o carpeta accesible al Linux que ejecuta el panel; un archivo sólo en el ordenador del navegador o terminal remoto no está automáticamente en el servidor.

| Formato | Revisión necesaria |
| --- | --- |
| MARC21 ISO 2709, MARCXML y texto MARC | Títulos, acentos, autoridades y ejemplares. El lector reconoce `.mrk` de MarcEdit; no exige conversión sólo por esa extensión. |
| CSV/TSV, `.xlsx`, `.xls`, `.ods`, `.dbf` | Separador, encabezados, contenido y destinos; usa valores y cabeceras disponibles. |
| JSON/XML tabular | Estructura reconocida; un XML cualquiera no es necesariamente MARCXML. |
| SQL tabular, incluso fragmentos sin cabecera | Relaciones y campos ambiguos. Extrae datos reconocibles, no ejecuta SQL como programa de migración. |
| ISIS | Exportación PostgreSQL reconocida con `acervo`. Un maestro CDS/ISIS `.mst` requiere exportación desde WinISIS en ISO 2709. |
| Biblioteca Fácil | Backup reconocido o carpeta de datos con tablas relacionadas juntas; revise bibliografía, lectores, préstamos y reservas por separado. |
| Backup completo Koha | Se dirige al restore, que sustituye la base, no añade registros. |

Un dump PostgreSQL de otro sistema, especialmente binario `pg_dump`, no es una base MariaDB lista para Koha. Si no se admite, exporte MARC o planillas desde origen. En compactados revise cada miembro. PDF, imágenes, documentos y ejecutables no son exportaciones bibliográficas utilizables por este lector.

## Mapeo manual integrado

1. Compruebe **Bibliographic**, **Patrons** o **Authorities** y cambie un modo incorrecto.
2. Examine la cuadrícula de registros/campos y cada destino. La barra divisoria o **Ctrl+Up/Down** ajustan su altura.
3. Elija conservar, redirigir, texto fijo o ignorar. Antes de descartar un identificador, comprenda sus relaciones.
4. Abra **Values of this Koha** para códigos existentes, biblioteca/tipo/categoría predeterminados y sustituciones origen/destino.
5. **Record preview** muestra el resultado. **Check the whole file** prepara y valida el archivo completo sin importarlo en Koha en esa etapa.
6. Dé nombre al perfil y **Save**; seleccione uno guardado y **Use** para cargarlo. Revíselo si cambia la estructura.
7. **Apply** o **Ctrl+S** acepta el mapeo y continúa la preparación, no es la confirmación final de escritura. **Skip: import as it is** y **Esc** omiten el mapeo manual, no cancelan todo el procedimiento.

Las opciones adicionales agrupan duplicados y ajustan texto. Revise la vista previa antes de transformar lotes; siglas, nombres propios y códigos no deben recibir correcciones indiscriminadas.

## Ejemplares, lectores y autoridades

Los ejemplares Koha están en `952`; se preservan y pueden remapear biblioteca y tipo cuando se solicita. No sustituya un código válido sólo por diferir del predeterminado. Revise biblioteca de origen/actual, barcode, signatura, tipo, ubicación y adquisición. `949`, `852`, `950` y `990` requieren interpretación: Pergamum y Biblivre no atribuyen necesariamente el mismo sentido a sus subcampos.

Una anotación de depósito legal con `DL` y fecha no crea automáticamente un ejemplar. Revise exclusiones y evidencia independiente de inventario. Barcode ausente solicita revisión por defecto; generarlo requiere elegir esa política e identidad estable de migración/origen. No renumera silenciosamente colisiones. En tablas SQL, exija relación reconocida; posición de columna y orden de filas no bastan. Si el vínculo no está claro, deténgase y corríjalo.

En **Patrons**, compruebe nombre, apellidos, tarjeta, contactos, dirección, fechas, biblioteca y categoría existente. E-mail, CPF y fecha detectados son indicios, no certeza. Nacimiento, inscripción y vencimiento pueden parecer iguales. La actualización de lectores existentes se pregunta y usa tarjeta para correspondencia; no equivale a crear sólo nuevos. No asigne permisos o autenticación suponiendo el significado de una columna.

En **Authorities**, revise identificador, encabezamiento autorizado, variantes, relaciones y tipo. Cambiar de modo no inventa información ausente.

## Confirmar y verificar

Lea cantidades, rechazos y preguntas pendientes antes de escribir. Para registros existentes puede mantener catálogo y añadir sólo ejemplares nuevos, sustituir por el entrante, o crear cada título sin comparar. Evite repetir lotes accidentalmente.

**Un fallo posterior puede dejar etapas anteriores importadas.** Guarde resumen/logs y compruebe antes de repetir. Verifique muestras, ejemplares, lectores y vínculos en Koha. **Library tools > Undo a MARC import** trata lotes MARC, no revierte universalmente lectores, préstamos y reservas. Para la base completa use Backup center con sus precauciones.

**Pendiente de confirmar:** compatibilidad con un layout propietario o versión concreta sin muestra y revisión del resultado.

## Fuentes comprobadas

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
