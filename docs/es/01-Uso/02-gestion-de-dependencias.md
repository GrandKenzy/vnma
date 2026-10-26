# Gestión de dependencias

`vnma` ofrece comandos para resolver, descargar, compilar, instalar y desinstalar paquetes desde distintas fuentes de distribución.

---

## 1. Instalar paquetes

### A. Desde PyPI

Para instalar un paquete y resolver su árbol de dependencias transitivas:

```bash
# Última versión compatible:
vnma install requests

# Versión fija:
vnma install colorama==0.4.6

# Atajo de versión con guion:
vnma install pygame-ce-2.5.8

# Rango de versiones:
vnma install "urllib3>=2.0.0,<3.0.0"
```

Durante la instalación, `vnma`:
1. Consulta la API JSON de PyPI y filtra las plataformas incompatibles y los wheels retirados (yanked).
2. Recorre el grafo de dependencias transitivas aplicando los marcadores de entorno PEP 508.
3. Descarga u obtiene el wheel de la caché local del usuario (`~/.vnma/cache/wheels/`).
4. Extrae en una sola pasada calculando hashes SHA256 y validando contra ataques Zip Slip.
5. Registra los archivos instalados en `manifest.json`.
6. Agrega la definición de la dependencia a `vnma.toml`.
7. Actualiza `vnma.lock`.

---

### B. Desde directorios locales (monorepos / código propietario)

Para vendorizar una biblioteca del mismo árbol o de un directorio hermano:

```bash
vnma install ./packages/my-internal-tool
# o ruta relativa:
vnma install ../shared-library
```

`vnma` compila el árbol de código local en un wheel aislado mediante PEP 517 antes de instalarlo. Si el directorio local contiene un `vnma_config.toml`, se respetan sus declaraciones explícitas (consulta [Especificaciones de configuración](03-especificaciones-de-configuracion.md#2-configuración-a-nivel-de-paquete-vnma_configtoml)).

En `vnma.toml` se registra como:

```toml
[dependencies]
my-internal-tool = { path = "./packages/my-internal-tool" }
```

---

### C. Desde repositorios Git remotos

Para instalar directamente desde un repositorio Git remoto:

```bash
vnma install git+https://github.com/psf/requests.git@main
```

`vnma` clona el repositorio en `~/.vnma/cache/git/`, construye un wheel en la caché y lo vendoriza en `vendor/`. Si el repositorio contiene un `vnma_config.toml`, se cargan automáticamente las rutas de DLL nativas y los puntos de entrada CLI que declara (consulta [Configuración a nivel de paquete](03-especificaciones-de-configuracion.md#2-configuración-a-nivel-de-paquete-vnma_configtoml)).

En `vnma.toml` se registra como:

```toml
[dependencies]
requests = { git = "https://github.com/psf/requests.git", branch = "main" }
```

Las dependencias que el repositorio declara para sí mismo también se resuelven e instalan; consulta [Dependencias anidadas](06-dependencias-anidadas.md).

---

## 2. Restaurar dependencias (flujo de equipo / CI)

Al clonar un proyecto que contiene `vnma.toml` y `vnma.lock`, el directorio `vendor/` no viene incluido en Git. Para restaurar todas las dependencias:

```bash
vnma install
# o explícitamente:
vnma install .
```

`vnma` lee `vnma.toml`, resuelve las fuentes (PyPI, rutas locales y repositorios Git) y puebla `vendor/` de forma idéntica.

---

## 3. Desinstalar paquetes y purgar el espacio de trabajo

### Desinstalar un paquete individual
Para quitar un paquete:

```bash
# Quita los archivos del paquete de vendor/ (conserva la declaración en vnma.toml para futuras instalaciones):
vnma uninstall colorama

# Quita el paquete de vendor/ Y lo elimina de vnma.toml:
vnma uninstall colorama --del
# o atajo:
vnma uninstall colorama -d
```

`vnma` elimina los archivos registrados en `manifest.json` para ese paquete. Los archivos compartidos que reclaman otros paquetes instalados (p. ej. en paquetes de namespace) se conservan, y los directorios padre vacíos se podan. Con `--del` (`-d`), la definición de la dependencia también se borra de `vnma.toml`. En ambos casos se sincroniza `vnma.lock`.

### Purgar todo el soporte de VNMA de un proyecto
Cuando se invoca `vnma uninstall` sin indicar un paquete, purga por completo todos los directorios vendor y archivos de soporte de VNMA de la carpeta, dejándola limpia como si VNMA nunca se hubiera inicializado:

```bash
# Purga interactiva de todo el soporte de VNMA en el directorio actual:
vnma uninstall

# Confirmación no interactiva (CI / automatización):
vnma uninstall -y

# Purga vendor y lockfiles pero conserva vnma.toml:
vnma uninstall --keep-config -y
```

Qué limpia `vnma uninstall`:
* Elimina `vendor/` (o `vendor_vnma/`) con todos los paquetes vendoreados y metadatos.
* Elimina `vnma.lock`.
* Elimina `vnma.toml` (salvo que se indique `--keep-config`).
* Limpia las rutas de VNMA de `.vscode/settings.json` (elimina `.vscode/` si queda vacío).
* Limpia el `PYTHONPATH` de VNMA de `.env` (elimina `.env` si queda vacío).
* Limpia los bloques de ignorados de VNMA de `.gitignore` (elimina `.gitignore` si queda vacío).
* Nunca desinstala la herramienta CLI global `vnma` ni toca archivos de código del usuario (p. ej. `main.py`).

---

## 4. Listar paquetes instalados

Para inspeccionar el directorio vendor actual:

```bash
vnma list
```

Formato de salida:

```text
[vnma] Packages installed in 'vendor':
Package                   Version         Native    
----------------------------------------------------
colorama                  0.4.6           No        
my-internal-tool          1.0.0           No        
pygame-ce                 2.5.8           Yes       
requests                  2.34.2          No        
```

---

## 5. Podar paquetes huérfanos (`vnma prune`)

Al quitar o modificar dependencias directamente en `vnma.toml`, los paquetes transitivos que ya no necesita ninguna dependencia raíz permanecen en `vendor/`.

Para inspeccionar o eliminar paquetes huérfanos:

```bash
# Vista previa de huérfanos sin modificar nada:
vnma prune --dry-run

# Confirmación interactiva de la poda:
vnma prune

# Confirmación no interactiva (CI / automatización):
vnma prune --yes
```

`vnma prune`:
1. Construye la clausura de alcanzabilidad desde todos los paquetes declarados en `vnma.toml`.
2. Identifica los paquetes presentes en `manifest.json` que están desconectados del grafo alcanzable.
3. Elimina los archivos huérfanos conservando los archivos de namespace compartidos.
4. Regenera `__bootstrap__.py` y sincroniza `vnma.lock`.

---

## 6. Modo offline y repositorios locales

En entornos aislados de red, pipelines de CI seguros o sin conexión a internet, las dependencias pueden restaurarse estrictamente desde wheels descargados previamente:

```bash
# Resuelve e instala estrictamente desde la caché de wheels del usuario (~/.vnma/cache/wheels/):
vnma install --offline

# Indica un directorio local adicional con archivos wheel:
vnma install --offline --find-links ./wheelhouse
```

Si un paquete no puede satisfacerse con los wheels locales disponibles, `vnma` lanza un error indicando el paquete y la restricción faltantes, sin iniciar peticiones de red.

---

## 7. Actualizar dependencias (`vnma update`)

Para actualizar las dependencias a sus últimas versiones compatibles sin modificar las restricciones fijadas por el usuario:

```bash
# Actualiza todas las dependencias (PyPI y Git):
vnma update

# Actualiza solo los paquetes de PyPI:
vnma update --pip

# Actualiza solo los paquetes de Git (obtiene los últimos commits de los repositorios remotos):
vnma update --git

# Actualiza un paquete individual y sus transitivas:
vnma update requests
```

### Protección de paquetes fijados
Siguiendo la semántica estándar de los lockfiles, `vnma update` respeta los pines explícitos del usuario:
* Los **paquetes de PyPI** fijados con `==` (p. ej. `colorama = "==0.4.6"`) se conservan y se omiten en silencio, sin errores.
* Los **paquetes de Git** bloqueados a un hash de `commit` o `tag` inmutable se conservan y se omiten en silencio, sin errores.
* Los paquetes con restricciones flotantes (p. ej. `*`, `>=2.0.0`, `~=1.5.0`) o ramas de Git flotantes (`main`) se actualizan a su última versión.

Las actualizaciones son transaccionales: los archivos obsoletos de versiones anteriores del paquete se eliminan de `vendor/` sin tocar los paquetes de namespace compartidos, y `vnma.lock` se actualiza de forma determinista.

---

## 8. Enlaces de desarrollo vivos (`vnma link`, `vnma unlink`, `vnma reload`)

Al desarrollar una biblioteca (como un SDK interno o un framework) junto con una aplicación que la consume, reconstruir e instalar wheels en cada edición ralentiza la iteración.

`vnma` ofrece enlaces de desarrollo vivos sin copia:

### A. Enlazar un árbol de código local (`vnma link`)

```bash
vnma link ../my-library
# o ruta relativa:
vnma link ./packages/my-internal-tool
# o ruta relativa al usuario:
vnma link ~/projects/my-library
```

1. **Sin copia y portable entre sesiones:** no copia archivos a `vendor/`. Serializa automáticamente las rutas con tokens independientes del usuario (`~/...`), de modo que la configuración funciona entre distintos desarrolladores y sesiones sin nombres de usuario fijos.
2. **Reflejo instantáneo:** los cambios en el código de la biblioteca enlazada se aplican de inmediato en la siguiente ejecución (`vnma run` o `import vendor`).
3. **Resolución de dependencias:** inspecciona `vnma_config.toml` o `pyproject.toml` en el directorio destino y resuelve e instala automáticamente en `vendor/` las dependencias declaradas.
4. **Autocompletado en el IDE:** inyecta el directorio destino en `.vscode/settings.json` (`${userHome}/...` en `python.analysis.extraPaths`) y en `.env`.

En `vnma.toml` se almacena de forma portable como:
```toml
[dependencies]
my-library = { path = "../my-library", editable = true }
```

---

### B. Desenlazar un paquete (`vnma unlink`)

Para quitar un paquete enlazado:

```bash
# Por nombre de paquete:
vnma unlink my-library

# O por ruta de directorio o token portable:
vnma unlink ../my-library
```

Esto elimina la dependencia de `vnma.toml`, borra su ruta de búsqueda de `__bootstrap__.py` y actualiza las configuraciones del IDE.

---

### C. Reconciliar y podar automáticamente (`vnma reload`)

Para verificar la integridad de todas las dependencias enlazadas, resolver los requisitos nuevos y podar automáticamente los paquetes que ya no se referencian:

```bash
vnma reload
```

* **Auditoría de integridad:** comprueba que todos los directorios enlazados existan. Si una carpeta se movió o se borró, se aborta con un cuadro de advertencia.
* **Poda automática:** si una biblioteca enlazada quitó una dependencia (o si la biblioteca se desenlazó), `vnma reload` detecta que ninguna parte del proyecto necesita ya ese paquete y lo elimina de `vendor/`.
* **Protección en `vnma run`:** antes de ejecutar cualquier script, `vnma run` verifica que todos los directorios enlazados existan y se detiene con un mensaje útil, en lugar de lanzar tracebacks de import confusos si falta alguno.
