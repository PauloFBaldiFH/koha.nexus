# 3. Backup y restore

[Índice](README.md)

## Centro, tipos y destinos

Abra **Backup center** o pulse `b`. Reúne último backup, tamaño, resultado, **Compression** y tarjetas:

| Tarjeta | Función |
| --- | --- |
| Download latest backup | Copiar el archivo más reciente encontrado |
| Generate manual backup and download to PC | Crear, comprobar y transferir un backup SQL |
| Export MARC21 records now | Exportar registros bibliográficos y autoridades |
| Restore database | Sustituir la base actual |
| Configure cloud backup | Configurar el envío externo |
| Test integrity of latest backup | Importar en una base temporal para probar |

**Restore database es una tarjeta de este centro**, no un botón superior ni una entrada independiente del menú principal. Resultado se refiere a la última ejecución nocturna; fecha y tamaño, al archivo más reciente. No siempre corresponden a la misma ejecución.

Un backup SQL contiene la base Koha, no una imagen completa de Windows, Debian o sus archivos. MARC21 reúne bibliografía y autoridades en `.tar.gz`; no recupera por sí solo lectores y circulación. Antes de un restore sobre una base con tablas, se crea y valida una copia de seguridad; una base vacía puede omitirla.

Los directorios predeterminados son `/var/backups/koha_sql` para SQL automático y copias de seguridad, y `/var/backups/koha_marc` para MARC. El backup manual tiene destino propio: por defecto, `backups` dentro de la carpeta personal identificada por el panel. Una copia `.part` sigue siendo temporal; sólo se convierte en archivo final tras las comprobaciones.

## Compresión

Seleccione **Compression**: gzip `.sql.gz` ofrece compatibilidad amplia; Zstandard `.sql.zst` es rápido y menor, sugerido para catálogos grandes; XZ/LZMA `.sql.xz` reduce más a costa de tiempo. La selección se guarda inmediatamente, sin botón adicional, y afecta nuevos backups nocturnos, manuales y de seguridad; no recomprime archivos existentes.

Si no se instala el compresor necesario, lea el error y el formato realmente utilizado: el flujo puede continuar con gzip. El restore reconoce archivos compatibles independientemente de esta selección. Use `.sql`, `.sql.gz`, `.sql.zst` o `.sql.xz`; la extensión no prueba la validez del contenido.

## Crear y descargar

1. Abra **Generate manual backup and download to PC**, revise la carpeta del servidor y elija un destino escribible.
2. Pulse **Save backup** y espere generación y comprobación. La pantalla no se cierra mientras guarda o copia.
3. Compruebe nombre, tamaño y ruta. En WSL use **Save to Windows Downloads** o **Choose folder in Windows**. En conexión remota ejecute el comando de transferencia mostrado en su propio ordenador.
4. Compruebe el archivo recibido y cierre con **Finish and exit**.

Los botones Windows sólo aparecen en WSL. No reutilice comandos de otra instalación: el panel calcula archivo y servidor. Si hay otro backup o restore activo, espere; no eluda el bloqueo compartido iniciando operaciones concurrentes por fuera.

**Download latest backup** copia un archivo existente; no crea uno nuevo. En escritorio Linux o WSL intenta usar Downloads; por SSH puede mostrar un comando para su ordenador. Si no encuentra archivo, genere un backup manual.

## Probar y exportar

En **Test integrity of latest backup**, compruebe archivo y fecha; **Choose another file** permite cambiarlos. Confirme, espere la importación temporal y lea el resultado con cantidades de tablas, registros y lectores cuando tiene éxito. No sustituye producción; el éxito corresponde a ese archivo en ese entorno. Conserve acceso a la misma copia transferida.

En **Export MARC21 records now**, lea la confirmación, autorice y espere el paquete bibliográfico y de autoridades. Compruebe ruta y contenido y descargue o transfiera con la instrucción mostrada. Koha sigue funcionando. Si hay nube configurada, el resultado informa también del envío. Conserve SQL para recuperar la base completa.

## Nube y horarios

**Configure cloud backup** ofrece dos rutas rápidas de Google Drive y otros servicios, incluidos OneDrive, MEGA y S3. Elija autorización en el servidor o desde otro ordenador según el entorno, siga la URL presentada y complete los campos del proveedor. S3 distingue servicio, región o endpoint y bucket. Espere la prueba real de envío y confirme la recepción en destino; no dependa de una configuración fallida.

Introduzca información privada sólo en su instalación, nunca en documentación, imágenes públicas o mensajes de soporte. Este manual no publica los archivos que la guardan. Los horarios predeterminados son SQL diario a las 23:00 y MARC los domingos a las 03:00, hora del servidor; cron puede haberlos cambiado.

## Restore: operación destructiva

**Confirmar autoriza sustituir la base actual.** Reserve una ventana de mantenimiento y mantenga copia externa; es una recomendación operativa, no una transferencia automática que el panel haga por usted.

1. Abra **Restore database**, seleccione el archivo accesible al servidor y siga las instrucciones de transferencia si está en otro ordenador. Bajo WSL puede copiarse desde Windows a almacenamiento Linux antes del restore.
2. Lea las comprobaciones de lectura, contenido, integridad y espacio. Investigue archivos sospechosos o incompletos aunque la extensión parezca correcta.
3. Revise otra vez el archivo al confirmar la sustitución. Puede desistir hasta esa confirmación; después espere sin cerrar, pues el flujo no es cancelable.

Primero importa SQL en una base temporal y comprueba tablas esenciales y cantidad. Si falla, se detiene antes de sustituir el catálogo. Si la base actual tiene tablas, crea una copia validada en la carpeta SQL con prefijo `pre_restore_safety_backup_`, fecha, hora y compresión. Si falla esa copia, no debe borrar la base existente; una base vacía puede omitirla.

Después detiene clientes, recrea/importa la base, actualiza el esquema, sincroniza el motor de búsqueda, reconstruye índices y reinicia servicios. Intenta reaplicar el tema guardado si hay estado disponible.

Un fallo temporal o de copia previa no equivale a una sustitución realizada. En fallos de recreación, importación o esquema puede intentar recuperar la base anterior, según etapa y copia disponible; **el rollback puede fallar**. Un error de indexación puede ocurrir después de restaurar la base: no presuponga que volvió el catálogo anterior.

Conserve el mensaje completo y los logs `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log` y, para indexación, `/var/log/koha-easy-install/zebra-rebuild.log`. Para recuperar, vuelva a la tarjeta del centro, no a números antiguos de menú; solicite asistencia si desconoce el estado. Después actualice el dashboard y compruebe registros y búsquedas en OPAC y staff. Terminar SQL no demuestra recuperación de archivos externos a la base.

## Fuentes comprobadas

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
