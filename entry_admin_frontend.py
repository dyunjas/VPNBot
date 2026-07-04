from backend.apps.admin_frontend import create_app
from backend.core.runtime import run_uvicorn

app = create_app()


def main() -> None:
    run_uvicorn("entry_admin_frontend:app", port_env="ADMIN_FRONTEND_PORT", default_port=8011)


if __name__ == "__main__":
    main()
