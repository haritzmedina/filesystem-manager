# Filesystem Manager (filesysman)

Analizador de espacio en disco ligero, estilo TreeSize.

- **Modo CLI** con argumentos: `filesysman C:\` o `filesysman /var/log`.
  Solo biblioteca estandar de Python.
- **Modo GUI** (PySide6/Qt6, tema oscuro/claro) al abrir sin argumentos
  (doble clic).
- Escaneo rapido con `os.scandir` + multihilo, tolerante a permisos denegados.
- Compilable a binario autonomo (Windows / Linux / macOS) con PyInstaller.
- Instalador Windows (Inno Setup) con accesos directos, PATH y desinstalador.

## Estructura del proyecto

```
filesystem-man/
├── src/
│   ├── __init__.py     # metadatos del paquete
│   ├── core.py         # motor de escaneo: os.scandir + threading
│   ├── cli.py          # vista de consola (carpetas que mas ocupan, %)
│   └── gui.py          # vista grafica PySide6/Qt6 (arbol + barras de %)
├── tests/
│   └── test_core.py    # pruebas unitarias del motor y formatos
├── assets/
│   └── app.ico         # icono de la aplicacion (usado por GUI e instalador)
├── main.py             # punto de entrada unificado CLI/GUI
├── build.py            # compilacion con PyInstaller
├── installer_win.iss   # instalador/desinstalador Inno Setup
├── requirements.txt    # dependencias (PySide6 para la GUI, dev/build)
└── README.md
```

## Requisitos

- Python 3.9+ (desarrollado con 3.12).
- **Modo GUI**: PySide6 (`pip install PySide6`). La CLI no necesita nada.
- Windows: para generar el instalador, Inno Setup 6.2+.

## Uso rapido (desde el codigo fuente)

```powershell
pip install -r requirements.txt     # solo para desarrollo/compilacion

python main.py C:\                  # modo CLI
python main.py C:\ -n 5             # CLI mostrando las 5 carpetas principales
python main.py --cli .              # fuerza CLI en el directorio actual
python main.py                      # modo GUI (sin argumentos)
python main.py --gui                # fuerza la GUI
```

## Modo CLI

```
filesysman [opciones] [RUTA]

RUTA                  Carpeta a analizar (por defecto: la actual)
-n, --top N           Carpetas mas grandes a mostrar (por defecto: 10)
-j, --jobs N          Hilos de escaneo (0 = automatico)
-q, --quiet           Oculta el progreso en vivo
--version             Muestra la version
--cli / --gui         Fuerza un modo concreto
```

Salida de ejemplo:

```
  Analizando: C:\Users\ana
  Total: 42.35 GB  (312.456 archivos, 8.902 carpetas)

  Carpetas que mas ocupan (10 de 8.902):
   1. ##############################-  96.4%     40.84 GB  AppData
   2. ##########--------------------  33.7%     14.28 GB  Documents
   ...
  Tiempo: 12.40 s
```

## Modo GUI

- Escribe o elige una carpeta (boton "Examinar...") y pulsa "Analizar".
- Interfaz moderna PySide6 (Qt6) con **tema oscuro por defecto** y boton
  para alternar a tema claro, e **icono propio** (assets/app.ico).
- **Arbol expandible estilo TreeSize**: el analisis inicial muestra la raiz,
  sus ficheros y carpetas directas; al **expandir** una carpeta su contenido
  se escanea bajo demanda en segundo plano (sin agotar memoria). Doble clic
  en una carpeta la expande/colapsa.
- La columna "% del total" muestra una **barra de progreso** por carpeta.
- Barra de estado con progreso en vivo y boton "Detener" para cancelar
  (interrumpe el escaneo y muestra los resultados parciales).
- Boton con **flecha hacia arriba** (icono) para volver a la carpeta padre.
- **Menu contextual** por carpeta: analizar, abrir en el explorador o
  copiar la ruta.
- Los permisos denegados se muestran como contador de errores, sin abortar.

## Pruebas unitarias (QA)

```powershell
python -m pytest tests -v
```

Cubre: formatos KB/MB/GB/TB, totales y conteos, arboles vacios, rutas
inexistentes, `PermissionError`, bucles de symlinks, cancelacion, progreso
y variantes de hilos (1, 2, 4).

## Compilacion de binarios (PyInstaller)

Ejecuta siempre **en el sistema operativo de destino** (PyInstaller no
compila de forma cruzada). Genera dos binarios del mismo codigo:

- `filesysman` (con consola) -> CLI desde la terminal.
- `filesysman-gui` (sin consola) -> GUI al hacer doble clic.

```powershell
pip install -r requirements.txt
python build.py                 # consola (onedir) + GUI (onefile) en dist/
python build.py --onefile       # consola tambien como un solo archivo
python build.py --clean         # borra build/ y dist/ antes de compilar
python build.py --name filesysman --icon assets\app.ico
```

### Windows

1. `python build.py` produce `dist\filesysman\` (con `filesysman.exe`) y
   `dist\filesysman-gui.exe`.
2. Pruebalo: `dist\filesysman\filesysman.exe C:\Users`.
3. Doble clic en `dist\filesysman-gui.exe` para la GUI.
4. Sigue con el instalador Inno Setup (abajo).

### Linux

1. `python build.py` produce `dist/filesysman/` y `dist/filesysman-gui`.
2. Instala globalmente (opcional):

```bash
sudo ln -s "$PWD/dist/filesysman/filesysman" /usr/local/bin/filesysman
chmod +x dist/filesysman/filesysman dist/filesysman-gui
```

3. Para un paquete instalable, genera un `.tar.gz` y, si lo deseas, un
   archivo `.desktop` que apunte a `filesysman-gui`. La GUI requiere
   `PySide6` presente en el sistema de compilacion (el binario generado la
   incluye empaquetada).

### macOS

1. `python build.py` produce `dist/filesysman` y `dist/filesysman-gui`
   (binario unico). Para obtener un bundle `.app`, compila la GUI con
   onedir:

```bash
python -m PyInstaller main.py --name filesysman-gui --windowed --onedir --paths .
```

2. Firma ad-hoc (Apple Silicon) y quita la cuarentena tras descargar:

```bash
codesign --force --deep -s - dist/filesysman-gui.app
xattr -cr dist/filesysman-gui.app
```

## Publicacion automatica (GitHub Actions)

El flujo `.github/workflows/release.yml` compila y publica paquetes para
**Windows, Linux y macOS** al pulsar un tag:

```powershell
git tag v1.0.1
git push origin v1.0.1
```

La accion crea una release en GitHub con:

| Plataforma | Artefactos |
| --- | --- |
| Windows | `Filesysman_Setup.exe` (instalador Inno), `filesysman-gui.exe` (portable), `filesysman-cli-win64.zip` |
| Linux | `filesysman-gui-linux64` (portable) y CLI en `filesysman-cli-linux64.tar.gz` |
| macOS (Intel/ARM) | `filesysman-gui-macos-x64.zip` y `...-macos-arm64.zip` (app bundle) + CLI comprimido |

- Cada SO se compila en su propio runner (PyInstaller no compila de forma cruzada).
- En Linux, el binario de la GUI requiere las librerias Qt del sistema
  (`libegl1 libgl1 libxkbcommon0 libxcb-cursor0`, etc.).
- En macOS el app bundle se firma ad-hoc (`codesign -s -`).

## Instalador Windows (Inno Setup)

Genera `Filesysman_Setup.exe`, que instala en `%ProgramFiles%\FilesystemManager`,
crea accesos directos (Menu de Inicio + Escritorio opcional), agrega el
directorio al **PATH del sistema** (para usar `filesysman` en CMD/PowerShell)
y registra un **desinstalador nativo** en "Agregar o quitar programas".

1. Instala [Inno Setup 6](https://jrsoftware.org/isdl.php).
2. Compila los binarios: `python build.py`.
3. Compila el instalador:

```powershell
iscc installer_win.iss
```

   (o abre `installer_win.iss` en el IDE de Inno y pulsa Compile).

4. El instalador queda en `dist\Filesysman_Setup.exe`.
5. **PATH**: abre una terminal nueva para ver el cambio (el instalador
   notifica a Windows, pero las terminales ya abiertas no se actualizan).
   Compruebalo con `filesysman --version`.
6. **Desinstalar**: "Agregar o quitar programas" > Filesystem Manager >
   Desinstalar (tambien quita el directorio del PATH).

## Solucion de problemas

| Problema | Solucion |
| --- | --- |
| Carpetas del sistema muestran errores | Ejecuta como administrador (CLI) o como admin (GUI). |
| El binario PyInstaller es marcado por el antivirus | Es un falso positivo comun; anade una exclusion o compila con `--onefile`. |
| `filesysman` no se reconoce tras instalar | Abre una terminal nueva o reinicia sesion. |
| GUI no arranca | `pip install PySide6` y vuelve a compilar (la CLI no lo necesita). |
| Escaneo muy lento en red | Reduce hilos con `-j 2`; no se siguen enlaces simbolicos a proposito. |
