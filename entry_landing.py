from backend.apps.landing import create_app
from backend.core.runtime import run_uvicorn

app = create_app()


def main() -> None:
    run_uvicorn("entry_landing:app", port_env="LANDING_PORT", default_port=8001)


if __name__ == "__main__":
    main()
