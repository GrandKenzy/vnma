# Dependencias anidadas

Un paquete que instalas puede depender a su vez de otros paquetes, y varios paquetes pueden depender del mismo. Este documento explica cómo `vnma install` maneja esos casos.

---

## 1. El escenario

```text
app
├── shared-lib          (Git)
└── tool-lib            (ruta local)
    └── shared-lib      (Git, mismo repositorio)
```

`app` depende de `shared-lib` y de `tool-lib`, y `tool-lib` también depende de `shared-lib`. Ambos caminos llevan al mismo paquete, así que debe instalarse una sola vez y antes que `tool-lib`.

---

## 2. Declarar dependencias

Un paquete declara lo que necesita en su propio manifiesto. `vnma` lee el primero de estos que declare alguna dependencia:

| Orden | Archivo | Dónde se declaran las dependencias |
| :--- | :--- | :--- |
| 1 | `vnma.toml` | `[dependencies]` |
| 2 | `vnma_config.toml` | `[dependencies]` |
| 3 | `pyproject.toml` | `[project].dependencies` o `[tool.vnma.dependencies]` |

Las entradas usan las mismas formas que el manifiesto raíz:

```toml
# tool-lib/vnma_config.toml
[package]
name = "tool-lib"
version = "1.0.0"

[exports]
modules = ["tool_lib"]

[dependencies]
shared-lib = { git = "https://github.com/org/shared-lib.git", branch = "main" }
helper = ">=1.0.0"
local-utils = { path = "../local-utils" }
```

Los valores `path` relativos se resuelven desde el directorio del manifiesto que los declara.

El proyecto raíz declara sus propios paquetes como de costumbre:

```toml
# app/vnma.toml
[project]
name = "app"
version = "1.0.0"

[dependencies]
shared-lib = { git = "https://github.com/org/shared-lib.git", branch = "main" }
tool-lib = { path = "../tool-lib" }
```

---

## 3. Qué hace `vnma install`

```bash
cd app
vnma install
```

1. **Recopila** las dependencias raíz.
2. **Inspecciona** cada repositorio Git (clonado en `~/.vnma/cache/git/`) y cada ruta local en busca de las dependencias que declara, y las encola.
3. **Deduplica** por nombre de paquete normalizado. Un paquete alcanzado por varios caminos se procesa una sola vez.
4. **Resuelve** juntos todos los requisitos de PyPI reunidos de todos los niveles, de modo que las restricciones de versión de distintos paquetes se contrastan entre sí.
5. **Ordena** el resultado para que una dependencia se instale antes que los paquetes que la necesitan.
6. **Instala** cada paquete desde su fuente y escribe `vnma.lock`.

Cada repositorio Git o ruta local se visita una sola vez, por lo que las declaraciones circulares terminan.

---

## 4. Precedencia

Cuando el manifiesto raíz y una dependencia declaran el mismo paquete, **se usa la declaración raíz**. En el escenario anterior, la rama de Git declarada en `app/vnma.toml` se aplica aunque `tool-lib` indique otra.

Si la raíz no declara un paquete que solo necesitan las dependencias, se instala como dependencia transitiva.

> [!WARNING]
> Las diferencias entre declaraciones del mismo paquete (refs de Git o rutas distintas) no se reportan. Tampoco se concilian dos dependencias que declaran el mismo paquete desde fuentes distintas: se usa la primera descubierta. Declara el paquete en el manifiesto raíz cuando la fuente importe.

---

## 5. Fuentes que solo tienen un manifiesto

Un repositorio Git o directorio local no necesita `pyproject.toml` ni `setup.py`. Si solo tiene `vnma_config.toml` o `vnma.toml`, `vnma` construye un wheel estándar generando temporalmente los metadatos de construcción y eliminándolos después. El árbol de código fuente no se modifica.

Los módulos a empaquetar provienen de `[exports].modules` en `vnma_config.toml`. Si esa lista no existe, `vnma` empaqueta los directorios de nivel superior que contienen `__init__.py` y los archivos `.py` de nivel superior.

La construcción usa `pip wheel`, por lo que `setuptools` debe poder obtenerse en el entorno de construcción.

---

## 6. Lockfile

`vnma.lock` registra la fuente real de cada paquete instalado, incluidos los que no se declararon en el manifiesto raíz:

```json
{
  "packages": {
    "shared-lib": { "source": "git", "git_url": "https://github.com/org/shared-lib.git", "git_ref": "main" },
    "tool-lib": { "source": "local", "path": "/home/user/projects/tool-lib" }
  }
}
```

La restauración con `vnma install` usa estos registros.

---

## 7. Límites

* Solo puede existir una versión de un paquete en `vendor/`. Las restricciones de PyPI en conflicto lanzan un `DependencyConflictError` (consulta [Limitaciones conocidas](../02-Consejos/02-limitaciones-conocidas.md)).
* Los paquetes enlazados (`editable`) no se copian; sus propias dependencias se instalan en `vendor/`, como se describe en [Gestión de dependencias](02-gestion-de-dependencias.md#8-enlaces-de-desarrollo-vivos-vnma-link-vnma-unlink-vnma-reload).
