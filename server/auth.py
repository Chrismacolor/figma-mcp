import os
import secrets
import sys

from fastapi import Header, HTTPException

_auth_token: str | None = None


def init_auth_token() -> str:
    global _auth_token
    _auth_token = os.environ.get("FIGMA_MCP_TOKEN") or secrets.token_urlsafe(32)
    source = "env" if os.environ.get("FIGMA_MCP_TOKEN") else "generated"
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  Auth token ({source}): {_auth_token}", file=sys.stderr)
    print(f"  Paste this into the Figma plugin to connect.", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
    return _auth_token


def get_auth_token() -> str:
    if _auth_token is None:
        raise RuntimeError("Auth token not initialized. Call init_auth_token() first.")
    return _auth_token


async def require_auth(authorization: str = Header(...)) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    if token != get_auth_token():
        raise HTTPException(status_code=401, detail="Invalid auth token")
    return token
