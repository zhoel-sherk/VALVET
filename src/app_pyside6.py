"""Deprecated import path. Use src/main.py to launch; MainWindow lives in app.window."""
from app.window import MainWindow
from main import main

__all__ = ["MainWindow", "main"]

if __name__ == "__main__":
    main()
