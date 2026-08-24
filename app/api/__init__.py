from app.api.routes_admin import router as admin_router
from app.api.routes_audit import router as audit_router
from app.api.routes_query import router as query_router
from app.api.routes_ui import router as ui_router

__all__ = ["admin_router", "audit_router", "query_router", "ui_router"]
