from backend.apps.miniapp import create_app
from backend.core.runtime import run_uvicorn

app = create_app()


def main() -> None:
    run_uvicorn("entry_miniapp:app", port_env="MINIAPP_PORT", default_port=8002)


if __name__ == "__main__":
    main()
