# FIX — Inserción segura del bootstrap de VNMA

**Estado:** pendiente de implementación  
**Componente:** `vnma/cli.py` — `cmd_insert_import()`  
**Comando:** `vnma insert-import [target]`

## Problema confirmado

La implementación actual inserta `import <vendor>.__bootstrap__  # From VNMA.` al inicio del archivo (salvo shebang/codificación), sin detectar declaraciones `from __future__ import annotations`. Esto genera un `SyntaxError` si el import del bootstrap queda antes de un `__future__` válido. Además, busca la subcadena `__bootstrap__` en todo el texto para decidir si ya existe el import: comentarios, cadenas y menciones de otros módulos producen falsos positivos.

## Regla obligatoria de ubicación

El bootstrap **debe ser el primer import ordinario y la primera sentencia ejecutable permitida**, excepto cuando haya declaraciones `from __future__ import ...` válidas. Respetar el encabezado que Python exige:

1. Conservar shebang y declaración de codificación PEP 263 en sus posiciones legales (líneas 1 o 2).
2. Conservar comentarios iniciales, líneas en blanco y docstring de módulo, si existe.
3. Detectar **todas** las declaraciones `from __future__ import ...` (incluida `annotations`), incluso si son multilínea; insertar el bootstrap **después de la última**, nunca antes.
4. Si no hay imports `__future__`, insertar el bootstrap al comienzo de las sentencias ordinarias, **después de la docstring de módulo** si existe.
5. Nunca insertarlo dentro de una docstring, un comentario, un bloque o una expresión multilínea.
6. Si el archivo tiene un `__future__` mal ubicado o sintaxis inválida, informar el error sin reescribir silenciosamente el archivo.

**Nota:** «primera línea sí o sí» se entiende como *primera posición legal para un import ordinario*. Colocarlo literalmente en la línea 1 rompería archivos con shebang, encoding, docstring o `__future__`. La regla también cubre otros imports `__future__`, no solo `annotations`.

### Ejemplo con annotations

**Entrada:**
```python
"""Módulo de ejemplo."""
from __future__ import annotations

def main() -> None:
    pass
```

**Salida:**
```python
"""Módulo de ejemplo."""
from __future__ import annotations
import vendor.__bootstrap__  # From VNMA.

def main() -> None:
    pass
```

### Ejemplo sin future

**Entrada:**
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entrada de la aplicación."""
import os
```

**Salida:**
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entrada de la aplicación."""
import vendor.__bootstrap__  # From VNMA.
import os
```

## Implementación recomendada

- Usar `ast.parse` para identificar la docstring y los nodos `ast.ImportFrom` con `module == "__future__"`; emplear `lineno`/`end_lineno` para ubicar la inserción sin reconstruir ni reformatear el resto del archivo.
- Validar que los imports `__future__` sean legales. En caso de duda, compilar el texto original antes de modificarlo; verificar también el resultado generado.
- Detectar imports existentes con AST: `ast.Import` cuyo alias tenga `name == "<vendor>.__bootstrap__"`; **no** usar búsquedas de subcadenas. Comentarios y strings que mencionan `__bootstrap__` no cuentan.
- Preservar el nombre configurado de vendor, BOM UTF-8 cuando exista y el estilo de salto de línea (LF/CRLF); evitar cambios innecesarios.
- Escritura segura: generar y validar el contenido completo antes de reemplazar el archivo; usar un archivo temporal y reemplazo atómico cuando sea viable.
- Mantener idempotencia: ejecutar dos veces no debe duplicar el import ni alterar el archivo en la segunda ejecución.

## Pruebas de regresión requeridas

- Archivo vacío y archivo inexistente.
- Import ordinario al inicio: bootstrap antes del primer import.
- `from __future__ import annotations`: bootstrap inmediatamente después.
- Múltiples imports `__future__`, incluidos imports multilínea.
- Shebang + codificación + docstring + `__future__`.
- Docstring multilínea que contiene el texto `from __future__` (no debe confundirse con una declaración real).
- Comentarios y strings que contienen `__bootstrap__` (no deben bloquear la inserción).
- Bootstrap ya importado (no debe duplicarse).
- CRLF y BOM UTF-8.
- Código inválido: no sobrescribir el original.
- Verificar con `compile(..., filename, "exec")` el código generado y comparar bytes en la segunda ejecución.

## Criterios de aceptación

1. Todo archivo Python válido sigue siendo sintácticamente válido después de insertar el bootstrap.
2. El bootstrap aparece exactamente una vez y antes de cualquier import ordinario o sentencia ejecutable, respetando las excepciones legales de Python.
3. Todas las declaraciones `__future__` permanecen antes del bootstrap.
4. El comando es idempotente y no confunde texto incidental con imports.
5. Los casos anteriores quedan cubiertos por pruebas automatizadas.

> Alcance de este archivo: especificación de corrección. **No modifica aún el código de VNMA.**
