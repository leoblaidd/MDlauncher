"""Executa o MD Launcher (usado também pelo PyInstaller)."""
import sys

from mdlauncher.app import main

if __name__ == "__main__":
    sys.exit(main())
