# 8. Administración, mensajes y VPN

[Índice](README.md)

Compruebe estado y backup reciente antes de administrar. Configurar no acredita funcionamiento a través de su red; compruébelo después.

## Cron

Abra **Schedules & cron tasks**, o `s`. Cada fila ofrece activación, frecuencia, hora y, según frecuencia, día o expresión propia. **Reload**, active sólo lo necesario, hora `HH:MM`, **Preview**, **Save** y confirme; recargue para verificar.

Gestiona `/etc/cron.d/koha_tasks`, conserva anterior como `koha_tasks.bak`. Desactivadas quedan comentadas con su horario, líneas propias se preservan. **Defaults** rellena valores que debe guardar. Predeterminados: SQL 23:00 diario y MARC domingo 03:00; revise zona y configuración efectiva. Servidor y Linux deben estar funcionando; no suponga que cron enciende Windows. Los avisos Koha tienen mecanismo distinto de estas tareas adicionales.

## WireGuard

**Security & access hub > WireGuard VPN**, o `v`: indique dirección pública/nombre y puerto UDP. **Set up the VPN** muestra cambios antes de confirmar; en router, encaminamiento UDP hacia el servidor. Nombre cada dispositivo, **Add device**, seleccione y **QR code & profile** para cliente WireGuard; compruebe conexión, staff y tráfico.

No publique perfiles/QR. **Revoke** invalida el perfil y exige uno nuevo para volver. **Turn off** desconecta pero conserva perfiles. Túnel dividido: sólo `10.66.0.0/24`; internet/DNS propios permanecen locales. Staff mediante VPN: `http://10.66.0.1:8080`. WSL sin red mirrored no es directamente accesible y mantiene esta VPN desactivada.

## Mensajes

**Messaging & interoperability**, o `m`: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**.

En E-mail active envío y revise SMTP predeterminado. Botones abren SMTP, dirección bibliotecaria, avisos/recibos y reglas de retraso en Koha. Activar no rellena todos los destinatarios/reglas; revise preferencias y plantillas, siguiendo autenticación del proveedor sin publicar datos privados.

**Set up WhatsApp and Telegram** configura servicio, país/área, pruebas, activación y teléfonos. WhatsApp requiere gateway y Telegram bot/destinatarios; no son servicios independientes de esa configuración. Pruebe destinatario autorizado antes de producción y revise formatos/plantillas antes de corrección masiva.

SMS lleva a `SMSSendDriver` y preferencias de lectores; requiere driver y servicio compatibles, no basta escribir nombre. **Alerts** define recordatorios antes del vencimiento, retrasos, repetición y resumen diario con canales; guarde y use **Dry run (sends nothing)** para simular. Activa tarea correspondiente: verifique cron. Evite duplicación con avisos propios de Koha.

SIP2 configura puerto, red, biblioteca y permisos de autoatención. Revise eliminación de ejemplos y cree el registro Koha mediante botón; equipo y servidor deben corresponder. No exponga toda la red por un test local. Z39.50 lleva a servidores del capítulo 5: salida y entrada son distintas.

## Seguridad, parámetros y actualización

El hub incluye Cloudflare Tunnel, UFW, restricción 8080, HTTPS y Fail2ban. Lea estado/resumen. VPN, túnel y acceso directo tienen alcances diferentes; no cambie firewall remoto sin conocer cómo mantendrá administración. **Pendiente de confirmar:** requisitos del dominio, router, proveedor e institución; código no permite receta universal de publicación.

**Koha settings & parameters** ajusta memoria/procesos, crea super bibliotecario y configura zona horaria. Reserve permisos amplios a quienes los necesitan. **Koha languages** distingue descargar/activar, sólo descargar, activar instalado y listar; compruebe resultado en panel, OPAC y staff.

**Update center** distingue paquetes/esquemas de actualización del panel GitHub. Backup y ventana de mantenimiento; actualizar panel puede cerrar sesión para cargar versión al reabrir. Si falla migración de esquema, un reinicio no demuestra resolución: consulte diagnóstico.

## Administración bibliotecaria

**Library tools** incluye vínculos/sincronización de autoridades, autores duplicados, informes SQL, categorías, calidad y privacidad. Para categoría elija origen/destino diferentes, regla y biblioteca; revise simulación antes del backup y confirmación. Calidad es lectura, no reparación automática. Anonimizar quita vínculos de historial antiguo con lectores según Koha, no todo historial bibliográfico. Eliminar lectores requiere filtros, simulación y confirmar cantidad: es destructivo, revise retención. Nombres parecidos no demuestran autor idéntico; revise propuestas. Herramientas ocultas no se presentan como tarjetas disponibles.

## Fuentes comprobadas

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
