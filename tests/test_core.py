"""Pruebas unitarias del motor de escaneo (src/core.py) y sus formatos.

Cubre: tamanos formateados, totales correctos, arboles vacios, rutas
inexistentes, permisos denegados, bucles de enlaces simbolicos, cancelacion,
progreso y variantes de hilos.
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core import Scanner, format_size  # noqa: E402


def _build_tree(base: Path) -> None:
    (base / "docs").mkdir()
    (base / "docs" / "a.txt").write_text("a" * 10)
    (base / "docs" / "sub").mkdir()
    (base / "docs" / "sub" / "b.bin").write_bytes(b"\x00" * 100)
    (base / "media").mkdir()
    (base / "media" / "c.bin").write_bytes(b"\xff" * 2000)
    (base / "root.txt").write_text("hello")


TOTAL_BYTES = 10 + 100 + 2000 + 5  # 2115
TOTAL_FILES = 4
TOTAL_DIRS = 3  # docs, docs/sub, media


def test_format_size_bytes() -> None:
    assert format_size(0) == "0 B"
    assert format_size(512) == "512 B"
    assert format_size(1023) == "1023 B"


def test_format_size_kb() -> None:
    assert format_size(1024) == "1.0 KB"
    assert format_size(1536) == "1.5 KB"


def test_format_size_mb_gb_tb() -> None:
    assert format_size(1024**2) == "1.0 MB"
    assert format_size(1024**3) == "1.0 GB"
    assert format_size(1024**4) == "1.0 TB"


def test_format_size_rounding() -> None:
    assert format_size(1024**3 + 512 * 1024**2) == "1.5 GB"


def test_scan_tree_totals(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    result = Scanner(str(tmp_path)).scan()
    assert result.total_size == TOTAL_BYTES
    assert result.file_count == TOTAL_FILES
    assert result.dir_count == TOTAL_DIRS
    assert result.error_count == 0
    assert not result.cancelled


def test_scan_children_stats(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    result = Scanner(str(tmp_path)).scan()
    names = sorted(result.root.children)
    assert names == ["docs", "media"]
    docs = result.root.children["docs"]
    assert docs.size == 110
    assert docs.files == 2
    assert docs.dirs == 1
    media = result.root.children["media"]
    assert media.size == 2000
    assert media.size_human == "2.0 KB"
    assert result.total_human == format_size(TOTAL_BYTES)


def test_scan_empty_directory(tmp_path: Path) -> None:
    result = Scanner(str(tmp_path)).scan()
    assert result.total_size == 0
    assert result.file_count == 0
    assert result.dir_count == 0
    assert not result.root.children


def test_scan_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "no_existe"
    result = Scanner(str(missing)).scan()
    assert result.error_count == 1
    assert result.total_size == 0
    assert result.errors, "el error deberia quedar registrado"


def test_permission_error_is_swallowed(monkeypatch, tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    (tmp_path / "ok.txt").write_text("1234")

    real_scandir = os.scandir

    def guarded(path, *args, **kwargs):
        if os.fspath(path) == str(locked):
            raise PermissionError(13, "Permission denied", str(path))
        return real_scandir(path, *args, **kwargs)

    monkeypatch.setattr(os, "scandir", guarded)
    result = Scanner(str(tmp_path)).scan()
    assert result.error_count == 1
    assert result.total_size == 4
    assert "locked" in result.errors[0]


def test_symlink_cycle_not_followed(tmp_path: Path) -> None:
    target = tmp_path / "real"
    target.mkdir()
    (target / "f.txt").write_text("x")
    try:
        os.symlink(tmp_path, tmp_path / "loop", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("los enlaces simbolicos no estan disponibles en este sistema")
    result = Scanner(str(tmp_path)).scan()
    assert result.total_size == 1
    assert result.dir_count == 1
    assert "loop" not in result.root.children


def test_stop_cancels_scan(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    scanner = Scanner(str(tmp_path))
    scanner.stop()
    result = scanner.scan()
    assert result.cancelled is True
    assert scanner.cancelled is True


def test_scan_jobs_variants(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    for jobs in (1, 2, 4):
        result = Scanner(str(tmp_path), jobs=jobs).scan()
        assert result.total_size == TOTAL_BYTES
        assert result.file_count == TOTAL_FILES
        assert result.dir_count == TOTAL_DIRS


def test_keep_files_lists_direct_files(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    result = Scanner(str(tmp_path), keep_files=True).scan()
    names = sorted(f.name for f in result.root.direct_files)
    assert names == ["root.txt"]
    assert result.root.direct_files[0].size == 5
    assert result.root.direct_files[0].size_human == "5 B"


def test_progress_callback_reports_final_totals(tmp_path: Path) -> None:
    _build_tree(tmp_path)
    seen = []
    scanner = Scanner(str(tmp_path), on_progress=seen.append)
    result = scanner.scan()
    assert seen, "el callback de progreso deberia haberse invocado"
    last = seen[-1]
    assert last.size == result.total_size
    assert last.files == result.file_count
