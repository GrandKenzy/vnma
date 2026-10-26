# Primeros pasos con VNMA

Este documento cubre la instalación, la inicialización de un proyecto y la estructura de directorios que gestiona `vnma`.

---

## 1. Requisitos del sistema

* Python 3.11, 3.12, 3.13 o 3.14.
* Sistema operativo: Windows 10/11, Linux (x86_64, aarch64) o macOS.
* Los binarios estándar `pip` y `git` disponibles en el `PATH`.

---

## 2. Instalación

Instala `vnma` en tu sistema o en el entorno de usuario activo:

```bash
# Clona el repositorio e instala en modo editable:
git clone https://github.com/GrandKenzy/vnma.git
cd vnma
pip install -e .
```

Verifica que el ejecutable de la CLI esté disponible:

```bash
vnma --help
```

---

## 3. Inicialización del proyecto

Para preparar un directorio de proyecto, nuevo o existente, para el vendoring:

```bash
cd my_project
vnma init
```

El comando `vnma init` realiza los siguientes pasos automáticos:

1. **Archivo de manifiesto:** genera `vnma.toml` si no existe ni `vnma.toml` ni `pyproject.toml`.
2. **Directorio vendor:** crea `vendor/` (o `vendor_vnma/` si `vendor/` ya está ocupado por archivos que no son de vnma).
3. **Cargador de runtime:** genera `vendor/__bootstrap__.py` y `vendor/__init__.py`.
4. **Hook de subprocesos:** crea `vendor/.vnma_meta/site/sitecustomize.py`.
5. **Reglas de Git:** agrega patrones a `.gitignore` para que los paquetes vendoreados no entren al control de versiones.
6. **Configuración de IDE:** inyecta rutas de búsqueda en `.vscode/settings.json`, `.idea/*.iml` y `.env`.
7. **Lockfile:** inicializa `vnma.lock`.

### 3.1 Generar una configuración limpia (`vnma generate`)

Si solo quieres generar un archivo de configuración vacío sin ejecutar la inicialización completa del entorno:

```bash
# Genera un vnma.toml vacío para el proyecto actual (versión 1.0.0):
vnma generate

# O genera un manifiesto de paquete (vnma_config.toml) para bibliotecas/repositorios:
vnma generate --package
```

* Opciones:
  * `-f`, `--force`: sobrescribe la configuración existente.
  * `-p`, `--package`, `--lib`: genera el manifiesto de biblioteca (`vnma_config.toml`) en lugar del archivo de proyecto (`vnma.toml`).

---

## 4. Estructura de proyecto gestionada

Después de ejecutar `vnma init` e instalar paquetes, tu espacio de trabajo tendrá esta organización:

```text
my_project/
├── .env                       # Definición de PYTHONPATH para ejecutar desde el IDE
├── .gitignore                 # Ignora automáticamente los artefactos de vendor
├── .vscode/
│   └── settings.json          # extraPaths configurado para Pylance/Jedi
├── vendor/                    # Paquetes vendoreados locales
│   ├── .vnma_meta/
│   │   ├── .bin/              # Wrappers de scripts generados (lanzadores de CLI)
│   │   ├── site/              # sitecustomize.py para inyección en subprocesos
│   │   ├── manifest.json      # Manifiesto criptográfico de archivos por paquete
│   │   └── python_version     # Versión de Python registrada al construir
│   ├── __bootstrap__.py       # Cargador O(1) de rutas y directorios de DLL
│   ├── __init__.py            # Punto de entrada que importa el bootstrap
│   └── <paquetes>/            # Paquetes de Python extraídos y módulos compilados
├── vnma.toml                  # Especificaciones declarativas de dependencias
├── vnma.lock                  # Lockfile determinista de versiones y fuentes
└── main.py                    # Punto de entrada de tu aplicación
```
