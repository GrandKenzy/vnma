# 01. Uso

> **Versión actual:** `0.3.2` (Beta)

Esta sección explica cómo instalar VNMA, gestionar las dependencias de un proyecto, configurar proyectos y paquetes, y ejecutar código con el runtime vendoreado.

---

## Resumen de la sección

| Guía | Resumen |
| :--- | :--- |
| **[01. Primeros pasos](./01-primeros-pasos.md)** | Instalar VNMA, `vnma init` y la primera instalación. |
| **[02. Gestión de dependencias](./02-gestion-de-dependencias.md)** | Fuentes PyPI, local y Git; restaurar, actualizar, podar, modo offline y enlaces vivos. |
| **[03. Especificaciones de configuración](./03-especificaciones-de-configuracion.md)** | `vnma.toml`, `vnma_config.toml` y reglas de precedencia. |
| **[04. Ejecución en runtime](./04-ejecucion-en-runtime.md)** | `vnma run`, carga hermética, registro de DLL y `vnma exec`. |
| **[05. Integración con IDE](./05-integracion-ide.md)** | Configuración de VS Code y PyCharm. |
| **[06. Dependencias anidadas](./06-dependencias-anidadas.md)** | Paquetes que dependen de otros paquetes y dependencias compartidas. |
| **[07. Puntos de entrada sin `vnma run`](./07-punto-de-entrada-sin-vnma-run.md)** | Iniciar un script o CLI con `python` directamente. |

---

## Resumen rápido

1. **Instalar:** `vnma init` y luego `vnma install <paquete>` desde PyPI, una ruta local o una URL de Git.
2. **Ejecutar:** `vnma run main.py`, o ejecuta `vnma insert-import` una vez y usa `python main.py`.
3. **Compartir:** versiona `vnma.toml` y `vnma.lock`; tu equipo restaura con `vnma install`.
