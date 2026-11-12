from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.profiles import Student
from app.models.user import User
from app.schemas.learning import (
    AcademicAlertResponse,
    ActivityParticipationCreate,
    ActivityParticipationResponse,
    AcademicGapResponse,
    AssessmentCreate,
    AssessmentMarksUpdate,
    AssessmentResponse,
    AssessmentResultCreate,
    AssessmentResultResponse,
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
    CurriculumProgressUpdate,
    CurriculumTopicCreate,
    CurriculumTopicResponse,
    CurriculumUnitCreate,
    CurriculumUnitResponse,
    NotificationResponse,
    NextBestActionResponse,
    RiskReportResponse,
    StudentActivityCreate,
    StudentActivityResponse,
    StudentTopicProgressResponse,
    SubmissionCreate,
    SubmissionEvaluation,
    SubmissionResponse,
    SyllabusProgressResponse,
)
from app.services import academic_gap_service, learning_service
from app.services.academic_insights_service import get_staff_academic_insights
from app.services.recommendation_service import get_next_best_actions

router = APIRouter(tags=["Curriculum, Assignments & Academic Progress"])


@router.post(
    "/curriculum/units",
    response_model=CurriculumUnitResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_curriculum_unit(
    data: CurriculumUnitCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.create_curriculum_unit(db, user, data)


@router.get(
    "/curriculum/subjects/{subject_id}",
    response_model=list[CurriculumUnitResponse],
)
def list_curriculum_units(
    subject_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.list_curriculum_units(db, user, subject_id)


@router.post(
    "/curriculum/units/{unit_id}/topics",
    response_model=CurriculumTopicResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_curriculum_topic(
    unit_id: int,
    data: CurriculumTopicCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.create_curriculum_topic(db, user, unit_id, data)


@router.put(
    "/curriculum/topics/{topic_id}/progress",
    response_model=StudentTopicProgressResponse,
)
def update_curriculum_progress(
    topic_id: int,
    data: CurriculumProgressUpdate,
    student_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.update_topic_progress(db, user, topic_id, data, student_id)


@router.get(
    "/curriculum/subjects/{subject_id}/progress",
    response_model=SyllabusProgressResponse,
)
def syllabus_progress(
    subject_id: int,
    student_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.get_syllabus_progress(db, user, subject_id, student_id)


@router.post(
    "/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    data: AssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.create_assignment(db, user, data)


@router.get("/assignments", response_model=list[AssignmentResponse])
def list_assignments(
    state: Optional[str] = Query(None, pattern="^(pending|overdue|all)$"),
    subject_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.list_assignments(db, user, state, subject_id)


@router.put("/assignments/{assignment_id}", response_model=AssignmentResponse)
def update_assignment(
    assignment_id: int,
    data: AssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.update_assignment(db, user, assignment_id, data)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    learning_service.deactivate_assignment(db, user, assignment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_assignment(
    assignment_id: int,
    data: SubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.STUDENT)),
):
    return learning_service.submit_assignment(db, user, assignment_id, data.content)


@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=list[SubmissionResponse],
)
def list_assignment_submissions(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.list_submissions(db, user, assignment_id)


@router.patch(
    "/submissions/{submission_id}/evaluate",
    response_model=SubmissionResponse,
)
def evaluate_submission(
    submission_id: int,
    data: SubmissionEvaluation,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.evaluate_submission(
        db, user, submission_id, data.score, data.feedback
    )


@router.post(
    "/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(
    data: AssessmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.create_assessment(db, user, data)


@router.get("/assessments", response_model=list[AssessmentResponse])
def list_assessments(
    subject_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.list_assessments(db, user, subject_id)


@router.get("/assessments/performance")
def student_performance(
    student_id: Optional[int] = Query(None, gt=0),
    subject_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.get_performance_report(db, user, student_id, subject_id)


@router.get("/assessments/subject-averages")
def subject_performance_averages(
    subject_id: Optional[int] = Query(None, gt=0),
    division_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.get_subject_averages(db, user, subject_id, division_id)


@router.post(
    "/assessments/{assessment_id}/results",
    response_model=AssessmentResultResponse,
)
def record_assessment_result(
    assessment_id: int,
    data: AssessmentResultCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.record_assessment_result(db, user, assessment_id, data)


@router.put(
    "/assessments/{assessment_id}/results/{student_id}",
    response_model=AssessmentResultResponse,
)
def update_assessment_result(
    assessment_id: int,
    student_id: int,
    data: AssessmentMarksUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.update_assessment_result(
        db, user, assessment_id, student_id, data
    )


@router.get(
    "/assessments/{assessment_id}/results",
    response_model=list[AssessmentResultResponse],
)
def list_assessment_results(
    assessment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.list_assessment_results(db, user, assessment_id)


@router.post(
    "/activities",
    response_model=StudentActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_activity(
    data: StudentActivityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.create_activity(db, user, data)


@router.get("/activities")
def list_activities(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.list_activities(db, user)


@router.post(
    "/activities/{activity_id}/participation",
    response_model=ActivityParticipationResponse,
)
def record_activity_participation(
    activity_id: int,
    data: ActivityParticipationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return learning_service.record_participation(db, user, activity_id, data)


@router.get("/activities/history")
def activity_history(
    student_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.activity_history(db, user, student_id)


@router.get("/activities/statistics")
def activity_statistics(
    student_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.activity_statistics(db, user, student_id)


@router.get("/analytics/gaps", response_model=AcademicGapResponse)
def calculate_gaps(
    student_id: Optional[int] = Query(None, gt=0),
    subject_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    if user.role == UserRole.STUDENT:
        student_id = learning_service._student_profile(user).id
    if student_id is None:
        raise HTTPException(status_code=422, detail="student_id is required")
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    academic_gap_service._check_student_scope(db, user, student, subject_id)
    indicators = academic_gap_service.calculate_academic_gaps(db, student_id, subject_id)
    risk_level, reasons = academic_gap_service.classify_risk(indicators)
    return {
        **indicators,
        "risk_level": risk_level,
        "risk_reasons": reasons,
        "detected_at": datetime.now(timezone.utc),
    }


@router.post("/analytics/analyze", response_model=AcademicGapResponse)
def analyze_academic_risk(
    student_id: Optional[int] = Query(None, gt=0),
    subject_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    gap, risk = academic_gap_service.analyze_student(db, user, student_id, subject_id)
    return {**gap.indicators, "risk_level": risk.risk_level,
            "risk_reasons": risk.risk_reasons, "detected_at": risk.detected_at}


@router.get("/analytics/risks", response_model=list[RiskReportResponse])
def risk_report(
    student_id: Optional[int] = Query(None, gt=0),
    subject_id: Optional[int] = Query(None, gt=0),
    risk_level: Optional[str] = Query(None, pattern="^(LOW|MEDIUM|HIGH)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return academic_gap_service.list_risk_records(db, user, student_id, subject_id, risk_level)


@router.get("/analytics/gap-history")
def gap_history(
    student_id: Optional[int] = Query(None, gt=0),
    subject_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return academic_gap_service.list_gap_snapshots(db, user, student_id, subject_id)


@router.get("/alerts", response_model=list[AcademicAlertResponse])
def academic_alerts(
    student_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return academic_gap_service.list_academic_alerts(db, user, student_id)


@router.get("/recommendations")
def recommendations(
    student_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.list_recommendations(db, user, student_id)


@router.get(
    "/recommendations/next-best-action",
    response_model=list[NextBestActionResponse],
)
def next_best_actions(
    student_id: Optional[int] = Query(None, gt=0),
    subject_id: Optional[int] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return get_next_best_actions(db, user, student_id, subject_id)


@router.get("/analytics/insights")
def academic_insights(
    subject_id: Optional[int] = Query(None, gt=0),
    department_id: Optional[int] = Query(None, gt=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return get_staff_academic_insights(
        db, user, subject_id, department_id, limit
    )


@router.get("/notifications", response_model=list[NotificationResponse])
def notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.list_notifications(db, user)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return learning_service.mark_notification_read(db, user, notification_id)
