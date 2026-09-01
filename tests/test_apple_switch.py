from __future__ import annotations

from themes.apple_switch import assets_dir, switch_qss


def test_switch_svg_assets_exist() -> None:
    d = assets_dir()
    for name in (
        "switch_off.svg",
        "switch_on.svg",
        "switch_hovered.svg",
        "switch_on_hovered.svg",
        "switch_off_disabled.svg",
        "switch_on_disabled.svg",
    ):
        p = d / name
        assert p.is_file(), name
        assert p.stat().st_size > 40
        text = p.read_text(encoding="utf-8")
        assert "<svg" in text
        assert "rect" in text


def test_switch_qss_targets_checkbox_indicator() -> None:
    qss = switch_qss()
    assert "QCheckBox::indicator" in qss
    assert "switch_off.svg" in qss
    assert "switch_on.svg" in qss
    assert "switch_hovered.svg" in qss
    assert "indicator:hover" in qss
    assert "indicator:focus" in qss
    assert "width: 36px" in qss


def test_extra_stylesheet_includes_switch_not_valvet_id() -> None:
    from themes import extra_application_stylesheet

    extra = extra_application_stylesheet()
    assert "QCheckBox::indicator" in extra
    assert "switch_off.svg" in extra
    assert "valvetSwitch" not in extra
    assert "QWidget#segmented" in extra
