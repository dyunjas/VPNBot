from backend.apps.cabinet import create_app
from backend.core.runtime import run_uvicorn

app = create_app()


def main() -> None:
    run_uvicorn("entry_cabinet:app", port_env="CABINET_PORT", default_port=8003)


if __name__ == "__main__":
    main()
