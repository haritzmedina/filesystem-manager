"""Automatiza la compilacion de binarios con PyInstaller.

Genera dos ejecutables con el mismo codigo base (main.py decide el modo):
  - ``filesysman``        con consola:  para usar desde la terminal (CLI).
  - ``filesysman-gui``    sin consola:  para abrir la GUI con doble clic.

Uso:
  python build.py                 # consola (onedir) + GUI (onefile)
  python build.py --onefile       # consola tambien como un solo archivo
  python build.py --skip-gui      # solo la version de consola
  python build.py --clean         # limpia build/ y dist/ antes de compilar
  python build.py --name filesysman --icon assets/app.ico

Si existe assets/app.ico se usa como icono por defecto.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN_SCRIPT = ROOT / "main.py"
DEFAULT_NAME = "filesysman"


def _run(cmd) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def _pyinstaller(extra) -> None:
    _run([sys.executable, "-m", "PyInstaller", "--noconfirm"] + extra)


def _exe_suffix() -> str:
    return ".exe" if sys.platform == "win32" else ""


def build(
    name: str,
    console_mode: str,
    build_gui: bool,
    icon: Path | None,
    clean: bool,
) -> None:
    if clean:
        for folder in (ROOT / "build", ROOT / "dist"):
            if folder.exists():
                shutil.rmtree(folder)

    base = [
        str(MAIN_SCRIPT),
        "--paths",
        str(ROOT),
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT / "build"),
    ]
    common = []
    if icon:
        if sys.platform == "darwin":
            icns = icon.with_suffix(".icns")
            if icns.is_file():
                common += ["--icon", str(icns)]
        else:
            common += ["--icon", str(icon)]

    suffix = _exe_suffix()
    console_opts = [
        "--name",
        name,
        f"--{console_mode}",
        "--console",
        "--exclude-module",
        "tkinter",
    ]
    _pyinstaller(base + console_opts + common)
    if console_mode == "onedir":
        console_out = ROOT / "dist" / name / f"{name}{suffix}"
    else:
        console_out = ROOT / "dist" / f"{name}{suffix}"
    print(f"\n[OK] Version de consola (CLI): {console_out}\n")

    if build_gui:
        gui_opts = ["--name", f"{name}-gui", "--onefile", "--windowed"]
        _pyinstaller(base + gui_opts + common)
        print(
            f"[OK] Version grafica (GUI): "
            f"{ROOT / 'dist' / (name + '-gui' + suffix)}"
        )
        print("     (doble clic para abrir la interfaz grafica)")
        print()

    print("Resumen:")
    print(f"  CLI:  {console_out}   (usalo en la terminal)")
    if build_gui:
        print(f"  GUI:  {ROOT / 'dist' / (name + '-gui' + suffix)}   (doble clic para la GUI)")
    print()
    if sys.platform == "win32":
        print("  Siguiente paso (Windows): compilar el instalador con Inno Setup:")
        print("    iscc installer_win.iss")
    else:
        print("  Distribuye los binarios de dist/ o crea tu instalador del sistema.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build.py", description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_NAME,
        help=f"Nombre base de los ejecutables (por defecto: {DEFAULT_NAME})",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Compilar la version de consola como un solo archivo (por defecto: onedir)",
    )
    parser.add_argument(
        "--skip-gui",
        action="store_true",
        help="No compilar la version grafica sin consola",
    )
    parser.add_argument(
        "--icon",
        type=Path,
        default=None,
        help="Icono .ico (Windows) / .icns (macOS) para los ejecutables",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Eliminar build/ y dist/ antes de compilar",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    default_icon = ROOT / "assets" / "app.ico"
    icon = args.icon or (default_icon if default_icon.is_file() else None)
    console_mode = "onefile" if args.onefile else "onedir"
    build(args.name, console_mode, not args.skip_gui, icon, args.clean)


if __name__ == "__main__":
    main()
