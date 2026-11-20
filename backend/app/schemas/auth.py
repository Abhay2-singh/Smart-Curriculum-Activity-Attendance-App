from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.models.enums import UserRole


class LoginRequest(BaseModel):
    """
    Credentials schema for authentication endpoint.
    Accepts either username or email as login identifier.
    """
    username: str = Field(..., description="Username or Email address", example="admin@example.com")
    password: str = Field(..., description="User password")
    role: Optional[UserRole] = Field(None, description="Expected account type")


class RegistrationRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    confirm_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be empty")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("password", "confirm_password")
    @classmethod
    def enforce_bcrypt_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return value

    @model_validator(mode="after")
    def validate_password_confirmation(self) -> "RegistrationRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class StudentRegistrationRequest(RegistrationRequest):
    enrollment_number: str = Field(..., min_length=1, max_length=50)

    @field_validator("enrollment_number")
    @classmethod
    def normalize_enrollment_number(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enrollment number cannot be empty")
        return value


from app.schemas.user import TeacherResponse, StudentResponse


class UserResponse(BaseModel):
    """
    Sanitized user details schema for public API responses.
    Excludes sensitive fields like password_hash.
    """
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    enrollment_number: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime
    teacher_profile: Optional[TeacherResponse] = None
    student_profile: Optional[StudentResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """
    JWT Access Token response structure.
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifespan in seconds")
    user: UserResponse


class RoleTestResponse(BaseModel):
    """
    Response schema for role authorization testing endpoints.
    """
    message: str
    user_id: int
    username: str
    role: UserRole
