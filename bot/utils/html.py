from html import escape


def html_escape(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)
