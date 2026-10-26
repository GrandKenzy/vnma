# Modelo de ejecución en runtime

Este documento explica cómo `vnma` ejecuta scripts, carga paquetes de forma hermética y resuelve bibliotecas dinámicas sin entornos virtuales.

---

## 1. Ejecutar aplicaciones con `vnma run`

Para ejecutar el script de una aplicación con el runtime vendoreado activo:

```bash
vnma run main.py -- --option value
```

### Ciclo de vida del proceso

Al invocar `vnma run`:
1. `vnma` localiza la raíz del proyecto y su directorio vendor.
2. Configura las variables de entorno:
   * `PYTHONPATH` incluye `vendor/.vnma_meta/site` (que contiene `sitecustomize.py`) y `vendor/`.
   * `PATH` antepone `vendor/.vnma_meta/.bin/` para exponer las herramientas CLI instaladas.
   * `PYTHONNOUSERSITE=1` impide cargar los directorios de usuario.
3. Lanza el intérprete de Python directamente:
   ```bash
   python main.py --option value
   ```
   Como la ejecución no usa `python -c "exec(...)"`, `sys.argv[0]` apunta correctamente a `main.py`, lo que preserva la compatibilidad con `argparse`, la inspección de `sys.argv` y el módulo `multiprocessing`.

---

## 2. Ejecución directa con Python (`import vendor.__bootstrap__`)

Si prefieres lanzar tu aplicación directamente con `python main.py` sin usar la CLI de `vnma`:

Agrega el import del bootstrap al inicio de tu archivo de entrada:

```python
import vendor.__bootstrap__
import requests
import pygame

# El código de la aplicación sigue...
```

Ejecuta `vnma insert-import` para agregar esta línea automáticamente. Consulta [Puntos de entrada sin `vnma run`](07-punto-de-entrada-sin-vnma-run.md).

---

## 3. Aislamiento de rutas en runtime

Aísla la ejecución de tu aplicación:

1. Identifica las rutas de la biblioteca estándar (`stdlib`, `platstdlib`, archivos zip del intérprete).
2. Identifica los directorios de paquetes globales:
   * `purelib` y `platlib` (`site-packages` del sistema).
   * Site-packages del usuario (`site.getusersitepackages()`).
   * Rutas de paquetes de distribución (`dist-packages`).
3. Filtra `sys.path` en el lugar, eliminando los paquetes de terceros globales y de usuario, y conservando la biblioteca estándar de Python y el directorio local `vendor/`.

Esto evita el problema común de que el código funcione localmente porque una dependencia existe en el Python del sistema del desarrollador, pero falle al desplegarse en un contenedor limpio.

---

## 4. Registro nativo de DLL en Windows

En Windows con Python 3.8+, Python ya no busca en el `PATH` del sistema las DLL que necesitan las extensiones compiladas (`.pyd`).

En lugar de hacer recorridos recursivos del sistema de archivos (`os.walk`) al iniciar, `vnma` registra durante la instalación los directorios relativos exactos que contienen archivos `.dll` en una tupla estática:

```python
_DLL_SUBDIRS = ['pygame', 'pygame/_sdl2']
```

Al iniciar:
1. `__bootstrap__.py` recorre `_DLL_SUBDIRS`.
2. Verifica que cada ruta esté estrictamente dentro de `VENDOR_ROOT` (evita el secuestro de DLL mediante symlinks externos).
3. Invoca `os.add_dll_directory()` y conserva el handle resultante en la colección global `_DLL_HANDLES` para evitar que el recolector de basura lo libere.

---

## 5. Ejecutables CLI (`vnma exec`)

Cuando los paquetes declaran scripts de consola (p. ej. `pytest`, `black`, `my-tool`):
* `vnma` genera scripts wrapper ejecutables en `vendor/.vnma_meta/.bin/`.
* Los wrappers configuran `PYTHONPATH` y lanzan la herramienta con el intérprete de Python del host.

Para invocar una herramienta instalada:

```bash
vnma exec my-tool --help
# o directamente en Windows:
.\vendor\.vnma_meta\.bin\my-tool.cmd --help
```
