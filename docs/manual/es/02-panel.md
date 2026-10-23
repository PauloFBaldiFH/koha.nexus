# 2. Primeros pasos y panel

[Índice](README.md)

## Abrir y navegar

En Debian o Ubuntu preparados por el instalador, ejecute:

```bash
sudo config.sh
```

En Windows use el icono **Koha** o abra Koha.Nexus instalado mediante MSIX. El primer inicio puede preguntar el idioma. Si falla la preparación Textual, el iniciador puede ofrecer el panel clásico. Este manual describe principalmente Textual; no traslade números de opciones de menús antiguos.

La barra lateral contiene las secciones. Destaque con las flechas y abra con **Enter**, o haga clic. Mover el destaque no ejecuta la acción. Abra la tarjeta de la tarea y lea las preguntas. **Tab** cambia el foco; termine de editar o salga de un campo antes de usar atajos de letras.

| Tecla | Acción |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Terminal Debian |
| `Ctrl+B` | Mostrar u ocultar la barra lateral |
| `q` | Salir del panel |

Salir de un panel inactivo no apaga el servidor. Durante una operación, respete su indicación de cancelación. Instalación y restore tienen etapas no cancelables; cerrar la ventana a la fuerza no es un procedimiento seguro.

## Interpretar Control Dashboard

La pantalla muestra estado general de Koha y memoria disponible, último backup con fecha/antigüedad/archivo, espacio libre, direcciones de acceso y componentes MariaDB, Apache, RabbitMQ, Memcached y Koha con comprobaciones HTTP.

El indicador de backup combina antigüedad del archivo y resultado de la última ejecución nocturna. Pueden coexistir archivo reciente y ejecución fallida; lea ambos. Un indicador favorable no sustituye una prueba de restore. Una respuesta HTTP tampoco demuestra que el instalador web de Koha se haya completado ni que funcionen todas las operaciones bibliotecarias.

**Refresh** relee el estado. **Restart Koha** solicita reparación/reinicio de servicios: tenga en cuenta a quienes usan el catálogo. **Export diagnostics** prepara información para soporte. Los botones pueden estar deshabilitados cuando el instalador presente no implementa la tarea correspondiente.

## Direcciones y primer acceso

Use las tarjetas de dirección para abrir o copiar la URL. Si no puede abrir un navegador, el panel puede copiarla para pegarla en el navegador de su ordenador. Los valores locales predeterminados son OPAC `http://localhost/` y staff `http://localhost:8080/`, puertos 80 y 8080.

En otro equipo use la dirección de red indicada, no su propio `localhost`. Si WSL usa NAT y el panel avisa que la red local no es accesible, compruebe la preparación de red Windows con el responsable técnico; no presuponga acceso desde todos los equipos.

Si el staff presenta el instalador web de Koha, complételo antes de operar la colección. Sus pantallas pueden variar según la versión. Después, **Create super librarian** está en **Koha settings & parameters** y abre su propio registro; introduzca los datos privados sólo allí.

Antes de comenzar: actualice el dashboard, compruebe servicios y direcciones, abra OPAC y staff desde el equipo adecuado, genere y pruebe un backup, y confirme dónde está la copia fuera del servidor y quién puede recuperarla. El último punto es una recomendación operativa: una copia externa utilizable depende de terminar y comprobar su transferencia.

## Fuentes comprobadas

- [installer](../../../installer).
- [app.py](../../../panel/kei_panel/app.py).
- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [main.py](../../../panel/kei_panel/screens/main.py).
- [install.py](../../../panel/kei_panel/routines/install.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [dashboard.py](../../../panel/kei_panel/views/dashboard.py).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [menus.py](../../../panel/kei_panel/menus.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
