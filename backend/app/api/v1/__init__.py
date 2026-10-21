from fastapi import APIRouter

from app.api.v1 import admin, auth, chat

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(chat.router)
router.include_router(admin.router)
