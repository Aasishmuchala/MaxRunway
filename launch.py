import sys
from pathlib import Path

root = str(Path(__file__).resolve().parent)
if root not in sys.path:
    sys.path.insert(0, root)
from maxrunway.ui import show
show()
