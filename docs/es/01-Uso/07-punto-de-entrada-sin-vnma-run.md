# Puntos de entrada sin `vnma run`

Por defecto, un script solo ve los paquetes de `vendor/` cuando se inicia con `vnma run`. Para una CLI o aplicación que ejecutas con frecuencia, eso es incómodo. `vnma insert-import` elimina esa necesidad.

---

## 1. El comando

```bash
# Usa el punto de entrada del proyecto (main.py, src/main.py, source/main.py, app.py):
vnma insert-import

# O indica el script:
vnma insert-import cli/entry.py
```

El comando inserta esta línea:

```python
import vendor.__bootstrap__  # From VNMA.
```

Si el proyecto usa otro directorio vendor (por ejemplo `vendor_vnma`), se usa ese nombre en lugar de `vendor`.

Después, ejecuta el script con normalidad:

```bash
python main.py
```

---

## 2. Comportamiento

| Situación | Resultado |
| :--- | :--- |
| El archivo no tiene el import del bootstrap | La línea se inserta al inicio. |
| El archivo empieza con un shebang (`#!`) y/o una declaración de codificación | La línea se inserta justo después. |
| El archivo ya hace referencia a `__bootstrap__` | No cambia nada. |
| El archivo no existe | Se crea con una plantilla mínima ejecutable. |
| No se indicó `target` y no se encontró un punto de entrada | Se crea `main.py` en la raíz del proyecto. |

Ejemplo del resultado para un script con shebang:

```python
#!/usr/bin/env python3
import vendor.__bootstrap__  # From VNMA.

from my_package.cli import main

if __name__ == "__main__":
    main()
```

> [!IMPORTANT]
> El import del bootstrap debe ejecutarse antes de cualquier import de un paquete vendoreado. `vnma insert-import` lo coloca al inicio por esa razón; mantenlo ahí.

---

## 3. Elegir cómo ejecutar

| Objetivo | Usa |
| :--- | :--- |
| Ejecutar tu propio script durante el desarrollo | `python main.py` después de `vnma insert-import`, o `vnma run main.py` |
| Ejecutar una CLI instalada desde una dependencia | `vnma exec <herramienta>` (consulta [Ejecución en runtime](04-ejecucion-en-runtime.md#5-ejecutables-cli-vnma-exec)) |
| Comprobar que los directorios enlazados existen antes de ejecutar | `vnma run` |

`vnma run` además define `PYTHONPATH` y `PYTHONNOUSERSITE=1` para el proceso hijo y verifica los directorios enlazados antes de iniciar. El import del bootstrap configura `sys.path` y los directorios de DLL de Windows desde dentro del proceso. Consulta [Ejecución en runtime](04-ejecucion-en-runtime.md) para los detalles de ambos.

---

## 4. Límites

* El comando solo busca en el archivo el texto `__bootstrap__`; cualquier aparición cuenta como un import existente.
* No crea scripts lanzadores para tu propio proyecto. Para tener un comando en el `PATH`, publica el proyecto como paquete o envuélvelo en un script propio.
