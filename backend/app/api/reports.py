from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_roles
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.attendance import DefaulterReportResponse
from app.services import attendance_service
from app.core.config import settings

router = APIRouter(prefix="/reports", tags=["Attendance Reports & Analytics"])


@router.get(
    "/defaulters",
    response_model=DefaulterReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Defaulters List Report (Admin & Teacher)",
    description="Retrieves students whose overall attendance percentage is below the given threshold (default 75%)."
)
def get_defaulter_report(
    academic_year_id: Optional[int] = Query(None, description="Filter by Academic Year ID"),
    division_id: Optional[int] = Query(None, description="Filter by Division ID"),
    threshold_percentage: float = Query(
        settings.REQUIRED_ATTENDANCE_PERCENTAGE,
        ge=0.0,
        le=100.0,
        description="Attendance threshold percentage configured by the institution"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER))
):
    return attendance_service.get_defaulter_report(
        db,
        academic_year_id=academic_year_id,
        division_id=division_id,
        threshold_percentage=threshold_percentage,
        current_user=current_user
    )
