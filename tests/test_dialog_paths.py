"""Tests for ui.dialog_paths module."""

import os
from unittest.mock import patch

from PySide6 import QtCore

from ui.dialog_paths import (
    directory_dialog,
    open_file_dialog,
    save_file_dialog,
)


class TestOpenFileDialog:
    """Tests for open_file_dialog function."""

    def test_open_file_dialog_without_settings(self, qtbot):
        """Test dialog works without settings (no persistence)."""
        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getOpenFileName"
        ) as mock_dialog:
            mock_dialog.return_value = ("/path/to/file.txt", "Text Files (*.txt)")

            path, selected = open_file_dialog(None, "Open File", "Text Files (*.txt)")

            assert path == "/path/to/file.txt"
            assert selected == "Text Files (*.txt)"
            mock_dialog.assert_called_once_with(
                None, "Open File", "", "Text Files (*.txt)"
            )

    def test_open_file_dialog_with_settings(self, qtbot, tmp_path):
        """Test dialog saves last directory to settings."""
        settings = QtCore.QSettings(
            str(tmp_path / "test.ini"), QtCore.QSettings.Format.IniFormat
        )
        history_key = "test/last_dir"

        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getOpenFileName"
        ) as mock_dialog:
            mock_dialog.return_value = ("/selected/dir/file.txt", "All Files (*)")

            path, selected = open_file_dialog(
                None,
                "Open File",
                "All Files (*)",
                settings=settings,
                history_key=history_key,
            )

            assert path == "/selected/dir/file.txt"
            assert settings.value(history_key) == "/selected/dir"

    def test_open_file_dialog_restores_last_dir(self, qtbot, tmp_path):
        """Test dialog restores last directory from settings."""
        settings = QtCore.QSettings(
            str(tmp_path / "test.ini"), QtCore.QSettings.Format.IniFormat
        )
        history_key = "test/last_dir"
        settings.setValue(history_key, "/previous/dir")

        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getOpenFileName"
        ) as mock_dialog:
            mock_dialog.return_value = ("", "")

            open_file_dialog(
                None,
                "Open File",
                "All Files (*)",
                settings=settings,
                history_key=history_key,
            )

            # Verify dialog was called with the saved directory
            call_args = mock_dialog.call_args
            assert call_args[0][2] == "/previous/dir"

    def test_open_file_dialog_cancelled(self, qtbot, tmp_path):
        """Test dialog doesn't save when cancelled."""
        settings = QtCore.QSettings(
            str(tmp_path / "test.ini"), QtCore.QSettings.Format.IniFormat
        )
        history_key = "test/last_dir"
        settings.setValue(history_key, "/old/dir")

        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getOpenFileName"
        ) as mock_dialog:
            mock_dialog.return_value = ("", "")  # User cancelled

            path, selected = open_file_dialog(
                None,
                "Open File",
                "All Files (*)",
                settings=settings,
                history_key=history_key,
            )

            assert path == ""
            assert selected == ""
            # Old value should remain unchanged
            assert settings.value(history_key) == "/old/dir"


class TestSaveFileDialog:
    """Tests for save_file_dialog function."""

    def test_save_file_dialog_without_settings(self, qtbot):
        """Test dialog works without settings."""
        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getSaveFileName"
        ) as mock_dialog:
            mock_dialog.return_value = ("/path/to/save.txt", "Text Files (*.txt)")

            path, selected = save_file_dialog(None, "Save File", "Text Files (*.txt)")

            assert path == "/path/to/save.txt"
            assert selected == "Text Files (*.txt)"

    def test_save_file_dialog_with_settings(self, qtbot, tmp_path):
        """Test dialog saves last directory to settings."""
        settings = QtCore.QSettings(
            str(tmp_path / "test.ini"), QtCore.QSettings.Format.IniFormat
        )
        history_key = "test/save_dir"

        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getSaveFileName"
        ) as mock_dialog:
            mock_dialog.return_value = ("/save/dir/output.txt", "All Files (*)")

            path, selected = save_file_dialog(
                None,
                "Save File",
                "All Files (*)",
                settings=settings,
                history_key=history_key,
            )

            assert path == "/save/dir/output.txt"
            assert settings.value(history_key) == "/save/dir"

    def test_save_file_dialog_with_default_name(self, qtbot, tmp_path):
        """Test dialog uses default name when provided."""
        settings = QtCore.QSettings(
            str(tmp_path / "test.ini"), QtCore.QSettings.Format.IniFormat
        )
        history_key = "test/save_dir"
        settings.setValue(history_key, "/saved/dir")

        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getSaveFileName"
        ) as mock_dialog:
            mock_dialog.return_value = ("/saved/dir/output.txt", "Text Files (*.txt)")

            save_file_dialog(
                None,
                "Save File",
                "Text Files (*.txt)",
                settings=settings,
                history_key=history_key,
                default_name="output.txt",
            )

            # Verify dialog was called with directory + default name
            call_args = mock_dialog.call_args
            assert call_args[0][2] == os.path.join("/saved/dir", "output.txt")

    def test_save_file_dialog_with_default_name_no_history(self, qtbot):
        """Test dialog uses default name when no history exists."""
        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getSaveFileName"
        ) as mock_dialog:
            mock_dialog.return_value = ("output.txt", "Text Files (*.txt)")

            save_file_dialog(
                None,
                "Save File",
                "Text Files (*.txt)",
                default_name="output.txt",
            )

            call_args = mock_dialog.call_args
            assert call_args[0][2] == "output.txt"


class TestDirectoryDialog:
    """Tests for directory_dialog function."""

    def test_directory_dialog_without_settings(self, qtbot):
        """Test dialog works without settings."""
        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getExistingDirectory"
        ) as mock_dialog:
            mock_dialog.return_value = "/selected/directory"

            path = directory_dialog(None, "Select Directory")

            assert path == "/selected/directory"

    def test_directory_dialog_with_settings(self, qtbot, tmp_path):
        """Test dialog saves last directory to settings."""
        settings = QtCore.QSettings(
            str(tmp_path / "test.ini"), QtCore.QSettings.Format.IniFormat
        )
        history_key = "test/dir_path"

        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getExistingDirectory"
        ) as mock_dialog:
            mock_dialog.return_value = "/new/directory"

            path = directory_dialog(
                None,
                "Select Directory",
                settings=settings,
                history_key=history_key,
            )

            assert path == "/new/directory"
            assert settings.value(history_key) == "/new/directory"

    def test_directory_dialog_restores_last_dir(self, qtbot, tmp_path):
        """Test dialog restores last directory from settings."""
        settings = QtCore.QSettings(
            str(tmp_path / "test.ini"), QtCore.QSettings.Format.IniFormat
        )
        history_key = "test/dir_path"
        settings.setValue(history_key, "/previous/dir")

        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getExistingDirectory"
        ) as mock_dialog:
            mock_dialog.return_value = ""

            directory_dialog(
                None,
                "Select Directory",
                settings=settings,
                history_key=history_key,
            )

            call_args = mock_dialog.call_args
            assert call_args[0][2] == "/previous/dir"

    def test_directory_dialog_cancelled(self, qtbot, tmp_path):
        """Test dialog doesn't save when cancelled."""
        settings = QtCore.QSettings(
            str(tmp_path / "test.ini"), QtCore.QSettings.Format.IniFormat
        )
        history_key = "test/dir_path"
        settings.setValue(history_key, "/old/dir")

        with patch(
            "ui.dialog_paths.QtWidgets.QFileDialog.getExistingDirectory"
        ) as mock_dialog:
            mock_dialog.return_value = ""  # User cancelled

            path = directory_dialog(
                None,
                "Select Directory",
                settings=settings,
                history_key=history_key,
            )

            assert path == ""
            assert settings.value(history_key) == "/old/dir"
