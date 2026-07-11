from __future__ import annotations

import argparse
import os
import subprocess
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"

SERVICE_IMPORTS = {
    "landing": ("entry_landing:app", "LANDING_PORT", 8001),
    "miniapp": ("entry_miniapp:app", "MINIAPP_PORT", 8002),
    "cabinet": ("entry_cabinet:app", "CABINET_PORT", 8003),
    "api": ("entry_api:app", "API_PORT", 8004),
    "admin": ("entry_admin:app", "ADMIN_FRONTEND_PORT", 8011),
}


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def bootstrap() -> None:
    if not VENV_DIR.exists():
        venv.create(VENV_DIR, with_pip=True)
    python_bin = _venv_python()
    subprocess.check_call([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], cwd=ROOT)
    subprocess.check_call([str(python_bin), "-m", "pip", "install", "-r", "requirements.txt"], cwd=ROOT)


def run_service(name: str) -> None:
    if name == "bot":
        from backend.apps.bot import run_bot
        from backend.core.runtime import run_async

        run_async(run_bot)
        return

    from backend.core.runtime import run_uvicorn

    import_path, port_env, default_port = SERVICE_IMPORTS[name]
    run_uvicorn(import_path, port_env=port_env, default_port=default_port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lunet service manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap", help="Create virtualenv and install dependencies")

    run_parser = subparsers.add_parser("run", help="Run a single service")
    run_parser.add_argument("service", choices=[*SERVICE_IMPORTS.keys(), "bot"])
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap()
        return
    if args.command == "run":
        run_service(args.service)
        return
    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
