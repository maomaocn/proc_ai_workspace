from fastapi import APIRouter

from app.api.v1 import (
    admin,
    approvals,
    auth,
    chat,
    inventory,
    knowledge,
    observability,
    procurements,
    suppliers,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(chat.router)
router.include_router(admin.router)
router.include_router(approvals.rules_router)
router.include_router(approvals.router)
router.include_router(knowledge.router)
router.include_router(procurements.router)
router.include_router(inventory.router)
router.include_router(suppliers.router)
router.include_router(observability.router)
router.include_router(observability.mcp_router)
