"""Interfaz de linea de comandos (CLI) para filesysman.

Uso: filesysman [opciones] [RUTA]
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from typing import List, Optional

from . import __version__
from .core import ProgressInfo, ScanResult, Scanner, format_size

WRITE_LOCK = threading.Lock()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="filesysman",
        description="Analizador de espacio en disco estilo TreeSize (CLI).",
        usage="%(prog)s [opciones] [RUTA]",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Carpeta a analizar (por defecto: la actual).",
    )
    parser.add_argument(
        "-n",
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="Mostrar las N carpetas que mas ocupan (por defecto: 10).",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=0,
        metavar="N",
        help="Hilos de escaneo; 0 = automatico (por defecto).",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="No mostrar el progreso en vivo.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _ensure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def _progress(info: ProgressInfo) -> None:
    if not sys.stderr.isatty():
        return
    with WRITE_LOCK:
        sys.stderr.write(
            f"\r  Escaneando... {info.files:,} archivos, {format_size(info.size)}"
        )
        sys.stderr.flush()


def _clear_progress() -> None:
    if not sys.stderr.isatty():
        return
    with WRITE_LOCK:
        sys.stderr.write("\r" + " " * 60 + "\r")
        sys.stderr.flush()


def _report(result: ScanResult, top: int, elapsed: float) -> None:
    total = result.total_size
    print()
    print(
        f"  Total: {format_size(total)}  "
        f"({result.file_count:,} archivos, {result.dir_count:,} carpetas)"
    )
    if result.error_count:
        print(
            f"  Errores: {result.error_count} "
            "(permisos denegados u otros; ejecuta como administrador si quieres "
            "analizar carpetas del sistema)"
        )
    if result.cancelled:
        print("  (escaneo interrumpido: resultados parciales)")
    print()

    children = sorted(
        result.root.children.items(), key=lambda kv: kv[1].size, reverse=True
    )
    if not children:
        print("  No hay subcarpetas.")
        print()
        return

    shown = children[:top]
    print(f"  Carpetas que mas ocupan ({len(shown)} de {len(children)}):")
    print()
    for i, (name, stats) in enumerate(shown, 1):
        pct = stats.size * 100.0 / total if total else 0.0
        bar_len = int(round(pct / 100.0 * 30))
        bar = "#" * bar_len + "-" * (30 - bar_len)
        print(
            f"  {i:>2}. {bar} {pct:5.1f}%  {format_size(stats.size):>10}  "
            f"{name[:60]}"
        )
    print()
    if len(children) > top:
        rest = sum(stats.size for _, stats in children[top:])
        print(f"  Y {len(children) - top} carpetas mas: {format_size(rest)}")
    print(f"  Tiempo: {elapsed:.2f} s")


def run(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    top = max(1, args.top)
    path = os.path.abspath(os.path.expanduser(args.path))

    if not os.path.exists(path):
        print(f"Error: la ruta no existe: {path}", file=sys.stderr)
        return 2
    if os.path.isfile(path):
        print(f"  {path}")
        print(f"  Tamano: {format_size(os.path.getsize(path))}  (1 archivo)")
        return 0

    print(f"  Analizando: {path}")
    on_progress = _progress if (not args.quiet) else None
    scanner = Scanner(path, jobs=args.jobs, on_progress=on_progress)
    start = time.perf_counter()
    result = scanner.scan()
    elapsed = time.perf_counter() - start
    _clear_progress()
    _report(result, top, elapsed)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    _ensure_utf8()
    return run(argv)
