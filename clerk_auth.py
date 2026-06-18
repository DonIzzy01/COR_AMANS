"""
Clerk Authentication for COR AMANS
===================================
Handles JWT verification, webhook signature checking, and DB user sync.

Activate by adding to .env:
  CLERK_PUBLISHABLE_KEY=pk_test_...
  CLERK_SECRET_KEY=sk_test_...
  CLERK_WEBHOOK_SECRET=whsec_...
"""

import base64
import hashlib
import hmac
import json

import requests
from flask import current_app
from flask_login import login_user

try:
    import jwt as pyjwt
    from jwt.algorithms import RSAAlgorithm
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False


def is_clerk_enabled():
    return current_app.config.get('CLERK_ENABLED', False)


def _frontend_api_from_key(publishable_key: str) -> str:
    """
    Clerk publishable keys encode the frontend API as base64url.
    pk_test_<base64url(frontend-api$)>  →  frontend-api
    """
    stripped = (
        publishable_key
        .replace('pk_test_', '')
        .replace('pk_live_', '')
    )
    # Base64url decode (add padding as needed)
    padding = 4 - len(stripped) % 4
    padded = stripped + ('=' * (padding % 4))
    try:
        decoded = base64.urlsafe_b64decode(padded).decode('utf-8').rstrip('$')
        return decoded
    except Exception:
        return ''


def get_clerk_jwks():
    """
    Fetch Clerk's JSON Web Key Set for JWT verification.
    Supports an optional CLERK_JWKS_URL override in config.
    """
    # Allow explicit override in .env for unusual setups
    jwks_url = current_app.config.get('CLERK_JWKS_URL', '')
    if not jwks_url:
        key = current_app.config.get('CLERK_PUBLISHABLE_KEY', '')
        frontend_api = _frontend_api_from_key(key)
        if not frontend_api:
            return None
        jwks_url = f"https://{frontend_api}/.well-known/jwks.json"

    try:
        resp = requests.get(jwks_url, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def verify_clerk_session_token(token: str) -> dict | None:
    """
    Verify a Clerk session JWT.
    Returns the decoded payload dict, or None on failure.
    """
    if not JWT_AVAILABLE or not token:
        return None

    try:
        header = pyjwt.get_unverified_header(token)
        kid = header.get('kid')
        jwks = get_clerk_jwks()
        if not jwks:
            return None

        for key_data in jwks.get('keys', []):
            if key_data.get('kid') == kid:
                public_key = RSAAlgorithm.from_jwk(json.dumps(key_data))
                payload = pyjwt.decode(
                    token,
                    public_key,
                    algorithms=['RS256'],
                    options={"verify_aud": False},
                )
                return payload
    except Exception:
        pass
    return None


def verify_clerk_webhook(
    payload_bytes: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
) -> bool:
    """
    Verify a Clerk webhook using the HMAC-SHA256 svix signature.
    """
    secret = current_app.config.get('CLERK_WEBHOOK_SECRET', '')
    if not secret:
        return False

    try:
        # Strip "whsec_" prefix and base64-decode the signing key
        secret_bytes = base64.b64decode(secret.replace('whsec_', ''))
        signed_content = f"{svix_id}.{svix_timestamp}.{payload_bytes.decode('utf-8')}"
        expected = base64.b64encode(
            hmac.new(secret_bytes, signed_content.encode(), hashlib.sha256).digest()
        ).decode()

        for sig in svix_signature.split(' '):
            if sig.startswith('v1,') and hmac.compare_digest(sig[3:], expected):
                return True
    except Exception:
        pass
    return False


def sync_clerk_user_to_db(clerk_payload: dict, db, User) -> 'User | None':
    """
    Create or update a local User from a Clerk JWT payload or webhook data.
    Returns the User, or None on error.
    """
    clerk_user_id = clerk_payload.get('sub') or clerk_payload.get('id')
    email = None

    # Clerk JWTs put primary email in email_addresses list
    for addr in clerk_payload.get('email_addresses', []):
        if addr.get('id') == clerk_payload.get('primary_email_address_id'):
            email = addr.get('email_address')
            break
    # Fallback for flat payloads
    if not email:
        email = clerk_payload.get('email_address') or clerk_payload.get('email', '')

    if not email or not clerk_user_id:
        return None

    email = email.lower()

    # Look up by Clerk ID first, then by email
    user = User.query.filter_by(clerk_user_id=clerk_user_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()

    if not user:
        import secrets as _sec
        user = User(
            email=email,
            clerk_user_id=clerk_user_id,
            is_paid=False,
            is_admin=False,
            email_verified=True,
        )
        user.set_password(_sec.token_urlsafe(32))   # unusable password; auth via Clerk
        db.session.add(user)

        first = clerk_payload.get('first_name', '')
        last  = clerk_payload.get('last_name', '')
        if first:
            user.bride_first_name = first
            user.bride_last_name  = last
            user.bride_email      = email
    else:
        if not user.clerk_user_id:
            user.clerk_user_id = clerk_user_id
        user.email_verified = True

    try:
        db.session.commit()
        user.ensure_registration_number()
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None

    return user
