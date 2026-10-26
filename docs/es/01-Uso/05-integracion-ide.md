# Integración con IDE

`vnma` configura automáticamente Visual Studio Code y JetBrains PyCharm para que el autocompletado, el linting, la inferencia de tipos y la navegación de símbolos funcionen sin pasos extra con las bibliotecas vendoreadas.

---

## 1. Visual Studio Code

### Configuración: `.vscode/settings.json`

Durante `vnma init`, `vnma install` o `vnma sync-ide`, `vnma` actualiza `.vscode/settings.json`:

```json
{
    "python.analysis.extraPaths": [
        "./vendor"
    ],
    "python.autoComplete.extraPaths": [
        "./vendor"
    ]
}
```

### Compatibilidad con JSONC

Los archivos de configuración de VS Code suelen contener comentarios en línea (`//`, `/* ... */`) y comas finales. `vnma` usa un prefiltro léxico para leer de forma segura JSON con comentarios (JSONC), de modo que las personalizaciones existentes del usuario no se sobrescriben ni se corrompen.

---

## 2. JetBrains PyCharm

### A. Archivo de entorno: `.env`

`vnma` crea o actualiza un `.env` en la raíz con:

```env
PYTHONPATH=./vendor
```

PyCharm lee los archivos `.env` automáticamente en las configuraciones de ejecución y en la consola de Python.

### B. Módulo del proyecto: `.idea/*.iml`

Si el directorio del proyecto contiene una carpeta `.idea`, `vnma` modifica el archivo de módulo (`.iml`) para registrar `vendor/` como carpeta de código fuente reconocida:

```xml
<content url="file://$MODULE_DIR$">
  <sourceFolder url="file://$MODULE_DIR$/vendor" isTestSource="false" />
</content>
```

---

## 3. Resincronización manual

Si los archivos de configuración del IDE se borran o se modifican externamente, ejecuta:

```bash
vnma sync-ide
```

Esto vuelve a aplicar los registros de rutas del IDE sin tocar los paquetes dentro de `vendor/`.
