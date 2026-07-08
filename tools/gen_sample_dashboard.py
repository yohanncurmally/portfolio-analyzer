"""Regenerate the sample dashboard image used in the README.

This is a DEV/DOCS utility, not part of the read-only product surface. It renders
the real pipeline against the fabricated demo portfolio (data_sources/demo), so the
README image is exactly what a user sees from:

    python scripts/analyze.py --source demo

Nothing here is a real portfolio. It runs offline (the demo supplies its own spot
prices) and uses pure-stdlib enrichment plus the HTML dashboard, so it needs no
third-party packages.

Two steps:

  1. Emit the HTML (this script):
       python tools/gen_sample_dashboard.py
     Writes docs/sample-dashboard.html (gitignored) and prints the screenshot command.

  2. Screenshot it to PNG with any Chromium-based browser (Chrome, Brave, Edge,
     Chromium). Example:
       "<browser>" --headless=new --disable-gpu --hide-scrollbars \
         --force-device-scale-factor=2 --window-size=1440,2560 \
         --screenshot=docs/sample-dashboard.png \
         "file://$PWD/docs/sample-dashboard.html"

Only docs/sample-dashboard.png is committed. Regenerate it after any change to the
dashboard layout or the demo data so the README stays in sync.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from analysis import dashboard_html  # noqa: E402
from analysis.enrich import enrich  # noqa: E402
from data_sources.demo.portfolio import SPOTS, fetch_snapshot  # noqa: E402


def main() -> None:
    snap = fetch_snapshot()
    es = enrich(snap, spots=SPOTS)
    out_html = _ROOT / "docs" / "sample-dashboard.html"
    out_png = _ROOT / "docs" / "sample-dashboard.png"
    dashboard_html.render(es, str(out_html))
    print(f"wrote {out_html.relative_to(_ROOT)}")
    print("\nNow screenshot it with any Chromium-based browser, e.g.:\n")
    print('  "<browser>" --headless=new --disable-gpu --hide-scrollbars \\\n'
          '    --force-device-scale-factor=2 --window-size=1440,2560 \\\n'
          f'    --screenshot={out_png.relative_to(_ROOT)} \\\n'
          f'    "file://{out_html}"\n')


if __name__ == "__main__":
    main()
