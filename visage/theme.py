"""Theme engine — load TOML themes, generate dynamic TCSS."""

import importlib.resources
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class Theme:
    name: str
    display_name: str
    colors: dict[str, str] = field(default_factory=dict)
    graph_style: str = "braille"

    def get(self, key: str, default: str = "") -> str:
        return self.colors.get(key, default)


_BUILTIN_THEME_DIR = Path(__file__).parent / "themes"


def _load_builtin_themes() -> dict[str, Theme]:
    themes: dict[str, Theme] = {}
    if not _BUILTIN_THEME_DIR.exists():
        return themes
    for toml_file in sorted(_BUILTIN_THEME_DIR.glob("*.toml")):
        try:
            with open(toml_file, "rb") as f:
                data = tomllib.load(f)
            meta = data.get("meta", {})
            colors = data.get("colors", {})
            name = toml_file.stem
            themes[name] = Theme(
                name=name,
                display_name=meta.get("display_name", name.title()),
                colors=colors,
                graph_style=meta.get("graph_style", "braille"),
            )
        except Exception:
            continue
    return themes


_BUILTIN_THEMES = _load_builtin_themes()


def list_themes() -> list[str]:
    return list(_BUILTIN_THEMES.keys())


def get_theme(name: str) -> Theme | None:
    return _BUILTIN_THEMES.get(name)


def get_default_theme() -> Theme:
    if "default" in _BUILTIN_THEMES:
        return _BUILTIN_THEMES["default"]
    if _BUILTIN_THEMES:
        first = next(iter(_BUILTIN_THEMES.values()))
        return first
    return Theme(name="fallback", display_name="Fallback", colors={
        "bg": "#1a1b26", "card": "#24283b", "border": "#3b4261",
        "accent": "#7aa2f7", "text": "#a9b1d6", "graph": "#7dcfff",
        "dim": "#565f89",
    })


def load_custom_theme(path: str | Path) -> Theme | None:
    try:
        p = Path(path)
        with open(p, "rb") as f:
            data = tomllib.load(f)
        meta = data.get("meta", {})
        colors = data.get("colors", {})
        name = p.stem
        return Theme(
            name=name,
            display_name=meta.get("display_name", name.title()),
            colors=colors,
            graph_style=meta.get("graph_style", "braille"),
        )
    except Exception:
        return None


def generate_tcss(theme: Theme) -> str:
    """Generate TCSS from a theme's color definitions."""
    c = theme.colors
    bg = c.get("bg", "#1a1b26")
    card = c.get("card", "#24283b")
    border = c.get("border", "#3b4261")
    accent = c.get("accent", "#7aa2f7")
    text = c.get("text", "#a9b1d6")
    graph = c.get("graph", "#7dcfff")
    dim = c.get("dim", "#565f89")
    bar = c.get("bar", graph)

    return f"""/* Visage — Generated from theme: {theme.display_name} */

Screen {{
    background: {bg};
}}

#dashboard {{
    layout: vertical;
    overflow-y: auto;
    padding: 0 1;
}}

.metric-card {{
    margin: 0 0 0 0;
    background: {card};
    border: solid {border};
    border-title-color: {accent};
    padding: 0 1;
    height: auto;
}}

.metric-title {{
    color: {accent};
    text-style: bold;
    padding: 0 0 0 0;
    margin: 0 0 0 0;
}}

.metric-bar-row {{
    height: 1;
    layout: horizontal;
    margin: 0 0 0 0;
}}

.metric-value {{
    color: {text};
    min-width: 8;
    padding: 0 0 0 1;
}}

.metric-detail {{
    color: {text};
    padding: 0 0 0 0;
    margin: 0 0 0 0;
}}

.metric-graph {{
    color: {graph};
    padding: 0 0 0 0;
    margin: 0 0 0 0;
}}

ProgressBar {{
    width: 1fr;
    color: {bar};
    background: {bg};
}}

ProgressBar > .bar {{
    color: {bar};
}}

Header {{
    background: {bg};
    color: {accent};
    text-style: bold;
}}

Footer {{
    background: {bg};
    color: {dim};
}}

#proc-filter {{
    display: none;
    margin: 0 0 0 0;
    padding: 0 0 0 0;
}}

.inspect-modal-container {{
    width: 85%;
    height: 85%;
    background: {card};
    border: solid {accent};
    padding: 1 2;
    align: center middle;
}}

#modal-title {{
    color: {accent};
    text-style: bold;
    margin-bottom: 1;
}}

#modal-tabs-bar {{
    height: 3;
    margin-bottom: 1;
}}

#modal-tabs-bar Button {{
    margin-right: 1;
    min-width: 12;
}}

#modal-body-scroll {{
    height: 1fr;
    background: {bg};
    border: solid {border};
    padding: 1;
}}

#modal-footer {{
    color: {dim};
    margin-top: 1;
}}
"""
