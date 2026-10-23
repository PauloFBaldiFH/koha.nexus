# 9. Diagnóstico y logs

[Índice](README.md)

Anote acción, hora, error completo y qué sigue funcionando. Página accesible, servicio activo y búsqueda correcta son comprobaciones distintas. No reinstale ni haga restore como primera respuesta universal.

## Secuencia de diagnóstico

Actualice **Control Dashboard**. En **Diagnostics & maintenance center**, abra **Detailed server & Koha status**, ejecute **Full system health check** y lea informe. **View latest validation report** permite volver a él; **Export diagnostics** en dashboard prepara soporte y muestra ruta. Aunque oculta datos de acceso, revise nombres, lectores y direcciones sensibles antes de compartir; no copie toda la instalación indiscriminadamente.

Si Textual no abre puede recurrir al modo clásico. Eso no revierte operaciones previas: guarde mensaje y log.

## Ubicación y lectura

| Ruta | Contenido |
| --- | --- |
| `/var/log/koha-easy-install/` | Directorio principal Linux |
| `apt.log` | Paquetes y etapas que lo utilizan |
| `validacao-*.log` | Informes fechados |
| `new-panel.log` | Errores Textual y traceback |
| `backup_sql.log`, `backup_marc.log` | Backups y exportaciones |
| `restore.log`, `restore-import.log` | Restore e importación SQL |
| `zebra-rebuild.log`, `search-engine.log` | Índice/búsqueda |
| `/var/log/koha-easy-install/tools/` | Operaciones de herramientas |
| `C:\Koha\logs`, antiguamente `C:\KohaEasy\logs` | Logs Windows según instalación detectada |

`*` representa archivos fechados, no un nombre literal; pueden no existir antes de ejecutar la rutina. Prefiera la ruta exacta mostrada. **Library tools > View tool logs** selecciona por fecha/rutina; los logs restringidos pueden contener datos personales.

El informe contiene contexto, fecha, versión y OK/avisos/fallos/información. Lea cada mensaje, no sólo total. **No critical failures** puede incluir avisos: backup antiguo requiere respuesta distinta de fallo de base o búsqueda. Tras corregir, valide otra vez y compare.

**Real-time Apache log auditing** selecciona staff/intranet u OPAC y busca ruta actual o alternativa antigua. En Textual **Pause** o `p` pausa visualización, no Apache; **Continue** sigue, **Back/Esc** cierra. El clásico usa `Ctrl+C` para salir de este seguimiento, no toda operación. Busque hora y contexto de `error`, `fatal`, `denied`, `fail`; destacar una palabra no identifica causa.

## Según el síntoma

- OPAC/staff inaccesible: revise Apache, MariaDB, Plack, cache y dirección local/red/VPN/túnel. `localhost` es el ordenador del navegador. **Restart / repair Koha services (Memcached, Plack)** puede interrumpir acceso; lea resultado y revalide, no dé éxito sólo por terminar.
- Registro ausente en búsqueda: examine motor, cola y relación índice/base. **Search engine & indexing > Repair / rebuild indexing** pide confirmaciones; espere. Cambiar a Elasticsearch no es primer paso obligatorio.
- Backup ausente: hora, resultado, espacio y equipo/Linux activos en cron. `.part` no está terminado. Revise `backup_sql.log`, pruebe integridad o genere manual; no borre última copia válida sin otra segura ni inicie tareas solapadas.
- Importación fallida/cantidades: guarde logs Magic Import y MARC indicados, compare entrada/preparación/escritura, modos, bibliotecas, tipos, barcodes, rechazos y duplicados. Una muestra correcta no valida todo; use validación completa y compruebe etapas terminadas antes de repetir.
- Restore fallido: identifique etapa. Indexación puede fallar con base ya restaurada; recuperación previa puede fallar también. Compruebe base, búsqueda y validación antes de declarar éxito.
- IA/enriquecimiento lento: revise Ollama, selección y memoria, o trabajo/servidores/límites. No repita tareas grandes por demora; servicio remoto y falta de RAM requieren diagnósticos distintos.

## Icono o bandeja Windows

En PowerShell del usuario conectado, **sin administrador**, ejecute:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

No es sólo lectura: puede recrear accesos y reiniciar bandeja. Guarda `diagnose-<date>.txt` en `logs` de la instalación detectada. Conserve ruta y error; es distinto de instalar con PowerShell administrativo.

**Deep database optimization & log cleanup** mantiene y reinicia servicios, pero puede borrar historial útil. Preserve diagnósticos y reserve mantenimiento; no lo use para esconder errores. Al pedir ayuda informe versión, Windows/WSL o distribución, acción/hora, mensaje completo, estado OPAC/staff/búsqueda y operación previa; comparta extractos revisados por privacidad.

**Pendiente de confirmar:** causa de un fallo sin mensaje completo y log; no atribuya todo a red o instalación.

## Fuentes comprobadas

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
