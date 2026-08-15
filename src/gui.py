"""Interfaz grafica moderna con PySide6 (Qt6): tema claro/oscuro + barras de %.

El arbol muestra la raiz, sus ficheros directos y sus carpetas de primer nivel.
Al **expandir** una carpeta se escanea su contenido bajo demanda en un QThread
(estilo TreeSize, sin agotar memoria): se cargan los ficheros y subcarpetas
directos con su tamano y porcentaje. Doble clic expande/colapsa.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QRectF, Qt, QThread, QUrl, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QIcon,
    QPainter,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __app_name__
from .core import ProgressInfo, ScanResult, Scanner, format_size

COLUMNS = ("name", "size", "percent", "files", "dirs")
HEADERS = ("Nombre", "Tamano", "% del total", "Archivos", "Carpetas")

PERCENT_ROLE = Qt.UserRole + 1
PATH_ROLE = Qt.UserRole + 2
DIR_ROLE = Qt.UserRole + 3
SIZE_ROLE = Qt.UserRole + 4
LOADED_ROLE = Qt.UserRole + 5
PLACEHOLDER_ROLE = Qt.UserRole + 6

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

DARK_COLORS = {
    "bg": "#23272e",
    "surface": "#2e333d",
    "surface_hover": "#38404d",
    "base": "#1b1e24",
    "alt": "#262b33",
    "border": "#3a3f4b",
    "text": "#e8eaed",
    "text_dim": "#6a7280",
    "accent": "#3d7bff",
    "accent_hover": "#5a92ff",
    "danger": "#e5484d",
}

LIGHT_COLORS = {
    "bg": "#f2f4f7",
    "surface": "#ffffff",
    "surface_hover": "#f7f9fc",
    "base": "#ffffff",
    "alt": "#f7f9fc",
    "border": "#d9dee6",
    "text": "#1f2328",
    "text_dim": "#6b7280",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "danger": "#dc2626",
}

QSS_TEMPLATE = """
QWidget {{
    background-color: {bg};
    color: {text};
    font-size: 13px;
}}
QLineEdit {{
    background-color: {base};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 7px 10px;
}}
QLineEdit:focus {{ border-color: {accent}; }}
QPushButton {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background-color: {surface_hover}; }}
QPushButton:pressed {{ background-color: {bg}; }}
QPushButton:disabled {{
    color: {text_dim};
    border-color: {border};
    background-color: {surface};
}}
QPushButton#primary {{
    background-color: {accent};
    border-color: {accent};
    color: white;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: {accent_hover}; }}
QPushButton#primary:disabled {{
    background-color: {surface};
    border-color: {border};
    color: {text_dim};
}}
QPushButton#danger {{ color: {danger}; }}
QPushButton#danger:hover {{ background-color: {danger}; color: white; }}
QTreeWidget {{
    background-color: {base};
    alternate-background-color: {alt};
    border: 1px solid {border};
    border-radius: 6px;
}}
QTreeWidget::item {{ padding: 3px 2px; }}
QTreeWidget::item:selected {{ background-color: {accent}; color: white; }}
QHeaderView::section {{
    background-color: {surface};
    border: none;
    border-bottom: 1px solid {border};
    padding: 6px 8px;
    font-weight: 600;
}}
QMenu {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 22px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {accent}; color: white; }}
QStatusBar {{ background-color: {bg}; }}
QProgressBar {{
    background-color: {base};
    border: 1px solid {border};
    border-radius: 4px;
    max-height: 8px;
}}
QProgressBar::chunk {{ background-color: {accent}; border-radius: 3px; }}
QScrollBar:vertical {{
    background: {base};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {border};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {base};
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {border};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QToolTip {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
}}
"""


def _qss(colors) -> str:
    return QSS_TEMPLATE.format(**colors)


def _palette(dark: bool) -> QPalette:
    if not dark:
        app = QApplication.instance()
        return app.style().standardPalette() if app else QPalette()
    p = QPalette()
    window = QColor(DARK_COLORS["bg"])
    base = QColor(DARK_COLORS["base"])
    text = QColor(DARK_COLORS["text"])
    surface = QColor(DARK_COLORS["surface"])
    accent = QColor(DARK_COLORS["accent"])
    disabled = QColor(DARK_COLORS["text_dim"])
    p.setColor(QPalette.Window, window)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, QColor(DARK_COLORS["alt"]))
    p.setColor(QPalette.ToolTipBase, surface)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, surface)
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.BrightText, QColor(DARK_COLORS["danger"]))
    p.setColor(QPalette.Highlight, accent)
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.Link, QColor("#6aa1ff"))
    for role in (
        QPalette.WindowText,
        QPalette.Text,
        QPalette.ButtonText,
        QPalette.HighlightedText,
        QPalette.ToolTipText,
    ):
        p.setColor(QPalette.Disabled, role, disabled)
    return p


def apply_theme(app: QApplication, dark: bool) -> None:
    app.setStyle("Fusion")
    app.setPalette(_palette(dark))
    app.setStyleSheet(_qss(DARK_COLORS if dark else LIGHT_COLORS))


def _app_icon() -> QIcon:
    for candidate in (ASSETS_DIR / "app.ico", Path("assets") / "app.ico"):
        try:
            if candidate.is_file():
                return QIcon(str(candidate))
        except OSError:
            continue
    return QIcon()


class PercentDelegate(QStyledItemDelegate):
    """Dibuja la columna de porcentaje como una barra de progreso redondeada."""

    def paint(self, painter: QPainter, option, index) -> None:
        super().paint(painter, option, index)
        pct = index.data(PERCENT_ROLE)
        if pct is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(12, 4, -12, -4)
        if rect.width() < 8 or rect.height() < 4:
            painter.restore()
            return
        radius = rect.height() / 2.0
        selected = bool(option.state & QStyle.State_Selected)
        if selected:
            track = QColor(255, 255, 255, 45)
            fill = QColor(255, 255, 255, 190)
            text_color = QColor(255, 255, 255)
        else:
            track = QColor(option.palette.color(QPalette.Text))
            track.setAlpha(24)
            fill = QColor(option.palette.color(QPalette.Highlight))
            text_color = option.palette.color(QPalette.Text)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(rect, radius, radius)
        pct = max(0.0, min(float(pct), 100.0))
        fill_rect = QRectF(
            rect.left(), rect.top(), rect.width() * pct / 100.0, rect.height()
        )
        if fill_rect.width() >= 2:
            painter.setBrush(fill)
            painter.drawRoundedRect(fill_rect, radius, radius)
        painter.setPen(text_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{pct:.1f}%")
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height() + 6, 26))
        return size


class ScanWorker(QThread):
    """Escaneo de la raiz: notifica por senales (seguro para la UI)."""

    progress = Signal(object)
    done = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, path: str, scan_id: int, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        self.scan_id = scan_id
        self.scanner: Optional[Scanner] = None

    def run(self) -> None:
        scanner = Scanner(self.path, on_progress=self.progress.emit, keep_files=True)
        self.scanner = scanner
        try:
            result = scanner.scan()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(self.scan_id, str(exc))
            return
        self.done.emit(self.scan_id, result)


class DirWorker(QThread):
    """Escaneo bajo demanda de una carpeta al expandirla en el arbol."""

    done = Signal(object, object)
    failed = Signal(object, str)

    def __init__(self, path: str, item: QTreeWidgetItem, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        self.item = item
        self.scanner: Optional[Scanner] = None

    def run(self) -> None:
        scanner = Scanner(self.path, keep_files=True)
        self.scanner = scanner
        try:
            result = scanner.scan()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(self.item, str(exc))
            return
        self.done.emit(self.item, result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{__app_name__} - Analisis de espacio en disco")
        self.setWindowIcon(_app_icon())
        self.resize(980, 640)
        self.setMinimumSize(720, 460)

        self._dark = True
        self._current = os.path.abspath(os.path.expanduser("~"))
        self._scan_id = 0
        self._worker: Optional[ScanWorker] = None
        self._dir_worker: Optional[DirWorker] = None
        self._pending: List[QTreeWidgetItem] = []
        self._summary_text = ""

        self._build_ui()
        self._set_busy(False)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 0)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.path_edit = QLineEdit(self._current)
        self.path_edit.setPlaceholderText("Ruta a analizar...")
        self.path_edit.setClearButtonEnabled(True)
        self.path_edit.returnPressed.connect(self._start_scan)
        top.addWidget(self.path_edit, 1)

        self.browse_btn = QPushButton("Examinar...")
        self.browse_btn.clicked.connect(self._browse)
        top.addWidget(self.browse_btn)

        self.up_btn = QPushButton()
        self.up_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.up_btn.setToolTip("Carpeta padre")
        self.up_btn.setFixedWidth(36)
        self.up_btn.clicked.connect(self._go_up)
        top.addWidget(self.up_btn)

        self.scan_btn = QPushButton("Analizar")
        self.scan_btn.setObjectName("primary")
        self.scan_btn.clicked.connect(self._start_scan)
        top.addWidget(self.scan_btn)

        self.stop_btn = QPushButton("Detener")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.clicked.connect(self._stop_scan)
        self.stop_btn.setEnabled(False)
        top.addWidget(self.stop_btn)

        self.theme_btn = QPushButton()
        self.theme_btn.clicked.connect(self._toggle_theme)
        top.addWidget(self.theme_btn)
        root.addLayout(top)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(COLUMNS))
        self.tree.setHeaderLabels(HEADERS)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setItemDelegateForColumn(2, PercentDelegate(self.tree))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemExpanded.connect(self._on_expand)
        self.tree.setToolTip("Doble clic en una carpeta para expandirla")
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in zip((1, 2, 3, 4), (110, 140, 100, 100)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.tree.setColumnWidth(column, width)
        root.addWidget(self.tree, 1)
        self.setCentralWidget(central)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(190)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.status_label = QLabel("Listo. Elige una carpeta y pulsa Analizar.")
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e5484d;")
        self.error_label.hide()
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.error_label)
        self.statusBar().addPermanentWidget(self.progress)

        self._apply_theme()

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self._dark)
        self.theme_btn.setText("Tema claro" if self._dark else "Tema oscuro")

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._apply_theme()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))

    # ------------------------------------------------------------- acciones

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Elegir carpeta a analizar",
            self.path_edit.text().strip() or self._current,
        )
        if chosen:
            self.path_edit.setText(chosen)

    def _current_path(self) -> str:
        value = os.path.expanduser(self.path_edit.text().strip())
        return os.path.abspath(value) if value else os.path.abspath(os.curdir)

    def _start_scan(self) -> None:
        path = self._current_path()
        if not os.path.isdir(path):
            self._show_error(f"No existe o no es una carpeta: {path}")
            return
        self._current = path
        self._begin_scan(path)

    def _begin_scan(self, path: str) -> None:
        if self._worker is not None:
            return
        self._pending.clear()
        dir_worker = self._dir_worker
        if dir_worker is not None and dir_worker.scanner is not None:
            dir_worker.scanner.stop()
        self._scan_id += 1
        worker = ScanWorker(path, self._scan_id, self)
        worker.progress.connect(self._on_progress)
        worker.done.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        self.tree.clear()
        self._set_busy(True)
        self._show_error("")
        self.status_label.setText(f"Analizando {path} ...")
        worker.start()

    def _stop_scan(self) -> None:
        worker = self._worker
        if worker is not None and worker.scanner is not None:
            worker.scanner.stop()

    def _go_up(self) -> None:
        parent = os.path.dirname(self._current)
        if parent != self._current:
            self._current = parent
            self.path_edit.setText(parent)
            self._begin_scan(parent)

    def _set_busy(self, busy: bool) -> None:
        parent = os.path.dirname(self._current)
        can_go_up = parent != self._current
        self.scan_btn.setEnabled(not busy)
        self.browse_btn.setEnabled(not busy)
        self.up_btn.setEnabled(not busy and can_go_up)
        self.stop_btn.setEnabled(busy)
        if busy:
            self.progress.setRange(0, 0)
            self.progress.show()
        else:
            self.progress.hide()

    # -------------------------------------------------------- callbacks Qt

    def _on_progress(self, info: ProgressInfo) -> None:
        if self._worker is None:
            return
        self.status_label.setText(
            f"Analizando... {info.files:,} archivos, {format_size(info.size)}"
        )

    def _on_done(self, scan_id: int, result: ScanResult) -> None:
        if scan_id == self._scan_id:
            self._finish(result)

    def _on_failed(self, scan_id: int, message: str) -> None:
        if scan_id != self._scan_id:
            return
        self.status_label.setText("Error durante el analisis.")
        self._show_error(message)

    def _on_worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self._set_busy(False)

    # ------------------------------------------------------------ resultados

    def _finish(self, result: ScanResult) -> None:
        self._current = result.root.path
        self.path_edit.setText(result.root.path)
        if result.cancelled:
            self._summary_text = "Analisis detenido (resultados parciales)."
        else:
            self._summary_text = (
                f"Total: {result.total_human} - {result.file_count:,} archivos, "
                f"{result.dir_count:,} carpetas"
            )
        self.status_label.setText(self._summary_text)
        if result.error_count:
            self._show_error(
                f"{result.error_count} errores (permisos denegados u otros)"
            )
        else:
            self._show_error("")
        self._populate(result)

    def _make_item(
        self,
        name: str,
        size_h: str,
        pct: float,
        files: int,
        dirs: int,
        path: str,
        is_dir: bool,
        size: int = 0,
        bold: bool = False,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem(
            [name, size_h, f"{pct:.1f}%", f"{files:,}", f"{dirs:,}"]
        )
        item.setData(2, PERCENT_ROLE, float(pct))
        item.setData(0, PATH_ROLE, path)
        item.setData(0, DIR_ROLE, is_dir)
        item.setData(0, SIZE_ROLE, int(size))
        item.setData(0, LOADED_ROLE, False)
        icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_DirIcon
            if is_dir
            else QStyle.StandardPixmap.SP_FileIcon
        )
        item.setIcon(0, icon)
        if bold:
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
        if is_dir and (files > 0 or dirs > 0):
            placeholder = QTreeWidgetItem(["Cargando..."])
            placeholder.setData(0, PLACEHOLDER_ROLE, True)
            placeholder.setForeground(0, QBrush(QColor("#8b93a1")))
            item.addChild(placeholder)
        return item

    def _populate(self, result: ScanResult) -> None:
        self.tree.clear()
        total = result.total_size or 1
        root_item = self._make_item(
            result.root.path,
            result.total_human,
            100.0,
            result.file_count,
            result.dir_count,
            path=result.root.path,
            is_dir=False,
            size=result.total_size,
            bold=True,
        )
        root_item.setData(0, LOADED_ROLE, True)
        self.tree.addTopLevelItem(root_item)
        for child in self._entries(result):
            root_item.addChild(child)
        root_item.setExpanded(True)

    def _entries(
        self,
        result: ScanResult,
        parent_path: Optional[str] = None,
        total: Optional[int] = None,
    ) -> List[QTreeWidgetItem]:
        """Crea los items directos (ficheros + carpetas) de la raiz escaneada."""
        entries = []
        for f in result.root.direct_files:
            entries.append((f.name, False, f.size, f.size_human, 1, 0))
        for name, stats in result.root.children.items():
            entries.append(
                (name, True, stats.size, stats.size_human, stats.files, stats.dirs)
            )
        entries.sort(key=lambda e: e[2], reverse=True)
        total = total or result.total_size or 1
        base = parent_path if parent_path is not None else result.root.path
        items = []
        for name, is_dir, size, size_h, files, dirs in entries:
            pct = size * 100.0 / total
            items.append(
                self._make_item(
                    name,
                    size_h,
                    pct,
                    files,
                    dirs,
                    path=os.path.join(base, name),
                    is_dir=is_dir,
                    size=size,
                )
            )
        return items

    # ------------------------------------------------- carga perezosa (expand)

    def _on_expand(self, item: QTreeWidgetItem) -> None:
        if not item.data(0, DIR_ROLE):
            return
        if item.data(0, LOADED_ROLE):
            return
        if item.childCount() == 1 and item.child(0).data(0, PLACEHOLDER_ROLE):
            item.removeChild(item.child(0))
        self._request_children(item)

    def _request_children(self, item: QTreeWidgetItem) -> None:
        if any(existing is item for existing in self._pending):
            return
        self._pending.append(item)
        self._start_next_expansion()

    def _start_next_expansion(self) -> None:
        if self._dir_worker is not None or not self._pending:
            return
        item = self._pending.pop(0)
        path = item.data(0, PATH_ROLE)
        if not path:
            self._start_next_expansion()
            return
        worker = DirWorker(str(path), item, self)
        worker.done.connect(self._on_dir_children)
        worker.failed.connect(self._on_dir_failed)
        worker.finished.connect(self._on_dir_worker_finished)
        self._dir_worker = worker
        self.status_label.setText(f"Cargando hijos de {path} ...")
        worker.start()

    def _on_dir_children(self, item: QTreeWidgetItem, result: ScanResult) -> None:
        if item.treeWidget() is None:
            return
        parent_path = str(item.data(0, PATH_ROLE))
        total = int(item.data(0, SIZE_ROLE)) or 1
        for child in self._entries(result, parent_path=parent_path, total=total):
            item.addChild(child)
        item.setData(0, LOADED_ROLE, True)
        self.status_label.setText(self._summary_text)

    def _on_dir_failed(self, item: QTreeWidgetItem, message: str) -> None:
        if item.treeWidget() is not None:
            self._show_error(f"No se pudo leer {item.data(0, PATH_ROLE)}: {message}")
        self.status_label.setText(self._summary_text)

    def _on_dir_worker_finished(self) -> None:
        worker = self._dir_worker
        self._dir_worker = None
        if worker is not None:
            worker.deleteLater()
        self._start_next_expansion()

    # ------------------------------------------------------------ eventos

    def _context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        path = item.data(0, PATH_ROLE)
        if not path:
            return
        menu = QMenu(self)
        if item.data(0, DIR_ROLE):
            action_scan = menu.addAction("Analizar esta carpeta")
            action_scan.triggered.connect(lambda: self._begin_scan(str(path)))
        open_action = menu.addAction("Abrir en el explorador")
        open_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        )
        copy_action = menu.addAction("Copiar ruta")
        copy_action.triggered.connect(
            lambda: QGuiApplication.clipboard().setText(str(path))
        )
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def closeEvent(self, event) -> None:
        for worker in (self._worker, self._dir_worker):
            if worker is not None:
                if worker.scanner is not None:
                    worker.scanner.stop()
                if not worker.wait(3000):
                    worker.terminate()
                    worker.wait(1000)
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    apply_theme(app, True)
    app.setWindowIcon(_app_icon())
    window = MainWindow()
    window.show()
    return app.exec()
