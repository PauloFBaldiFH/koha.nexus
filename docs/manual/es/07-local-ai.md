# 7. IA local

[Índice](README.md)

La pantalla **AI**, tecla `a`, reúne proveedor, Ollama y dos herramientas: catalogación por fotos en MARC Replace y asistente del inicio staff. Configurar proveedor no las instala automáticamente.

## Ollama local

1. Lea el aviso: IA local puede consumir CPU/RAM y ralentizar Koha.
2. En **Ollama on this server**, **Check Ollama**; si falta, **Install Ollama** y espere.
3. Elija opción de la lista y **Download**; requiere red y disco. No se fijan nombres de modelos porque disponibilidad/lista cambian.
4. Elija **Local Ollama** y compruebe URL; predeterminada `http://127.0.0.1:11434`.
5. **Use for chat** o **Use for cataloguing** según propósito. Fotos necesitan visión; sólo texto no sirve.
6. **Test connection** y **Save**, o **F5** y **Ctrl+S**. Rellenar un campo no lo guarda.

Chat vacío reutiliza selección de visión. **Load models** consulta al proveedor y avisa si usa lista integrada por fallo de conexión. Instalado ocupa disco; en memoria ocupa RAM. **Free memory** descarga de RAM sin borrar y Ollama puede recargar en la siguiente solicitud. Su caja sigue visible con otro proveedor: confirme proveedor y URL guardados, no suponga procesamiento local sólo porque está instalado.

## MARC Replace y fotos

Instale/actualice la página y abra **MARC Replace**. El instalador comprueba compilación con Koha y pregunta por accesos staff. Trabaja un registro por vez: seleccione `.mrc`/`.xml` o pegue texto, indique `biblionumber` para sustituir, use **Preview** y compare antes de confirmar. Vacío crea nuevo: evite duplicar. Conserva ejemplares existentes y excluye campos de item entrantes. Guarda versión previa descargable MARCXML; reenviarla al mismo identificador permite recuperarla, sin sustituir backup completo.

En **AI cataloguing**, envíe fotos legibles de cubierta, portada y reverso disponibles; acepta JPEG/PNG/WebP y al menos una. Elija framework nuevo o registro a sustituir, **Read the photos**, espere y revise borrador contra imágenes: título, responsabilidad, publicación, ISBN, clasificación y ausencias. Corrija MARC antes de confirmar. Clasificación sugerida requiere tablas bibliotecarias; dígito ISBN válido no prueba edición correcta. El borrador no guarda campos de ejemplares.

## Asistente staff

**Install, update or remove the assistant** administra el chat que reemplaza noticias en inicio staff, sin afectar OPAC. Busca con Koha y consultas de lectura definidas por la aplicación, no SQL libre generado. Puede devolver enlaces y propuestas.

**Propuesta no equivale a cambio ejecutado:** revise registro, antes/después y efecto; exige **Approve & Execute** y permisos propios. Si cambió desde la propuesta puede rechazar y pedir otra. Consulte cambios confirmados; limpiar conversación o quitar asistente no los deshace. Quitar borra conversaciones y conserva registro de cambios aprobados.

Observe CPU, memoria y Koha; si se ralentiza evite nuevas fotos y libere memoria cuando corresponda. No hay tiempo garantizado para todo equipo. Proveedor remoto recibe datos de la solicitud: revise política de privacidad e imágenes y no envíe lectores sólo para probar. Etiquetas de coste no garantizan gratuidad.

**Pendiente de confirmar:** RAM, disco y latencia para cada elección/hardware; el mínimo de Koha no garantiza rendimiento IA.

## Fuentes comprobadas

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
