"""STEP 1 of SnapTrade setup: register your SnapTrade end-user.

Requires SNAPTRADE_CLIENT_ID and SNAPTRADE_CONSUMER_KEY in .env.
Prints a userId + userSecret; copy BOTH into .env. The userSecret is shown
only once and cannot be recovered (only reset).

Usage:  .venv/bin/python scripts/register_snaptrade_user.py [user_id]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_sources.snaptrade.auth import register_user


def main():
    user_id = sys.argv[1] if len(sys.argv) > 1 else "portfolio-user"
    secret = register_user(user_id)
    print("\nSnapTrade user registered. Save these to your .env:\n")
    print(f"SNAPTRADE_USER_ID={user_id}")
    print(f"SNAPTRADE_USER_SECRET={secret}")
    print("\n(The userSecret cannot be retrieved again; store it now.)\n")


if __name__ == "__main__":
    main()
