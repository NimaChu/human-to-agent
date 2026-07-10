from __future__ import annotations

from jinja2 import Environment, StrictUndefined


def render_template(source: str, context: dict[str, object]) -> str:
    environment = Environment(
        undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True
    )
    rendered = environment.from_string(source).render(**context)
    return rendered.replace("\r\n", "\n").replace("\r", "\n")
