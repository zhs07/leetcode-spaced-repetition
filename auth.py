"""Verify Supabase access tokens using the configured project's public keys."""

from uuid import UUID

import jwt
from fastapi import HTTPException


class TokenVerifier:
    def __init__(self, supabase_url: str):
        self.issuer = supabase_url.rstrip("/") + "/auth/v1"
        self.keys = jwt.PyJWKClient(
            self.issuer + "/.well-known/jwks.json", timeout=5,
            cache_jwk_set=True, lifespan=300,
        )

    def verify(self, token: str) -> UUID:
        try:
            if len(token) > 16384:
                raise ValueError("Oversized token")
            header = jwt.get_unverified_header(token)
            # This header is untrusted: only use it to reject unsupported tokens.
            if header.get("alg") not in {"ES256", "RS256"} or not isinstance(header.get("kid"), str) or not header["kid"]:
                raise ValueError("Unsupported signing key")
            key = self.keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token, key.key, algorithms=["ES256", "RS256"],
                issuer=self.issuer, audience="authenticated",
                options={"require": ["exp", "iat", "iss", "aud", "sub", "role"]},
            )
            if claims["role"] != "authenticated" or claims.get("is_anonymous", False) is not False:
                raise ValueError("A signed-in account is required")
            user_id = UUID(claims["sub"])
            if user_id.int == 0:
                raise ValueError("Invalid subject")
            return user_id
        except jwt.PyJWKClientConnectionError:
            raise HTTPException(503, "Sign-in verification is temporarily unavailable. Please try again.") from None
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise HTTPException(
                401, "Your session is invalid or expired. Please sign in again.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
