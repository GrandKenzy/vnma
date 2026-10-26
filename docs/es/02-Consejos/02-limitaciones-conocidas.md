# Limitaciones conocidas

Este documento describe las limitaciones estructurales y de diseño inherentes al modelo de ejecución de Python y a la implementación actual de `vnma`.

---

## 1. Espacio de nombres plano en runtime (`sys.modules`)

A diferencia de ecosistemas como Node.js (npm), que permiten jerarquías de módulos anidadas mediante resolución relativa de archivos, CPython usa un único diccionario global (`sys.modules`) para todos los módulos importados en un proceso.

* **Impacto:** dos versiones mutuamente excluyentes de la misma biblioteca (p. ej. `urllib3<2.0.0` y `urllib3>=2.0.0`) no pueden importarse a la vez en el mismo proceso de Python bajo el mismo nombre sin shading del código fuente o alteración de nombres de espacios de nombres.
* **Comportamiento actual:** `vnma` detecta esta condición durante la resolución del grafo de dependencias y lanza un `DependencyConflictError` en lugar de escribir un estado ambiguo o corrupto en `vendor/`.

---

## 2. Colisiones de nombres de bibliotecas compartidas (DLL/SO)

En Windows y Linux, el enlazador dinámico asocia una biblioteca compartida por su nombre de archivo base en el espacio de direcciones del proceso.

* **Impacto:** si el Paquete A incluye `zlib.dll` (v1.2.8) y el Paquete B incluye `zlib.dll` (v1.3.1), el cargador del sistema operativo se enlazará con la DLL que se cargue primero. Si la compatibilidad ABI diverge, pueden producirse violaciones de memoria.
* **Comportamiento actual:** `vnma` calcula hashes SHA256 de todas las DLL y registra advertencias explícitas de colisión cuando binarios distintos comparten el mismo nombre de archivo.

---

## 3. Paquetes con rutas de runtime no estándar

Ciertos paquetes de Python heredados inspeccionan `site-packages` en tiempo de ejecución o asumen que residen directamente dentro de `sys.prefix`.

* **Impacto:** aunque la mayoría de los paquetes modernos usan `__file__`, `importlib.resources` o `importlib.metadata` (que funcionan sin problemas con `vnma`), los paquetes que comprueban de forma fija `sys.prefix` o `site.USER_BASE` pueden requerir configuración explícita en `vnma.toml`.

---

## 4. Optimización de red PEP 658

PyPI soporta las descargas de metadatos básicos PEP 658 (obtener pequeños archivos `.metadata` en lugar de wheels completos durante la resolución de dependencias). `vnma` actualmente resuelve los requisitos inspeccionando los metadatos de los lanzamientos mediante la API JSON de PyPI y descargando los wheels a la caché. El streaming completo de la Simple API de PEP 658 está previsto para próximas versiones.

---

## 5. El mismo paquete declarado desde fuentes distintas

Cuando el mismo paquete lo declaran el manifiesto raíz y una dependencia, o dos dependencias, con refs de Git o rutas distintas:

* **Impacto:** solo puede instalarse una fuente en `vendor/`.
* **Comportamiento actual:** gana la declaración raíz. Entre dos declaraciones no raíz, se usa la primera descubierta. La diferencia no se reporta. Consulta [Dependencias anidadas](../01-Uso/06-dependencias-anidadas.md#4-precedencia).
