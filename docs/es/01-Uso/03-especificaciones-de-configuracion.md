# Especificaciones de configuración

Este documento define el esquema y el comportamiento de `vnma.toml` (nivel de proyecto) y `vnma_config.toml` (nivel de paquete).

---

## 1. Configuración del proyecto (`vnma.toml`)

El `vnma.toml` raíz declara las dependencias del proyecto, los ajustes de vendor y las sobrescrituras específicas por paquete.

### Ejemplo completo

```toml
[project]
name = "my-application"
version = "0.1.0"

[dependencies]
# Restricciones estándar de PyPI:
colorama = "==0.4.6"
pygame-ce = ">=2.5.0, <2.6.0"

# Dependencia de directorio de código local:
my-internal-tool = { path = "./packages/my-internal-tool" }

# Dependencia de repositorio Git:
custom-fork = { git = "https://github.com/user/fork.git", branch = "main" }

[dev-dependencies]
pytest = ">=8.0.0"

[tool.vnma]
vendor_dir = "vendor"
ide_integration = ["vscode", "pycharm"]

# Sobrescrituras explícitas para paquetes de terceros:
[package.unusual-package]
dll_directories = ["unusual_package/libs"]
entry_points = { run-tool = "unusual_package.cli:run" }
```

### Campos

* **`[project]`**: metadatos básicos del proyecto (`name`, `version`).
* **`[dependencies]`**: mapa de nombres de paquete a restricciones de versión, rutas del sistema de archivos o repositorios Git.
* **`[tool.vnma]`**:
  * `vendor_dir`: nombre del directorio de vendoring (`vendor` por defecto; se ajusta automáticamente a `vendor_vnma` si `vendor/` ya está ocupado).
  * `ide_integration`: lista de IDE a sincronizar (`["vscode", "pycharm"]`).
* **`[package.<name>]`**: sobrescrituras aplicadas a paquetes específicos durante la instalación.

---

## 2. Configuración a nivel de paquete (`vnma_config.toml`)

`vnma_config.toml` es un manifiesto explícito y opcional que se coloca en el **directorio raíz** de tu biblioteca (o repositorio). Su propósito es **eliminar las suposiciones heurísticas ("cero magia")** cuando `vnma` construye e instala paquetes desde repositorios de GitHub, directorios de código locales o subproyectos de un monorepo.

Cuando existe `vnma_config.toml`, `vnma` da prioridad a sus declaraciones sobre las inspecciones automáticas del sistema de archivos.

---

### Esquema completo

```toml
[package]
name = "my-library"      # Identificador de distribución; puede contener guiones
package = "my_library"  # Nombre de import de Python: import my_library
version = "0.1.0"
type = "pure-python"  # "pure-python" | "native" | "mixed"

[runtime]
# Rutas relativas dentro del paquete que contienen bibliotecas dinámicas (.dll, .so, .dylib)
# vnma las registra automáticamente con os.add_dll_directory() en Windows al ejecutar:
dll_directories = [
    "my_library/libs",
    "my_library/vendor_bin",
]

# Fuerza el aislamiento hermético al cargar este paquete (filtra site-packages externos):
hermetic = true

[exports]
# Directorios de módulos de nivel superior a exponer en sys.path:
modules = ["my_library"]

# Puntos de entrada de línea de comandos expuestos como wrappers ejecutables en vendor/.bin/:
entry_points = {
    my-tool = "my_library.cli:main",
    runner = "my_library.__main__:main"
}
```

---

### Referencia de campos

| Sección | Campo | Tipo | Descripción |
| :--- | :--- | :--- | :--- |
| `[package]` | `name` | string | Identificador de distribución (normalizado según PEP 503). No tiene que coincidir con el nombre del módulo importado. |
| `[package]` | `package` | string | **Nombre de import oficial de Python**, p. ej. `my_lib` cuando la distribución se llama `my-lib-framework`. Debe usar identificadores de Python válidos separados por puntos. |
| `[package]` | `packname` | string | Alias heredado de `package` (soportado para manifiestos existentes). `package` tiene prioridad si ambos están definidos. |
| `[package]` | `version` | string | Versión de lanzamiento del paquete (p. ej. `"1.0.0"`). Reemplaza el versionado de respaldo. |
| `[package]` | `type` | string | Clasificación del paquete: `"pure-python"` (por defecto), `"native"` o `"mixed"`. |
| `[runtime]` | `dll_directories` | lista de strings | Subdirectorios con objetos compartidos nativos (`.dll`, `.so`, `.dylib`). Se inyectan en `_DLL_SUBDIRS` de `__bootstrap__.py`. |
| `[runtime]` | `hermetic` | boolean | Por defecto `true`. Si está activo, impide el respaldo en tiempo de ejecución al `site-packages` global de Python. |
| `[exports]` | `modules` | lista de strings | Paquetes o módulos raíz de Python exportados por esta distribución. |
| `[exports]` | `entry_points` | tabla / mapa | Mapa de nombre de binario a callable de Python `module.submodule:function`. Los wrappers se escriben en `.bin/`. |
| `[dependencies]` | *nombre* | string / tabla | Dependencias de este paquete: una restricción de PyPI, `{ git = ..., branch = ... }` o `{ path = ... }`. Se instalan junto con el paquete (consulta [Dependencias anidadas](06-dependencias-anidadas.md)). |

---

### Nombre de distribución vs. nombre de import

Un nombre de distribución puede diferir del nombre que se importa. Por ejemplo, un manifiesto puede usar un nombre de distribución como `my-lib-framework2.0.0Beta`, el campo heredado `packname = "my_lib"`, `[exports] modules = ["my_lib"]` y un punto de entrada para `my_lib.__main__`. VNMA lo sigue aceptando sin cambios. Los manifiestos nuevos deberían expresar el mismo contrato de forma explícita:

```toml
[package]
name = "my-lib-framework2.0.0Beta"
package = "my_lib"
version = "2.0.0b1"
type = "pure-python"

[runtime]
dll_directories = []
hermetic = true

[exports]
modules = ["my_lib"]

[exports.entry_points]
my-lib = "my_lib.__main__:main"
```

`name` sigue siendo la identidad de dependencia/distribución que usan el manifiesto y la resolución de VNMA; `package` es la identidad de import de Python, validada contra los módulos del wheel instalado. No es un renombrado de `my_lib` al nombre de distribución.

Las dependencias locales editables (`{ path = "...", editable = true }`) y las dependencias de rama de Git (`{ git = "...", branch = "main" }`) están soportadas en el manifiesto raíz.

### Instalación atómica en 0.3.0

`vnma install`, `update`, `link` y `reload` preparan sus operaciones sobre vendor en una carpeta hermana temporal y publican el árbol vendor completo solo si todo sale bien. La eliminación de paquetes y `prune` desde la CLI también preparan las modificaciones. Los comandos fallidos restauran el vendor, la configuración del proyecto y el lockfile anteriores. Un journal permite la recuperación tras la caída de un proceso, con un bloqueo exclusivo contra mutaciones concurrentes. Los wrappers de CLI generados usan rutas seguras ante reubicación.

Limitaciones: la preparación por copia del árbol completo puede requerir espacio extra en disco (aproximadamente otro árbol vendor), y en Windows los dos renombrados son **recuperables pero no una primitiva atómica de intercambio de directorios**. La purga genérica de todo el espacio de trabajo `uninstall --all` sigue siendo una operación destructiva explícita, no una transacción reversible.

---

### Casos de uso reales

#### Caso A: biblioteca de Python puro con herramientas CLI
Si tu biblioteca de GitHub ofrece una herramienta de línea de comandos:

```toml
[package]
name = "devkit"
version = "1.2.0"
type = "pure-python"

[exports]
entry_points = { devkit = "devkit.cli:main" }
```

Al instalar con `vnma install git+https://github.com/org/devkit.git@main`, `vnma`:
1. Compila el paquete en `vendor/devkit/`.
2. Genera automáticamente `vendor/.vnma_meta/.bin/devkit.cmd` (y `.bat`).
3. Permite ejecutar `vnma exec devkit --help` de inmediato.

---

#### Caso B: biblioteca con binarios nativos compilados (C / C++ / Rust / SDL2)
Si tu biblioteca incluye extensiones C compiladas o DLL de terceros:

```toml
[package]
name = "fast-engine"
version = "2.0.0"
type = "native"

[runtime]
dll_directories = ["fast_engine/native_libs"]
```

Al instalarla, `vnma`:
1. Omite el escaneo heurístico de extensiones binarias.
2. Inyecta `"fast_engine/native_libs"` en el registro estático de DLL de complejidad $O(1)$ de `vendor/__bootstrap__.py`.
3. Garantiza que las llamadas a la API Win32 de Windows (`os.add_dll_directory`) mantengan los handles de las DLL de forma persistente en memoria.

---

### Jerarquía de precedencia

Para determinar cómo se comporta un paquete, `vnma` resuelve las configuraciones en este orden estricto:

```text
1. Sobrescrituras del proyecto   ([package.<name>] en el vnma.toml raíz)
             ↓
2. Manifiesto del paquete        (vnma_config.toml en el repositorio de la biblioteca)
             ↓
3. Estándares PEP 517 / Wheel    (.dist-info/entry_points.txt, METADATA, RECORD)
             ↓
4. Heurísticas automáticas       (escáneres de extensión de archivo: .pyd, .so, .dll)
```
