# Ejemplo Aislado: Dependencia Anidada con Gram de GitHub

Este ejemplo demuestra y verifica el soporte de VNMA para dependencias en estructura diamante y anidadas en 2 niveles de profundidad utilizando el repositorio real de GitHub:
`https://github.com/GrandKenzy/Gram`

## Estructura de la prueba

```
examples/nested_gram/
├── subproject/                  # Proyecto intermedio (Profundidad 1)
│   ├── sub_parser.py           # Módulo que importa y usa gram
│   └── vnma_config.toml        # Declara dependencia a Gram de GitHub
│
├── main_project/                # Proyecto principal (Profundidad 0)
│   ├── main.py                 # Importa gram directamente y usa sub_parser
│   ├── vnma.toml               # Declara dependencias a Gram (GitHub) y subproject (local)
│   └── vnma.lock               # Lockfile generado automáticamente
│
└── run_example.py               # Script automatizado para verificar todo
```

## Dependencias declaradas

### `main_project/vnma.toml`:
```toml
[project]
name = "main-project"
version = "1.0.0"

[dependencies]
gram = { git = "https://github.com/GrandKenzy/Gram.git", branch = "main" }
sub-parser = { path = "../subproject" }
```

### `subproject/vnma_config.toml`:
```toml
[package]
name = "sub-parser"
version = "1.0.0"
type = "pure-python"

[exports]
modules = ["sub_parser"]

[dependencies]
gram = { git = "https://github.com/GrandKenzy/Gram.git", branch = "main" }
```

## Cómo ejecutar

Desde la raíz del repositorio:
```bash
python examples/nested_gram/run_example.py
```
O directamente dentro de `main_project`:
```bash
cd examples/nested_gram/main_project
python main.py
# o también:
python -m vnma run main.py
python -m vnma exec gram
```
