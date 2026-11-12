import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db

router = APIRouter(prefix="/health", tags=["Health Checks"])
logger = logging.getLogger(__name__)


@router.get("", summary="Basic Health Check")
def health_check():
    """
    Returns API runtime health status.
    """
    return {
        "status": "ok",
        "message": "Attendance Management System API is running"
    }


@router.get("/database", summary="Database Connectivity Check")
def database_health_check(db: Session = Depends(get_db)):
    """
    Verifies connection to MySQL database by running a lightweight query.
    """
    try:
        # Execute test query
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
            "database_name": settings.DB_NAME,
            "host": settings.DB_HOST,
            "port": settings.DB_PORT
        }
    except SQLAlchemyError as exc:
        logger.warning("Database health check failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": "disconnected",
                "message": "Failed to connect to MySQL database",
            }
        ) from exc
