"""Tests for Sprint 9 — theme system, graph styles, layout."""

import sys
from pathlib import Path
from unittest.mock import patch
import pytest


class TestThemeEngine:
    def test_list_themes_returns_list(self):
        from visage.theme import list_themes
        themes = list_themes()
        assert isinstance(themes, list)
        assert "default" in themes

    def test_get_default_theme(self):
        from visage.theme import get_default_theme
        theme = get_default_theme()
        assert theme.name == "default"
        assert theme.display_name == "Tokyo Night"
        assert "bg" in theme.colors

    def test_get_theme_by_name(self):
        from visage.theme import get_theme
        theme = get_theme("dracula")
        assert theme is not None
        assert theme.display_name == "Dracula"
        assert theme.colors.get("bg") == "#282a36"

    def test_get_theme_nonexistent(self):
        from visage.theme import get_theme
        theme = get_theme("nonexistent_theme")
        assert theme is None

    def test_all_builtin_themes_have_required_fields(self):
        from visage.theme import list_themes, get_theme
        for name in list_themes():
            theme = get_theme(name)
            assert theme is not None
            assert theme.name == name
            assert "bg" in theme.colors
            assert "card" in theme.colors
            assert "accent" in theme.colors
            assert "text" in theme.colors

    def test_generate_tcss(self):
        from visage.theme import get_default_theme, generate_tcss
        theme = get_default_theme()
        tcss = generate_tcss(theme)
        assert "Screen {" in tcss
        assert theme.colors.get("bg", "#1a1b26") in tcss
        assert ".metric-card {" in tcss

    def test_load_custom_theme(self):
        from visage.theme import load_custom_theme
        import tempfile
        content = """
[meta]
display_name = "Custom Test"
graph_style = "block"

[colors]
bg = "#000000"
card = "#111111"
border = "#222222"
accent = "#ffffff"
text = "#cccccc"
graph = "#aaaaaa"
dim = "#555555"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(content)
            f.flush()
            theme = load_custom_theme(f.name)
            assert theme is not None
            assert theme.display_name == "Custom Test"
            assert theme.graph_style == "block"
            assert theme.colors["bg"] == "#000000"
            Path(f.name).unlink()

    def test_load_custom_theme_invalid(self):
        from visage.theme import load_custom_theme
        theme = load_custom_theme("/nonexistent/path.toml")
        assert theme is None


class TestGraphStyle:
    def test_detect_ascii_fallback_ssh(self):
        from visage.util import detect_ascii_fallback
        with patch.dict("os.environ", {"SSH_CONNECTION": "1.2.3.4", "TERM": "xterm-256color"}):
            assert detect_ascii_fallback() is True

    def test_detect_ascii_fallback_linux_term(self):
        from visage.util import detect_ascii_fallback
        with patch.dict("os.environ", {"TERM": "linux", "LANG": "C"}):
            assert detect_ascii_fallback() is True

    def test_detect_ascii_fallback_no_utf(self):
        from visage.util import detect_ascii_fallback
        with patch.dict("os.environ", {"LANG": "C.UTF-8"}):
            assert detect_ascii_fallback() is False

    def test_get_graph_style_auto_fallback(self):
        from visage.util import get_graph_style
        with patch("visage.util.detect_ascii_fallback", return_value=True):
            assert get_graph_style("auto") == "ascii"

    def test_get_graph_style_block_unchanged(self):
        from visage.util import get_graph_style
        assert get_graph_style("block") == "block"

    def test_get_graph_style_braille_no_fallback(self):
        from visage.util import get_graph_style
        with patch("visage.util.detect_ascii_fallback", return_value=False):
            assert get_graph_style("braille") == "braille"


class TestConfigTheme:
    def test_config_defaults(self):
        from visage.config import VisageConfig
        cfg = VisageConfig()
        assert cfg.theme == "default"
        assert cfg.graph_style == "braille"

    def test_config_loads_theme(self):
        from visage.config import load_config
        import tempfile, json
        config = {"theme": "dracula", "graph_style": "block"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            cfg = load_config(f.name)
            assert cfg.theme == "dracula"
            assert cfg.graph_style == "block"
            Path(f.name).unlink()
