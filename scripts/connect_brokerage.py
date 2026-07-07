"""STEP 2 of SnapTrade setup: connect Robinhood (read-only OAuth).

Requires SNAPTRADE_USER_ID + SNAPTRADE_USER_SECRET in .env (from step 1).
Prints a one-time connection-portal URL. Open it in your browser, choose
Robinhood, and authenticate. SnapTrade then syncs ALL accounts under that
login — your taxable brokerage AND your IRA.

Usage:  .venv/bin/python scripts/connect_brokerage.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_sources.snaptrade.auth import connection_portal_url
from data_sources.snaptrade.client import get_user_creds


def main():
    user_id, user_secret = get_user_creds()
    url = connection_portal_url(user_id, user_secret)
    print("\nOpen this URL in your browser to connect Robinhood (read-only):\n")
    print(url)
    print("\nAfter connecting, run:  .venv/bin/python scripts/pull_snapshot.py\n")


if __name__ == "__main__":
    main()
