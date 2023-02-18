import __main__
from pathlib import Path

def resource_path(relative_path: str) -> Path:
    """
    Get absolute path to resource, works for dev and for PyInstaller.

    source: https://stackoverflow.com/a/13790741/19634396
    """
    try:
        # PyInstaller creates a temporary folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__main__.__file__).parent.resolve()
    return Path(base_path, relative_path)