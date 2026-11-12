from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.learning import (
    AcademicDocumentResponse,
    AssistantMessageResponse,
    AssistantQuery,
    AssistantResponse,
)
from app.models.learning import AcademicAssistantMessage
from app.services.rag_service import (
    answer_academic_question,
    delete_academic_document,
    ingest_academic_pdf,
    list_academic_documents as list_documents_for_user,
    replace_academic_document,
)

router = APIRouter(tags=["Academic Documents & Assistant"])


@router.post(
    "/documents",
    response_model=AcademicDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_academic_document(
    file: UploadFile = File(...),
    subject_id: Optional[int] = Form(None, gt=0),
    department_id: Optional[int] = Form(None, gt=0),
    academic_class_id: Optional[int] = Form(None, gt=0),
    academic_year_id: Optional[int] = Form(None, gt=0),
    semester_id: Optional[int] = Form(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    content = file.file.read(settings.PDF_MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.PDF_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds the configured upload limit")
    return ingest_academic_pdf(
        db,
        user,
        file.filename or "academic-document.pdf",
        file.content_type or "",
        content,
        subject_id,
        department_id,
        academic_class_id,
        academic_year_id,
        semester_id,
    )


@router.get("/documents", response_model=list[AcademicDocumentResponse])
def list_academic_documents(
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    return list_documents_for_user(db, user, subject_id)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_academic_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    delete_academic_document(db, user, document_id)
    return None


@router.post(
    "/documents/{document_id}/replace",
    response_model=AcademicDocumentResponse,
)
def replace_document(
    document_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    content = file.file.read(settings.PDF_MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.PDF_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds the configured upload limit")
    return replace_academic_document(
        db,
        user,
        document_id,
        file.filename or "academic-document.pdf",
        file.content_type or "",
        content,
    )


@router.post("/assistant/query", response_model=AssistantResponse)
def query_academic_assistant(
    query: AssistantQuery,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    recent_count = db.execute(
        select(func.count(AcademicAssistantMessage.id)).where(
            AcademicAssistantMessage.user_id == user.id,
            AcademicAssistantMessage.role == "user",
            AcademicAssistantMessage.created_at
            >= datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    ).scalar_one()
    if recent_count >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Assistant request limit reached; try again in a minute",
        )
    answer = answer_academic_question(db, user, query.question, query.subject_id)
    citations = [citation.model_dump() for citation in answer["citations"]]
    db.add_all(
        [
            AcademicAssistantMessage(
                user_id=user.id,
                subject_id=query.subject_id,
                role="user",
                content=query.question,
                citations=[],
            ),
            AcademicAssistantMessage(
                user_id=user.id,
                subject_id=query.subject_id,
                role="assistant",
                content=answer["answer"],
                citations=citations,
            ),
        ]
    )
    db.commit()
    return answer


@router.get("/assistant/history", response_model=list[AssistantMessageResponse])
def assistant_history(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    messages = list(
        db.execute(
            select(AcademicAssistantMessage)
            .where(AcademicAssistantMessage.user_id == user.id)
            .order_by(AcademicAssistantMessage.created_at.desc(), AcademicAssistantMessage.id.desc())
            .limit(limit)
        ).scalars()
    )
    return list(reversed(messages))


@router.delete("/assistant/history", status_code=status.HTTP_204_NO_CONTENT)
def clear_assistant_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    db.query(AcademicAssistantMessage).filter(
        AcademicAssistantMessage.user_id == user.id
    ).delete(synchronize_session=False)
    db.commit()
    return None
