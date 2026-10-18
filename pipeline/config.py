"""Project paths and fixed constants shared by every stage."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"          # Local state (SQLite); gitignored.
REPORTS = ROOT / "reports"    # Human-readable stage reports; committed.
GRADING = ROOT / "grading"
COST = ROOT / "cost"
PROMPTS = ROOT / "prompts"
MANIFEST = ROOT / "manifest.json"
LEDGER_DB = WORK / "ledger.sqlite"   # One spend ledger for every run in the project.
DEFAULT_STORE = WORK / "store.sqlite"

# The professor's checker defines the CSV parser and row hash; import it so ours can never drift.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FULL_INPUT_SHA256 = "1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6"

# Declared full-corpus scope from GRADING_CONTRACT.md / COST_CALCULATOR.md.
FULL_SCOPE = {"records": 660622, "nonempty": 660609, "empty_review_text": 13, "distinct_nonempty_texts": 484189}

EMPTY_REASON = "empty_review_text"
MAX_REVIEWS_PER_REQUEST = 50         # Contract limit for enrichment requests.
# Model allowlist: every request reserves spend through rates.worst_case(), which refuses any other model.
MODEL_ALLOWLIST = frozenset({("typesafe", "jev-1.13.0"), ("anthropic", "claude-haiku-5-5")})
