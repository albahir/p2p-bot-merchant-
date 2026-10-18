"""Tests unitarios (TDD) para el motor de temas y tokens de diseño Stitch (SPEC-013)."""

from src.reporting.dashboard.theme import (
    STITCH_TOKENS,
    get_stitch_css,
    render_status_badge,
)


def test_stitch_tokens_palette():
    assert "bg_dark" in STITCH_TOKENS
    assert STITCH_TOKENS["bg_dark"] == "#0B0E14"
    assert "emerald" in STITCH_TOKENS
    assert STITCH_TOKENS["emerald"] == "#10B981"
    assert "ruby" in STITCH_TOKENS
    assert STITCH_TOKENS["ruby"] == "#F43F5E"
    assert "cyan" in STITCH_TOKENS
    assert STITCH_TOKENS["cyan"] == "#06B6D4"


def test_get_stitch_css_contains_glassmorphism_rules():
    css = get_stitch_css()
    assert isinstance(css, str)
    assert "#0B0E14" in css
    assert "backdrop-filter" in css
    assert ".fintech-card" in css
    assert ".terminal-header" in css
    assert ".badge-pill" in css
    assert "tabular-nums" in css


def test_render_status_badge():
    badge_green = render_status_badge("BALANCED", variant="success")
    assert "badge-success" in badge_green
    assert "BALANCED" in badge_green

    badge_red = render_status_badge("DISCREPANCY", variant="danger")
    assert "badge-danger" in badge_red
    assert "DISCREPANCY" in badge_red

    badge_matched = render_status_badge("MATCHED", variant="matched")
    assert "badge-matched" in badge_matched
