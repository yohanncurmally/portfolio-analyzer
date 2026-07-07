"""SnapTrade client + credentials, loaded from environment."""

import os

from dotenv import load_dotenv
from snaptrade_client import SnapTrade

load_dotenv()


def get_client() -> SnapTrade:
    client_id = os.getenv("SNAPTRADE_CLIENT_ID")
    consumer_key = os.getenv("SNAPTRADE_CONSUMER_KEY")
    if not client_id or not consumer_key:
        raise RuntimeError(
            "Missing SNAPTRADE_CLIENT_ID / SNAPTRADE_CONSUMER_KEY. "
            "Copy .env.example to .env and fill them in from the SnapTrade dashboard."
        )
    return SnapTrade(consumer_key=consumer_key, client_id=client_id)


def get_user_creds() -> tuple[str, str]:
    user_id = os.getenv("SNAPTRADE_USER_ID")
    user_secret = os.getenv("SNAPTRADE_USER_SECRET")
    if not user_id or not user_secret:
        raise RuntimeError(
            "Missing SNAPTRADE_USER_ID / SNAPTRADE_USER_SECRET. "
            "Run scripts/register_snaptrade_user.py first, then save the values to .env."
        )
    return user_id, user_secret
