import argparse

from .dashboard import export_dashboard
from .download import download_all
from .transform import build_all
from .validate import validate_all


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline de ventas, canales y medios de pago del retail argentino."
    )
    parser.add_argument(
        "stage",
        choices=["download", "build", "validate", "export", "all"],
        help="Etapa que se desea ejecutar.",
    )
    parser.add_argument("--force", action="store_true", help="Descarga nuevamente las fuentes.")
    arguments = parser.parse_args()

    if arguments.stage in ("download", "all"):
        download_all(force=arguments.force)
    if arguments.stage in ("build", "all"):
        build_all()
    if arguments.stage in ("validate", "all"):
        validate_all()
    if arguments.stage in ("export", "all"):
        export_dashboard()


if __name__ == "__main__":
    main()
