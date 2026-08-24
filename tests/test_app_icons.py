"""Application icon files exist for Win/Linux packaging."""

from app.icons import application_icon_path, repo_root


def test_icon_assets_exist():
    img = repo_root() / "img"
    assert (img / "icon.svg").is_file()
    assert (img / "readme.svg").is_file()
    assert (img / "icon.ico").is_file()
    assert (img / "icon-256.png").is_file()
    assert (img / "icon-512.png").is_file()
    p = application_icon_path()
    assert p is not None and p.is_file()
