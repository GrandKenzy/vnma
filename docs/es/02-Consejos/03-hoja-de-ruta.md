# Hoja de ruta

Este documento describe las capacidades completadas en versiones recientes y las mejoras de arquitectura futuras que se consideran para `vnma`.

---

## 1. Implementado recientemente

### v0.3.2

* **Dependencias anidadas:** las dependencias declaradas por paquetes Git y locales se resuelven junto con el manifiesto raíz, con deduplicación de diamantes y orden de instalación topológico.
* **`vnma insert-import`:** agrega el import del bootstrap a un script de entrada para que se ejecute con `python` directamente.

### v0.3.0

* **Poda de huérfanos (`vnma prune`):** identifica y elimina los paquetes de `vendor/` que ya no están referenciados por `vnma.toml` ni por dependencias activas.
* **Modo offline (`--offline`):** permite restaurar dependencias estrictamente desde cachés locales de wheels sin contactar redes externas.
* **Preparación transaccional y rollback:** preparación en carpetas vendor aisladas con journals de recuperación para garantizar que las instalaciones fallidas nunca corrompan el proyecto.
* **Resolvedor con backtracking acotado:** evalúa grafos de dependencias transitivas y resuelve conflictos de versiones de forma limpia.

---

## 2. Planeado y en consideración

### A. Streaming de metadatos PEP 658
Descargar los archivos `.metadata` de los wheels directamente desde PyPI en lugar de descargar los archivos `.whl` completos durante la inspección de dependencias, acelerando de forma significativa la resolución inicial en conexiones lentas.

### B. Generación aislada de stubs de tipos (`vnma stubs generate`)
Generar archivos de stubs de tipos `.pyi` para extensiones C/C++ compiladas (`.pyd` / `.so`) introspeccionándolas en un subproceso aislado, mejorando el autocompletado y la verificación de tipos en VS Code (Pylance) y PyCharm.

### C. AST Shading automatizado (`--shaded`)
Para bibliotecas de Python puro con conflictos de versiones inevitables en árboles de dependencias complejos, explorar la reescritura de los nodos `ast.Import` y `ast.ImportFrom` para reubicar los paquetes en conflicto bajo prefijos de espacio de nombres aislados.
