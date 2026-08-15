"""Punto de entrada unificado de filesysman.

- Con argumentos (ej. ``filesysman C:\\``)  -> modo CLI.
- Sin argumentos (ej. doble clic)           -> modo GUI (PySide6/Qt).
- ``--cli`` o ``--gui`` fuerzan un modo concreto.

Si PySide6 no esta instalado, se usa el modo CLI como respaldo automatico.
"""

import sys


def _gui_available() -> bool:
    try:
        import PySide6  # noqa: F401

        return True
    except Exception:
        return False


def _run_cli(argv):
    from src.cli import main as cli_main

    return cli_main(argv)


def _run_gui() -> None:
    from src.gui import main as gui_main

    gui_main()


def main() -> int:
    force_cli = "--cli" in sys.argv
    force_gui = "--gui" in sys.argv
    args = [a for a in sys.argv[1:] if a not in ("--cli", "--gui")]

    if force_cli:
        return _run_cli(args)

    if force_gui or not args:
        if _gui_available():
            try:
                _run_gui()
                return 0
            except Exception as exc:
                print(f"GUI no disponible en este entorno: {exc}", file=sys.stderr)
                if force_gui:
                    return 1
        else:
            print(
                "PySide6 no esta instalado; se usara el modo CLI "
                "(instala con: pip install PySide6).",
                file=sys.stderr,
            )

    return _run_cli(args or ["."])


if __name__ == "__main__":
    sys.exit(main())
