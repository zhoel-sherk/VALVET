"""Helper functions for QFileDialog with last directory persistence.

This module provides wrapper functions for QFileDialog that automatically
save and restore the last used directory via QSettings.
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6 import QtCore, QtWidgets


def open_file_dialog(
    parent: Optional[QtWidgets.QWidget],
    title: str,
    filter: str,
    *,
    settings: Optional[QtCore.QSettings] = None,
    history_key: Optional[str] = None,
) -> tuple[str, str]:
    """Open file dialog with automatic last directory persistence.

    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        filter: File filter string (e.g., "Excel Files (*.xlsx);;All Files (*)")
        settings: QSettings instance for persistence (optional)
        history_key: Key to use in QSettings for storing last directory (optional)

    Returns:
        Tuple of (selected_file_path, selected_filter)
    """
    start_dir = ""
    if settings and history_key:
        start_dir = str(settings.value(history_key, "") or "")

    path, selected_filter = QtWidgets.QFileDialog.getOpenFileName(
        parent, title, start_dir, filter
    )

    if path and settings and history_key:
        settings.setValue(history_key, os.path.dirname(path))

    return path, selected_filter


def save_file_dialog(
    parent: Optional[QtWidgets.QWidget],
    title: str,
    filter: str,
    *,
    settings: Optional[QtCore.QSettings] = None,
    history_key: Optional[str] = None,
    default_name: Optional[str] = None,
) -> tuple[str, str]:
    """Save file dialog with automatic last directory persistence.

    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        filter: File filter string (e.g., "Excel Files (*.xlsx);;All Files (*)")
        settings: QSettings instance for persistence (optional)
        history_key: Key to use in QSettings for storing last directory (optional)
        default_name: Default file name to suggest (optional)

    Returns:
        Tuple of (selected_file_path, selected_filter)
    """
    start_dir = ""
    if settings and history_key:
        start_dir = str(settings.value(history_key, "") or "")

    if default_name and start_dir:
        start_dir = os.path.join(start_dir, default_name)
    elif default_name:
        start_dir = default_name

    path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
        parent, title, start_dir, filter
    )

    if path and settings and history_key:
        settings.setValue(history_key, os.path.dirname(path))

    return path, selected_filter


def directory_dialog(
    parent: Optional[QtWidgets.QWidget],
    title: str,
    *,
    settings: Optional[QtCore.QSettings] = None,
    history_key: Optional[str] = None,
) -> str:
    """Directory selection dialog with automatic last directory persistence.

    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        settings: QSettings instance for persistence (optional)
        history_key: Key to use in QSettings for storing last directory (optional)

    Returns:
        Selected directory path (empty string if cancelled)
    """
    start_dir = ""
    if settings and history_key:
        start_dir = str(settings.value(history_key, "") or "")

    path = QtWidgets.QFileDialog.getExistingDirectory(parent, title, start_dir)

    if path and settings and history_key:
        settings.setValue(history_key, path)

    return path
