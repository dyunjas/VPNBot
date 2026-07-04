from backend.apps.bot import run_bot
from backend.core.runtime import run_async


def main() -> None:
    run_async(run_bot)


if __name__ == "__main__":
    main()
