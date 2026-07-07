"""SnapTrade user registration + brokerage connection portal.

One-time setup flow:
  1. register_user(user_id)      -> returns userSecret (save to .env)
  2. connection_portal_url(...)  -> open in browser, log into Robinhood (OAuth)
Once connected, SnapTrade syncs ALL accounts under that login (brokerage + IRA).
"""

from .client import get_client


def register_user(user_id: str) -> str:
    """Create a SnapTrade end-user. Returns the userSecret (store it securely)."""
    client = get_client()
    resp = client.authentication.register_snap_trade_user(body={"userId": user_id})
    return resp.body["userSecret"]


def connection_portal_url(user_id: str, user_secret: str) -> str:
    """Return a one-time URL to launch the brokerage connection portal."""
    client = get_client()
    resp = client.authentication.login_snap_trade_user(
        query_params={"userId": user_id, "userSecret": user_secret}
    )
    body = resp.body
    # body is either a dict with redirectURI or the URL string itself.
    if isinstance(body, dict):
        return body.get("redirectURI") or body.get("redirect_uri") or str(body)
    return str(body)
