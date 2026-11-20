from hashlib import sha256
from typing import Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status

from app.models.user import User
from app.models.enums import UserRole
from app.core.security import hash_password, verify_password


def get_user_by_username_or_email(db: Session, identifier: str) -> Optional[User]:
    """
    Lookup user by exact username or email address.
    """
    clean_identifier = identifier.strip().lower()
    return db.query(User).filter(
        or_(
            User.username == identifier.strip(),
            User.email == clean_identifier
        )
    ).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Lookup user by primary key ID.
    """
    return db.query(User).filter(User.id == user_id).first()


def register_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password: str,
    role: UserRole,
    enrollment_number: Optional[str] = None,
) -> User:
    clean_email = email.strip().lower()
    clean_enrollment = enrollment_number.strip() if enrollment_number else None

    if db.query(User.id).filter(User.email == clean_email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email address is already registered.",
        )
    if clean_enrollment and db.query(User.id).filter(
        User.enrollment_number == clean_enrollment
    ).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This enrollment number is already registered.",
        )

    username_hash = sha256(f"{role.value}:{clean_email}".encode("utf-8")).hexdigest()[:32]
    user = User(
        username=f"{role.value.lower()}_{username_hash}",
        email=clean_email,
        full_name=full_name.strip(),
        enrollment_number=clean_enrollment,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email address or enrollment number is already registered.",
        ) from exc
    db.refresh(user)
    return user


def authenticate_user(db: Session, identifier: str, password: str) -> User:
    """
    Verifies user credentials.
    Returns User if valid and active.
    Raises HTTP 401 for invalid credentials or inactive accounts.
    """
    user = get_user_by_username_or_email(db, identifier)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    is_valid = verify_password(password, user.password_hash)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
