"""Pull a live portfolio snapshot (all connected accounts) and analyze it.

Usage:
  .venv/bin/python scripts/pull_snapshot.py            # pull + print analysis
  .venv/bin/python scripts/pull_snapshot.py --debug    # also dump raw API bodies
  .venv/bin/python scripts/pull_snapshot.py --json-only # save JSON, no report
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.portfolio import report
from data_sources.snaptrade.portfolio import fetch_snapshot

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"


def main():
    debug = "--debug" in sys.argv
    json_only = "--json-only" in sys.argv

    snap = fetch_snapshot(debug=debug)

    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"snapshot_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(snap.to_dict(), indent=2, default=str))

    if not json_only:
        report(snap)
    print(f"Saved snapshot -> {path.relative_to(OUTPUT_DIR.parent)}\n")


if __name__ == "__main__":
    main()
