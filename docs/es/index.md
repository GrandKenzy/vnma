# Documentación de VNMA

> **Versión:** `0.3.2` (Beta)
> **Runtime:** CPython 3.11+ · Windows y Linux

Bienvenido a la documentación oficial en español de **VNMA**, un gestor de dependencias y vendoring que instala los paquetes en un directorio local del proyecto (`vendor/`) en lugar de crear entornos virtuales.

---

## Índice de documentación

### [01. Uso](./01-Uso/index.md)
Instalación de VNMA, gestión de dependencias, configuración de proyectos y paquetes, y ejecución de código.
- **[01. Primeros pasos](./01-Uso/01-primeros-pasos.md)** — Instalar VNMA, inicializar un proyecto y la primera instalación.
- **[02. Gestión de dependencias](./01-Uso/02-gestion-de-dependencias.md)** — Instalar desde PyPI, rutas locales y Git; actualizar, podar, modo offline y enlaces vivos.
- **[03. Especificaciones de configuración](./01-Uso/03-especificaciones-de-configuracion.md)** — Esquema de `vnma.toml` y `vnma_config.toml`, y orden de precedencia.
- **[04. Ejecución en runtime](./01-Uso/04-ejecucion-en-runtime.md)** — `vnma run`, carga hermética, registro de DLL y `vnma exec`.
- **[05. Integración con IDE](./01-Uso/05-integracion-ide.md)** — Configuración de VS Code y PyCharm.
- **[06. Dependencias anidadas](./01-Uso/06-dependencias-anidadas.md)** — Paquetes que dependen de otros paquetes, dependencias compartidas y orden de instalación.
- **[07. Puntos de entrada sin `vnma run`](./01-Uso/07-punto-de-entrada-sin-vnma-run.md)** — Ejecutar un script o CLI con `python` usando `vnma insert-import`.

### [02. Consejos](./02-Consejos/index.md)
Estabilidad, limitaciones y dirección del proyecto.
- **[01. Estado Beta](./02-Consejos/01-estado-beta.md)** — Qué se ha validado y cómo usar VNMA durante la beta.
- **[02. Limitaciones conocidas](./02-Consejos/02-limitaciones-conocidas.md)** — Restricciones del modelo de ejecución de Python y de la implementación actual.
- **[03. Hoja de ruta](./02-Consejos/03-hoja-de-ruta.md)** — Trabajo reciente y mejoras planeadas.
- **[04. Visión de la comunidad](./02-Consejos/04-vision-de-la-comunidad.md)** — Dónde encaja VNMA y dónde no.

### [Changelog](../../changelog/README.md)
Notas de versión, un archivo por versión (en inglés).
