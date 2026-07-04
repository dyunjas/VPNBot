from backend.apps.api import create_app
from backend.core.runtime import run_uvicorn

app = create_app()


def main() -> None:
    run_uvicorn("entry_api:app", port_env="API_PORT", default_port=8004)


if __name__ == "__main__":
    main()
