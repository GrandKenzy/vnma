# Visión de la comunidad y aspiraciones de adopción

Este documento reflexiona sobre el estado actual de la gestión de dependencias en Python y la filosofía que guía a `vnma`.

---

## 1. El contexto: el paradigma del virtualenv

Durante más de dos décadas, el estándar de la comunidad de Python para aislar aplicaciones ha sido el entorno virtual (`venv` / `virtualenv`). Al crear un directorio con una copia o symlink del ejecutable de Python junto a un directorio `site-packages` aislado, los desarrolladores pueden instalar bibliotecas sin permisos de administrador ni conflictos con los paquetes del sistema.

Este modelo resolvió el aislamiento de paquetes en su momento, pero introduce compromisos concretos:
* **Huella y redundancia:** replicar los binarios del intérprete de Python, los scripts y las herramientas base en cada proyecto consume almacenamiento y aumenta la latencia de inicialización.
* **No portabilidad:** los entornos virtuales fijan rutas absolutas en las cabeceras de scripts (`#!...`) y en los archivos de configuración (`pyvenv.cfg`), por lo que no son reubicables ni exportables entre ubicaciones del sistema de archivos.
* **Fragmentación de herramientas:** activar y desactivar entornos introduce fricción cognitiva en multiplexores de terminal, scripts de shell, runners de CI y configuraciones de IDE.

---

## 2. La alternativa del vendoring

Lenguajes como Go, Rust y JavaScript (con herramientas como pnpm, yarn zero-installs y el vendoring de Go) han demostrado las ventajas ergonómicas del almacenamiento de dependencias local al proyecto:
* Las dependencias residen limpiamente dentro del espacio de trabajo.
* El ejecutable de Python del sistema o del contenedor se reutiliza directamente sin mutación.
* Compartir un proyecto solo requiere compartir las definiciones de código fuente; las dependencias se restauran de forma determinista en segundos.

`vnma` busca ofrecer este flujo de forma nativa a los desarrolladores de Python. Combinando:
1. Extracción de distribuciones wheel conforme a los estándares,
2. Saneamiento hermético de rutas en runtime,
3. Registro determinista de DLL en sistemas operativos modernos, y
4. Archivos de configuración explícitos y de cero magia (`vnma_config.toml`),

`vnma` pretende demostrar que el vendoring a nivel de aplicación en Python no solo es viable, sino que puede ser robusto, predecible y limpio.

---

## 3. Aspiraciones de adopción en el ecosistema Python

Aunque los entornos virtuales seguirán siendo la opción por defecto en muchos flujos de trabajo, esperamos que `vnma` aporte una alternativa viable y ligera para:
* **Herramientas CLI y aplicaciones de escritorio:** donde las distribuciones autocontenidas y reubicables simplifican el empaquetado.
* **Desarrollo de videojuegos y motores embebidos:** (p. ej. Pygame, Godot-Python, scripting de Blender) donde las dependencias binarias necesitan una carga directa y determinista.
* **Microservicios y serverless:** donde la latencia de arranque en frío y las capas de contenedor mínimas ofrecen beneficios de rendimiento tangibles.

Los comentarios, la experimentación de la comunidad y las pruebas en el mundo real de desarrolladores de Python son bienvenidos mientras `vnma` avanza por la Beta.
