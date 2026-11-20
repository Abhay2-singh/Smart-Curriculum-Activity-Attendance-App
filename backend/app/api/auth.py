from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegistrationRequest,
    StudentRegistrationRequest,
    TokenResponse,
    UserResponse,
    RoleTestResponse,
)
from app.services.auth_service import authenticate_user, register_user
from app.services.profile_provisioning_service import ensure_user_profile
from app.models.enums import UserRole
from app.api.deps import (
    get_current_active_user,
    require_admin,
    require_teacher,
    require_student,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Authorization"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login",
    description="Authenticates user credentials and returns a JWT access token."
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Verify user credentials and issue a signed JWT access token.
    """
    user = authenticate_user(
        db=db,
        identifier=login_data.username,
        password=login_data.password
    )
    if login_data.role and user.role != login_data.role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials for the selected account type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = ensure_user_profile(db, user)

    access_token = create_access_token(
        subject=user.id,
        extra_data={
            "role": user.role.value,
            "username": user.username
        }
    )

    expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in_seconds,
        user=UserResponse.model_validate(user)
    )


@router.post(
    "/register/student",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a student account",
)
def register_student(
    registration: StudentRegistrationRequest,
    db: Session = Depends(get_db),
):
    user = register_user(
        db,
        full_name=registration.full_name,
        email=str(registration.email),
        password=registration.password,
        role=UserRole.STUDENT,
        enrollment_number=registration.enrollment_number,
    )
    user = ensure_user_profile(db, user)
    return user


@router.post(
    "/register/teacher",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a teacher account",
)
def register_teacher(
    registration: RegistrationRequest,
    db: Session = Depends(get_db),
):
    user = register_user(
        db,
        full_name=registration.full_name,
        email=str(registration.email),
        password=registration.password,
        role=UserRole.TEACHER,
    )
    user = ensure_user_profile(db, user)
    return user


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User Profile",
    description="Returns current authenticated user details extracted from JWT token."
)
def get_me(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Protected endpoint returning current user information.
    """
    current_user = ensure_user_profile(db, current_user)
    return UserResponse.model_validate(current_user)


# Dedicated role test endpoints to verify role authorization filters
@router.get(
    "/test/admin",
    response_model=RoleTestResponse,
    summary="Test ADMIN Role Access",
    description="Protected endpoint accessible only to ADMIN role."
)
def test_admin_access(
    current_user: User = Depends(require_admin)
):
    return RoleTestResponse(
        message="Access granted to ADMIN endpoint",
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role
    )


@router.get(
    "/test/teacher",
    response_model=RoleTestResponse,
    summary="Test TEACHER Role Access",
    description="Protected endpoint accessible only to TEACHER role."
)
def test_teacher_access(
    current_user: User = Depends(require_teacher)
):
    return RoleTestResponse(
        message="Access granted to TEACHER endpoint",
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role
    )


@router.get(
    "/test/student",
    response_model=RoleTestResponse,
    summary="Test STUDENT Role Access",
    description="Protected endpoint accessible only to STUDENT role."
)
def test_student_access(
    current_user: User = Depends(require_student)
):
    return RoleTestResponse(
        message="Access granted to STUDENT endpoint",
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role
    )
