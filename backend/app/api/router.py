"""API router registration."""

from fastapi import APIRouter

from app.auth.routes import router as auth_router
from app.jobs.routes import router as jobs_router
from app.users.routes import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
