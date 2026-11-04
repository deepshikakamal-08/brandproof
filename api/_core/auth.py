"""Signed session tokens and organisation-scoped access.

Every API request (except health and session creation) carries
`Authorization: Bearer <token>`. The token names the user and organisation;
every query is filtered by that org_id, so one customer can never read
another customer's guidelines or drafts.
"""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException

from . import db

SECRET = os.getenv("SECRET_KEY", "dev-only-change-me")
ROLES = ["creator", "manager", "reviewer", "admin"]
TTL = 7 * 24 * 3600


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign(user_id, org_id):
    payload = _b64(json.dumps({"u": user_id, "o": org_id, "exp": int(time.time()) + TTL}).encode())
    sig = _b64(hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify(token):
    try:
        payload, sig = token.split(".")
        good = _b64(hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(_unb64(payload))
        if data["exp"] < time.time():
            return None
        return data
    except Exception:
        return None


def current(authorization: str = Header(default="")):
    """FastAPI dependency: returns {user_id, org_id, role, name}."""
    token = authorization.removeprefix("Bearer ").strip()
    data = verify(token) if token else None
    if not data:
        raise HTTPException(401, "Sign in again: your session is missing or expired.")
    m = db.one("SELECT m.role, u.name FROM members m JOIN users u ON u.id = m.user_id "
               "WHERE m.user_id = ? AND m.org_id = ?", (data["u"], data["o"]))
    if not m:
        raise HTTPException(401, "This workspace no longer exists. Start a new demo.")
    return {"user_id": data["u"], "org_id": data["o"], "role": m["role"], "name": m["name"]}


def require(user, *roles):
    if user["role"] not in roles:
        raise HTTPException(403, f"Only {' or '.join(roles)} can do this. Switch role in the top bar.")
