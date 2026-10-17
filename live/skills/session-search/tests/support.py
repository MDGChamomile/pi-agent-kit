"""Load the standalone CLI scripts through Python's shared module cache."""
from pathlib import Path
import sys

SCRIPTS = Path(__file__).parents[1] / "scripts"
SEARCH_SCRIPT = SCRIPTS / "session_search.py"
RECALL_SCRIPT = SCRIPTS / "session_recall.py"
sys.path.insert(0, str(SCRIPTS))

import session_search
import session_recall
