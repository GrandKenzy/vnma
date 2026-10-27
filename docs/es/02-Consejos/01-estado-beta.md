# Estado Beta y consideraciones de estabilidad

`vnma` se encuentra actualmente en **Beta (v0.3.3)**. Este documento ofrece un resumen objetivo de los entornos probados, las expectativas de estabilidad y las prácticas de despliegue recomendadas.

---

## 1. Qué se ha validado

Las siguientes capacidades se han probado en escenarios representativos:

* **Compatibilidad con CPython:** validado en CPython 3.11, 3.12 y 3.14 en Windows (amd64) y Linux.
* **Extensiones nativas C/C++:** verificado con paquetes que distribuyen archivos `.pyd` compilados y bibliotecas compartidas (p. ej. `pygame-ce`, que incluye las DLL de runtime de SDL2).
* **Grafos de dependencias transitivas:** validado con árboles profundos (p. ej. `requests` resolviendo `urllib3`, `certifi`, `idna`, `charset-normalizer`).
* **Compilaciones locales PEP 517:** verificado con árboles de código locales que contienen `pyproject.toml` o un manifiesto `vnma_config.toml`.
* **Dependencias anidadas:** validado con una dependencia Git que también requiere un paquete local dos niveles más adentro (caso diamante); consulta [Dependencias anidadas](../01-Uso/06-dependencias-anidadas.md).
* **Controles de seguridad:** validada la extracción en una sola pasada, la comprobación de rutas canónicas contra Zip Slip y la prohibición de symlinks.
* **Ejecución hermética:** validada la exclusión del `site-packages` global conservando las extensiones de la biblioteca estándar de CPython.

---

## 2. Uso recomendado durante la Beta

1. **Desarrollo y herramientas:** ideal para flujos de trabajo de desarrollo, scripts, herramientas de escritorio y proyectos autocontenidos donde se quiere evitar la sobrecarga de los entornos virtuales.
2. **Despliegues en contenedores:** adecuado para entornos en contenedores donde construir los wheels en una sola capa del proyecto reduce el tamaño de la imagen.
3. **Servicios críticos de producción:** para despliegues de servidor críticos, asegúrate de que toda la suite de pruebas pase con `vnma run` antes de reemplazar los pipelines tradicionales con entornos virtuales.

---

## 3. Reportar problemas

Si encuentras un comportamiento de resolución inesperado, fallos al cargar DLL o discrepancias de empaquetado, repórtalos con:
* La versión exacta de Python y la arquitectura de la plataforma (`python -V`, detalles del SO).
* El contenido de `vnma.toml` y `vnma.lock`.
* La salida de la terminal con los tracebacks de error.
