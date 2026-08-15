"""Motor de escaneo de disco: os.scandir + multihilo.

El arbol se reparte entre los subdirectorios de primer nivel y cada uno se
recorre en un hilo con una pila explicita (sin recursion, segura para arboles
profundos). Los enlaces simbolicos no se siguen (evita bucles y doble conteo)
y los errores de permisos se cuentan sin abortar el escaneo.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

__all__ = [
    "Scanner",
    "DirStats",
    "FileStats",
    "ScanResult",
    "ProgressInfo",
    "format_size",
]


def format_size(num_bytes: float) -> str:
    """Convierte bytes a texto legible (B, KB, MB, GB, TB, PB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if size < 1024.0 or unit == "PB":
            if unit == "B":
                return f"{size:.0f} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


@dataclass
class FileStats:
    """Fichero directo de un directorio (nombre + tamano)."""

    name: str
    size: int = 0

    @property
    def size_human(self) -> str:
        return format_size(self.size)


@dataclass
class DirStats:
    """Estadisticas de un directorio (en escaneos completos, solo los hijos
    de primer nivel se conservan en ``children`` para no agotar memoria).

    ``direct_files`` solo se rellena si el Scanner se crea con ``keep_files``.
    """

    path: str
    size: int = 0
    files: int = 0
    dirs: int = 0
    errors: int = 0
    children: Dict[str, "DirStats"] = field(default_factory=dict)
    direct_files: List["FileStats"] = field(default_factory=list)

    @property
    def name(self) -> str:
        base = os.path.basename(self.path.rstrip("\\/"))
        return base or self.path

    @property
    def size_human(self) -> str:
        return format_size(self.size)


@dataclass
class ProgressInfo:
    """Instantanea de progreso para callbacks (GUI/CLI)."""

    files: int = 0
    dirs: int = 0
    size: int = 0
    cancelled: bool = False


@dataclass
class ScanResult:
    """Resultado agregado de un escaneo completo."""

    root: DirStats
    total_size: int = 0
    file_count: int = 0
    dir_count: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def total_human(self) -> str:
        return format_size(self.total_size)


class Scanner:
    """Escanea un arbol de directorios con os.scandir y hilos.

    Args:
        root: Ruta raiz a analizar.
        jobs: Numero de hilos (0 = nucleos de CPU).
        on_progress: Callback opcional, invocado periodicamente con ProgressInfo.
        max_errors: Limite de mensajes de error conservados en ScanResult.errors.
        keep_files: Si True, conserva en ``result.root.direct_files`` la lista
            de ficheros directos (nombres + tamanos) para pintarlos en un arbol.
    """

    def __init__(
        self,
        root: str,
        jobs: int = 0,
        on_progress: Optional[Callable[[ProgressInfo], None]] = None,
        max_errors: int = 100,
        keep_files: bool = False,
    ) -> None:
        self.root = os.path.abspath(root)
        self.jobs = jobs or max(1, os.cpu_count() or 4)
        self.on_progress = on_progress
        self.max_errors = max_errors
        self.keep_files = keep_files
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._live = ProgressInfo()
        self._error_log: List[str] = []
        self._last_report = 0.0

    @property
    def cancelled(self) -> bool:
        return self._stop.is_set()

    def stop(self) -> None:
        """Solicita la detencion del escaneo en curso."""
        self._stop.set()

    def _record(self, files: int, dirs: int, size: int, error: Optional[str]) -> None:
        with self._lock:
            self._live.files += files
            self._live.dirs += dirs
            self._live.size += size
            if error is not None and len(self._error_log) < self.max_errors:
                self._error_log.append(error)

    def _report(self) -> None:
        if not self.on_progress:
            return
        now = time.monotonic()
        if now - self._last_report < 0.1:
            return
        self._last_report = now
        with self._lock:
            info = ProgressInfo(
                files=self._live.files,
                dirs=self._live.dirs,
                size=self._live.size,
                cancelled=self.cancelled,
            )
        self.on_progress(info)

    def _walk_dir(self, path: str) -> DirStats:
        """Recorre un subarbol de forma iterativa; devuelve sus totales."""
        stats = DirStats(path=path)
        stack: List[str] = [path]
        while stack and not self._stop.is_set():
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    subdirs: List[str] = []
                    for entry in it:
                        if self._stop.is_set():
                            break
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                stats.dirs += 1
                                subdirs.append(entry.path)
                                self._record(0, 1, 0, None)
                            elif entry.is_file(follow_symlinks=False):
                                size = entry.stat(follow_symlinks=False).st_size
                                stats.files += 1
                                stats.size += size
                                self._record(1, 0, size, None)
                        except PermissionError as exc:
                            stats.errors += 1
                            self._record(0, 0, 0, str(exc))
                        except OSError as exc:
                            stats.errors += 1
                            self._record(0, 0, 0, str(exc))
                    stack.extend(reversed(subdirs))
            except PermissionError as exc:
                stats.errors += 1
                self._record(0, 0, 0, str(exc))
            except OSError as exc:
                stats.errors += 1
                self._record(0, 0, 0, str(exc))
            self._report()
        return stats

    def scan(self) -> ScanResult:
        """Ejecuta el escaneo completo de la raiz y devuelve el resultado."""
        root = DirStats(path=self.root)
        result = ScanResult(root=root)

        entries: List[os.DirEntry] = []
        try:
            with os.scandir(self.root) as it:
                for entry in it:
                    if self._stop.is_set():
                        break
                    entries.append(entry)
        except PermissionError as exc:
            root.errors += 1
            self._record(0, 0, 0, str(exc))
        except OSError as exc:
            root.errors += 1
            self._record(0, 0, 0, str(exc))

        subdirs: List[os.DirEntry] = []
        for entry in entries:
            if self._stop.is_set():
                break
            try:
                if entry.is_dir(follow_symlinks=False):
                    subdirs.append(entry)
                elif entry.is_file(follow_symlinks=False):
                    size = entry.stat(follow_symlinks=False).st_size
                    root.files += 1
                    root.size += size
                    self._record(1, 0, size, None)
                    if self.keep_files:
                        root.direct_files.append(FileStats(entry.name, size))
            except PermissionError as exc:
                root.errors += 1
                self._record(0, 0, 0, str(exc))
            except OSError as exc:
                root.errors += 1
                self._record(0, 0, 0, str(exc))

        done: List[tuple] = []
        if subdirs and not self._stop.is_set():
            with ThreadPoolExecutor(max_workers=self.jobs) as pool:
                futures = {pool.submit(self._walk_dir, d.path): d for d in subdirs}
                for future in as_completed(futures):
                    entry = futures[future]
                    try:
                        child = future.result()
                    except Exception as exc:
                        child = DirStats(path=entry.path, errors=1)
                        self._record(0, 0, 0, f"{entry.path}: {exc}")
                    done.append((entry.name, child))

        for name, child in done:
            root.children[name] = child
            root.files += child.files
            root.dirs += child.dirs + 1
            root.size += child.size
            root.errors += child.errors

        result.total_size = root.size
        result.file_count = root.files
        result.dir_count = root.dirs
        result.error_count = root.errors
        with self._lock:
            result.errors = list(self._error_log)
        result.cancelled = self._stop.is_set()

        if self.on_progress:
            with self._lock:
                self.on_progress(
                    ProgressInfo(
                        files=self._live.files,
                        dirs=self._live.dirs,
                        size=self._live.size,
                        cancelled=result.cancelled,
                    )
                )
        return result
