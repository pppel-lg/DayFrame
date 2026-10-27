"""PyInstaller entry; preserve package-relative imports in the real backend."""
from backend.dayframe.desktop_entry import main

if __name__ == '__main__':
    raise SystemExit(main())
