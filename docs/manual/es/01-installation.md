# 1. Instalación

[Índice](README.md)

## Elegir el entorno y comprobar los requisitos

En Windows, Koha funciona dentro de Debian mediante WSL 2. Las herramientas de Windows preparan el entorno, abren el panel e integran la aplicación. En Debian o Ubuntu, el panel y los servicios se instalan directamente en el servidor. Para abrir un catálogo existente, use el panel; no repita la instalación como método de acceso.

| Entorno | Requisitos comprobados |
| --- | --- |
| Windows | Windows 10 versión 2004, compilación 19041 o posterior, o Windows 11; sistema de 64 bits y virtualización activada; 8 GB de RAM, 12 GB recomendados; 10 GB libres en la unidad de instalación, 20 GB recomendados. |
| Debian/Ubuntu | Debian 11/12/13 o Ubuntu 22.04/24.04; arquitecturas amd64 y arm64 identificadas por el instalador; menos de 5 GB libres bloquea la instalación, entre 5 y menos de 10 GB genera un aviso, y 10 GB o más supera esa comprobación. |

Son requisitos de entrada: catálogo, adjuntos, índices y backups necesitan espacio adicional. **RAM Linux, pendiente de confirmar:** la guía recomienda 4 GB para servidor dedicado, con 8 GB recomendados, y 8/12 GB para escritorio o entorno virtualizado. La comprobación Linux actual no impone un mínimo numérico de RAM; superarla no garantiza capacidad para cualquier carga. Windows tolera memoria reservada por el hardware: sus umbrales detectados son 7,5 y 11,5 GB.

Linux requiere privilegios administrativos y acceso al repositorio de Koha. Los puertos TCP 80 y 8080 corresponden al OPAC y al staff. Si están ocupadas, el panel ofrece detener los servicios que las usan. **Autorícelo únicamente si sabe que pueden interrumpirse.**

## Windows con PowerShell

Entre en la cuenta administradora de Windows que utilizará Koha. Abra PowerShell como administrador en esa misma cuenta y ejecute:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Si la elevación solicita la cuenta de otra persona, cancele e inicie sesión con una cuenta apropiada: los componentes WSL pertenecen a la cuenta instaladora. Lea las comprobaciones; resuelva la virtualización desactivada antes de continuar. Responda a las preguntas de creación de la cuenta Debian en la propia ventana; es distinta de la cuenta bibliotecaria de Koha.

Espere la preparación de WSL 2 y Debian. Si pide reiniciar, el instalador registra la continuación para el siguiente inicio de sesión. Cuando abra el panel, elija idioma y **Install Koha server**. Al terminar dentro del panel, salga normalmente y espere la finalización de la integración de Windows.

La carpeta predeterminada es `C:\Koha`; las instalaciones antiguas pueden conservar `C:\KohaEasy`. No la mueva manualmente para reparar una interrupción. Registre el error: el instalador conserva etapas completadas y puede retomarlas o reabrir el panel si falta instalar el servidor. Esto no elimina el riesgo de una reinstalación destructiva.

## Windows con MSIX

El MSIX prepara el mismo entorno WSL; instalar el paquete no configura por sí solo el servidor y la base de datos. Abra PowerShell **normal, sin elevar previamente**, y ejecute:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

El auxiliar descarga el paquete configurado en su código, comprueba su origen, solicita autorización administrativa e instala para el usuario actual. No ignore rechazos. Abre Koha.Nexus para continuar: espere la preparación y complete la instalación guiada. Después salga del panel normalmente y espere los accesos directos, las tareas y la red de Windows. Cerrar antes de completar el servidor no constituye una instalación terminada; vuelva a abrir para continuar.

**Pendiente de confirmar:** disponibilidad y dirección pública de Microsoft Store. El código de empaquetado no acredita una publicación. También queda pendiente el funcionamiento completo de MSIX en ARM64: el manifiesto generado es x64; el soporte arm64 de Linux no lo demuestra. Aunque el manifiesto admita un Windows anterior, planifique con los requisitos completos de WSL indicados arriba.

## Debian y Ubuntu

Descargue y abra el instalador desde el terminal del servidor:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Para conservar el repositorio y sus traducciones junto al instalador:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Elija idioma y **Install Koha server**. Corrija fallos críticos antes de continuar; un aviso no certifica capacidad para cualquier uso. Si utiliza una distribución WSL, debe ser WSL 2 con systemd en ejecución; el flujo rechaza WSL 1. En Windows es preferible la preparación guiada anterior.

## Instalar el servidor desde el panel

1. Abra **Install Koha server**, espere el preflight y lea el informe. Evalúe la interrupción de servicios si hay puertos ocupados.
2. Confirme sólo después de verificar el equipo de destino. Confirme la zona horaria detectada o seleccione región y ciudad.
3. **Si ya existe una instancia, deténgase a comprobarla.** La reinstalación borra base y configuración, exige otra confirmación y la palabra exacta `REINSTALL`. No sirve simplemente para abrir o actualizar el panel.
4. Espere las etapas sin cerrar la ventana: la operación no es cancelable. La estimación de 10 a 30 minutos depende del equipo y de la red.
5. Lea el resultado y el informe ofrecido; una instalación finalizada con incidencias no implica servicios sanos. Considere el reinicio cuando se ofrezca y, en MSIX, espere también la continuación de Windows.

No copie datos privados de la pantalla de resultado a documentos públicos o solicitudes de soporte.

## Fuentes comprobadas

- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [installer](../../../installer).
- [README.md](../../../README.md).
- [install.ps1](../../../windows/install.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [instalar_msix.ps1](../../../windows/msix/instalar_msix.ps1).
- [KohaMsixEntry.cs](../../../windows/msix/KohaMsixEntry.cs).
- [KohaMsixPanel.ps1](../../../windows/KohaMsixPanel.ps1).
- [compilar_msix.ps1](../../../windows/msix/compilar_msix.ps1).
- [install.py](../../../panel/kei_panel/routines/install.py).
