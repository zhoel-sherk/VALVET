from __future__ import annotations

from themes.segmented import segmented_qss


def test_segmented_qss_has_checked_border() -> None:
    qss = segmented_qss()
    assert "QWidget#segmented" in qss
    assert ":checked" in qss
    assert "border:" in qss


def test_extra_stylesheet_includes_segmented() -> None:
    from themes import extra_application_stylesheet

    extra = extra_application_stylesheet()
    assert "QWidget#segmented" in extra
    assert "QPushButton:checked" in extra


def _qapp():
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_segmented_control_exclusive_and_stretch() -> None:
    from PySide6.QtWidgets import QSizePolicy

    from ui.chrome import segmented_control

    _qapp()
    frame, group, buttons = segmented_control(("Auto", "mm", "mil", "inch"))
    assert frame.objectName() == "segmented"
    assert len(buttons) == 4
    assert group.exclusive()
    for btn in buttons:
        pol = btn.sizePolicy()
        assert pol.horizontalPolicy() == QSizePolicy.Policy.Expanding
        assert frame.layout().stretch(frame.layout().indexOf(btn)) == 1
    buttons[0].setChecked(True)
    buttons[2].setChecked(True)
    assert buttons[2].isChecked()
    assert not buttons[0].isChecked()
    assert not buttons[1].isChecked()
    assert not buttons[3].isChecked()
    assert buttons[0].property("seg") == "first"
    assert buttons[1].property("seg") == "mid"
    assert buttons[3].property("seg") == "last"


def test_pcb_preview_gerber_segments(tmp_path) -> None:
    from PySide6 import QtCore
    from PySide6.QtWidgets import QSizePolicy

    from pcb_preview_tab import PcbPreviewTab

    _qapp()
    settings = QtCore.QSettings(
        str(tmp_path / "t.ini"), QtCore.QSettings.Format.IniFormat
    )
    tab = PcbPreviewTab(settings=settings)
    try:
        segs = (
            tab._rb_g_auto,
            tab._rb_g_mm,
            tab._rb_g_mils,
            tab._rb_g_in,
        )
        assert len(segs) == 4
        for b in segs:
            assert b.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
        tab._rb_g_mils.setChecked(True)
        assert tab._gerber_unit_mode() == "mils"
        assert not tab._rb_g_auto.isChecked()
        assert not tab._rb_g_mm.isChecked()
        assert not tab._rb_g_in.isChecked()
        assert tab._rb_pnp_xy_mm.isChecked()
        tab._rb_pnp_xy_mils.setChecked(True)
        assert tab._rb_pnp_xy_mils.isChecked()
        assert not tab._rb_pnp_xy_mm.isChecked()
    finally:
        tab.close()
