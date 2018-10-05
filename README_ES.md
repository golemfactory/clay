# Golem

[![AppVeyor](https://ci.appveyor.com/api/projects/status/ieb6fm74e0f74qm1?svg=true)](https://ci.appveyor.com/project/golemfactory/golem)
[![codecov](https://codecov.io/gh/golemfactory/golem/branch/develop/graph/badge.svg)](https://codecov.io/gh/golemfactory/golem)

El objetivo del proyecto Golem es crear un sistema mundial de procesamiento de potencia de cálculo, en el que los usuarios puedan vender el tiempo de CPU que les sobra de sus ordenadores personales y los consumidores puedan adquirir recursos para tareas que requieran un uso intensivo de los ordenadores. Desde el punto de vista técnico, Golem está diseñado como una red descentralizada de P2P establecida por nodos que ejecutan el software cliente Golem. Para el propósito de este trabajo asumimos que hay dos tipos de nodos en la red Golem: los nodos solicitantes que anuncian tareas de computación y los nodos de procesamiento que realizan cálculos (en la implementación real, los nodos pueden cambiar entre ambos roles).

## Instalación y pruebas

Para Mac OS X (ver. 10.12 (Sierra) o posterior) sigue las instrucciones de instalación de [aquí](https://github.com/golemfactory/homebrew-golem).
Para Ubuntu (16.04 o superior) descarga el [script](https://raw.githubusercontent.com/golemfactory/golem/develop/Installer/Installer_Linux/install.sh), dale permisos de ejecución `chmod +x install.sh` y ejecuta `./install.sh`.
Para MS Windows 10 descarga el instalador desde [aquí](https://github.com/golemfactory/golem/releases/); cuando esté descargado, solo ejecuta `setup.exe`.

Después, lea la descripción de la aplicación y las instrucciones para el [test](https://github.com/golemfactory/golem/wiki/Testing).

[Golem para macOS](https://github.com/golemfactory/homebrew-golem)

[Golem Linux script](https://raw.githubusercontent.com/golemfactory/golem/develop/Installer/Installer_Linux/install.sh)

[Instalador de Golem para MS Windows](https://github.com/golemfactory/golem/releases/)

Todos los paquetes lanzados están disponibles [aquí](https://github.com/golemfactory/golem/releases), sin embargo, le recomendamos encarecidamente que utilice instaladores preparados.

## Uso y resolución de problemas

La documentación para usar la app está ubicada aquí: https://docs.golem.network/

Los problemas más comunes se describen en la sección 9: https://golem.network/documentation/09-common-issues-troubleshooting/

## Advertencia

El proyecto de Golem es un proyecto en curso. La versión actual es una etapa alfa de Brass Golem y no está completamente asegurada. Comprueba [esta lista de cuestiones](https://github.com/golemfactory/golem/labels/security) para más detalles.
Por favor, asegúrese de que entiende el riesgo antes de instalar el software.

## Licencia

Golem es de código abierto y se distribuye bajo la [licencia GPLv3](https://www.gnu.org/licenses/gpl-3.0.html).

## Agradecimientos

Golem se comunica con tecnologías de terceros, algunas de ellas se pueden descargar e instalar con el paquete Golem :
* [Docker](https://www.docker.com/)
* [FreeImage](http://freeimage.sourceforge.net/)
* [Geth](https://github.com/ethereum/go-ethereum/wiki/geth)
* [OpenExr](http://www.openexr.com/)
* [OpenSSL](https://www.openssl.org/)
* [Python3](https://www.python.org/)
* [SQLite3](https://sqlite.org/index.html)
* [Pyvmmonitor](http://pyvmmonitor.com)

Pruebas:
* General: [Minilight](http://www.hxa.name/minilight) por Harrison Ainsworth / HXA7241 y Juraj Sukop.
* Blender: [scene-BMW](https://www.blender.org/download/demo-files/).
* LuxRender: [SchoolCorridor](http://www.luxrender.net/wiki/Show-off_pack) por Simon Wendsche.

Iconos:
* [Freeline](https://www.iconfinder.com/iconsets/freeline) por Enes Dal.

## Ofertas de trabajo

- [C++ & Solidity Software Engineer](docs/jobs/cpp_and_solidity_software_engineer.md)

## Contacto  

Ayúdenos a desarrollar la aplicación enviando problemas y errores. Lea las intrucciones
[aquí](https://github.com/golemfactory/golem/wiki/Testing).

También puede enviarnos un email a `contact@golem.network` o hablar con nosotros en [chat.golem.network](https://chat.golem.network).
