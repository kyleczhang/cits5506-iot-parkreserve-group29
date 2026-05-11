"""Authentication and user-lookup business logic."""

from __future__ import annotations

from uuid import UUID

from flask_jwt_extended import create_access_token
from sqlalchemy import select

from app.extensions import db
from app.models import User, UserRole
from app.utils.errors import ConflictError, NotFoundError, UnauthorizedError
from app.utils.security import hash_password, verify_password


def register(*, email: str, name: str, password: str, role: UserRole = UserRole.USER) -> User:
    """Create a new user account after enforcing email uniqueness."""

    existing = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("email already registered", code="email_taken")
    user = User(email=email, name=name, password_hash=hash_password(password), role=role)
    db.session.add(user)
    db.session.commit()
    return user


def login(*, email: str, password: str) -> tuple[User, str]:
    """Validate credentials and return the matching user plus a JWT."""

    user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(user.password_hash, password):
        raise UnauthorizedError("invalid credentials", code="invalid_credentials")
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role.value})
    return user, token


def get_by_id(user_id: str | UUID) -> User:
    """Load one user by primary key or raise an API-level not-found error."""

    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("user not found", code="user_not_found")
    return user
