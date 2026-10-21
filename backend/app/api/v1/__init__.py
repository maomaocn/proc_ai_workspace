from fastapi import APIRouter

from app.api.v1 import admin, auth, chat, inventory, knowledge, procurements, suppliers

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(chat.router)
router.include_router(admin.router)
router.include_router(knowledge.router)
router.include_router(procurements.router)
router.include_router(inventory.router)
router.include_router(suppliers.router)
