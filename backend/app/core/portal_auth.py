"""Portal tokens are random opaque secrets, hashed at rest -- not JWTs. This keeps them
structurally incapable of being accepted by the internal `get_current_user` dependency
(a portal token isn't even valid JWT syntax), and means validity/expiry/one-time-use are
enforced by a real DB row, not just by trusting an unrevokable signed claim.
"""

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.portal import PortalToken
from app.models.quotation import Quotation

portal_bearer_scheme = HTTPBearer(auto_error=False)

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portal link not found or has expired")


def generate_portal_token() -> str:
    return secrets.token_urlsafe(32)


def hash_portal_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def get_portal_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(portal_bearer_scheme),
    db: Session = Depends(get_db),
) -> tuple[PortalToken, Quotation]:
    if credentials is None:
        raise _NOT_FOUND
    token_hash = hash_portal_token(credentials.credentials)
    portal_token = db.query(PortalToken).filter(PortalToken.token_hash == token_hash).first()
    if portal_token is None:
        raise _NOT_FOUND
    if portal_token.expires_at < datetime.now(timezone.utc):
        raise _NOT_FOUND
    quotation = db.get(Quotation, portal_token.quotation_id)
    if quotation is None:
        raise _NOT_FOUND
    return portal_token, quotation
