"""
Clerk Authentication Scaffold for COR AMANS
============================================
This module scaffolds Clerk integration for when you are ready to activate it.

HOW TO ACTIVATE:
  1. Create a Clerk project at https://clerk.com
  2. Copy your Publishable Key and Secret Key
  3. Add them to your .env file:
       CLERK_PUBLISHABLE_KEY=pk_test_...
       CLERK_SECRET_KEY=sk_test_...
  4. Set up a webhook in your Clerk dashboard pointing to:
       https://your-domain.com/clerk/webhook
  5. Add the webhook secret to .env:
       CLERK_WEBHOOK_SECRET=whsec_...

FLOW (when CLERK_ENABLED=True):
  - Login/register pages show Clerk's sign-in/sign-up components
  - After auth, Clerk calls /clerk/sync with the session token
  - This module verifies the JWT and syncs to the local User table
  - Flask-Login session is then created for server-side auth
"""

import os
import hmac
import hashlib
import json
import requests
from functools import wraps
from flask import current_app, request, jsonify, session
from flask_login import login_user

try:
    import jwt as pyjwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False


def is_clerk_enabled():
    return current_app.config.get('CLERK_ENABLED', False)


def get_clerk_jwks():
    """Fetch Clerk's JSON Web Key Set for JWT verification."""
    clerk_key = current_app.config.get('CLERK_PUBLISHABLE_KEY', '')
    # Derive frontend API from publishable key
    # pk_test_abc123 → frontend API is at https://abc123.clerk.accounts.dev
    try:
        instance_id = clerk_key.replace('pk_test_', '').replace('pk_live_', '')
        jwks_url = f"https://{instance_id}.clerk.accounts.dev/.well-known/jwks.json"
        resp = requests.get(jwks_url, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def verify_clerk_session_token(token):
    """
    Verify a Clerk session JWT token.
    Returns the decoded payload dict or None on failure.
    """
    if not JWT_AVAILABLE:
        return None

    try:
        # Decode without verification first to get the key ID (kid)
        unverified = pyjwt.decode(token, options={"verify_signature": False})
        header = pyjwt.get_unverified_header(token)
        kid = header.get('kid')

        jwks = get_clerk_jwks()
        if not jwks:
            return None

        # Find the matching key
        from jwt.algorithms import RSAAlgorithm
        for key_data in jwks.get('keys', []):
            if key_data.get('kid') == kid:
                public_key = RSAAlgorithm.from_jwk(json.dumps(key_data))
                payload = pyjwt.decode(
                    token,
                    public_key,
                    algorithms=['RS256'],
                    options={"verify_aud": False}
                )
                return payload
    except Exception:
        pass
    return None


def verify_clerk_webhook(payload_bytes, svix_id, svix_timestamp, svix_signature):
    """
    Verify a Clerk webhook request using the webhook secret.
    Returns True if the signature is valid.
    """
    secret = current_app.config.get('CLERK_WEBHOOK_SECRET', '')
    if not secret:
        return False

    # Remove the "whsec_" prefix and base64 decode
    import base64
    secret_bytes = base64.b64decode(secret.replace('whsec_', ''))

    signed_content = f"{svix_id}.{svix_timestamp}.{payload_bytes.decode('utf-8')}"
    expected = base64.b64encode(
        hmac.new(secret_bytes, signed_content.encode(), hashlib.sha256).digest()
    ).decode()

    signatures = svix_signature.split(' ')
    for sig in signatures:
        if sig.startswith('v1,'):
            if hmac.compare_digest(sig[3:], expected):
                return True
    return False


def sync_clerk_user_to_db(clerk_payload, db, User):
    """
    Create or update a local User record from a Clerk JWT payload.
    Returns the User instance.
    """
    from models import User as UserModel
    clerk_user_id = clerk_payload.get('sub')
    email = None

    # Clerk puts primary email in email_addresses or as 'email'
    email_addresses = clerk_payload.get('email_addresses', [])
    for addr in email_addresses:
        if addr.get('id') == clerk_payload.get('primary_email_address_id'):
            email = addr.get('email_address')
            break
    if not email:
        email = clerk_payload.get('email', '')

    if not email or not clerk_user_id:
        return None

    # Find by Clerk ID first, then by email
    user = UserModel.query.filter_by(clerk_user_id=clerk_user_id).first()
    if not user:
        user = UserModel.query.filter_by(email=email.lower()).first()

    if not user:
        # Create new user
        import secrets as sec
        user = UserModel(
            email=email.lower(),
            clerk_user_id=clerk_user_id,
            is_paid=False,
            is_admin=False,
            email_verified=True,
        )
        # Set a random unusable password (auth is via Clerk)
        user.set_password(sec.token_urlsafe(32))
        user.ensure_registration_number()
        db.session.add(user)

        # Populate name fields from Clerk metadata if available
        first_name = clerk_payload.get('first_name', '')
        last_name = clerk_payload.get('last_name', '')
        if first_name:
            user.bride_first_name = first_name
            user.bride_last_name = last_name
            user.bride_email = email.lower()
    else:
        # Update Clerk ID if this user was created before Clerk was enabled
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
