# 5. Enriquecimiento y Z39.50/SRU

[Índice](README.md)

## Enriquecer registros existentes

Importar trae una exportación; enriquecer busca datos complementarios o un libro nuevo. Una coincidencia de título requiere revisión bibliográfica. Abra **Library tools > On-demand enrichment**, o `n`; la antigua pantalla bibliográfica por lotes ya no es el acceso del menú actual.

1. Introduzca `all` o `biblionumbers` como `101, 102, 500-510`, y **Search**.
2. Siga trabajo y servidores. Una tarea grande sigue en segundo plano y puede continuar tras reiniciar; necesita máquina disponible para progresar.
3. **Pause/Resume** controla la búsqueda; pausar no revierte lo aplicado.
4. Seleccione el trabajo, abra informe y compare asuntos, clasificación, notas y descripción física.
5. **Search more servers** consulta fuentes aún no usadas; **Choose donor** selecciona fuente para grupos de campos entre resultados disponibles.
6. **Apply** sólo después de revisar y leer la confirmación. Buscar/preparar informe no graba propuestas.

La pantalla actual usa Z39.50 directo. Los servidores tienen límites y fallos temporales; tardanza o ausencia de resultado no demuestra inexistencia del libro. No hay límite general de 50 registros: ese umbral participa en la protección al aplicar, con copias de registros para trabajos pequeños y backup completo verificado para grandes. La revisión sigue siendo necesaria.

**Revert** recupera versiones anteriores conforme las protecciones del flujo y conserva registros editados después de aplicar. No es un restore completo ni deshace toda edición de otros usuarios.

## Buscar un libro nuevo

En la misma pantalla use ISBN o título; autor y año ayudan. Pulse **Find**, examine fuentes y seleccione. **Import as new record** añade tras confirmar y no sustituye un registro con igual ISBN. Se retiran campos locales `9XX` del donante y se registra procedencia, evitando copiar sus ejemplares como propios. Compruebe el resultado y cree sus ejemplares según el procedimiento local. El lote correspondiente puede tratarse con **Undo a MARC import**.

## Autoridades

Abra **Enrich & standardize authorities**, o `h`. Defina alcance y formas exactas o próximas. Las próximas pueden proponer corrección y autoridades preliminares: requieren especial revisión. Busca primero autoridades propias, después base de enriquecimiento y servidores directos, priorizando fuentes brasileñas y restringiendo asuntos a ellas. Esto no garantiza adecuación a su política catalográfica.

Lea informe antes de **Apply**, que crea autoridades necesarias y vínculos con backup de seguridad. Conserva registros editados después del informe. Al revertir se conservan autoridades creadas que aún tienen vínculos; no se borran indiscriminadamente.

## Z39.50 y SRU

Abra **Z39.50 / SRU servers**, o `z`. El servidor de entrada permite consultas de otras bibliotecas y su interruptor afecta también la puerta del firewall. La red comunitaria añade una fuente compartida, distinta de los servidores directos de enriquecimiento.

La tabla de salud muestra fallos; **Reset/Reset all** permite otro intento, no repara el servicio remoto. Para catalogación por copia, seleccione fuentes con espacio, **Scan** y **Add to Koha** para las seleccionadas que funcionan. El test busca un registro real, no sólo una puerta abierta.

SRU disponible en configuración no significa que toda búsqueda de enriquecimiento use SRU. Consultar fuera no requiere exponer el servidor de entrada: son sentidos distintos.

**Pendiente de confirmar:** disponibilidad, cobertura y condiciones de acceso de cada fuente desde la red de la biblioteca en el momento de uso.

## Fuentes comprobadas

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
