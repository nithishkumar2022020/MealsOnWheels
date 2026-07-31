"""Route routes. Public read — a traveller picks a route before authenticating."""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import DbSession
from app.schemas import RouteListResponse
from app.services import routes as routes_service

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.get("", response_model=RouteListResponse)
async def list_routes(db: DbSession) -> RouteListResponse:
    """List the seeded travel routes.

    No auth: this is the first screen a traveller sees, before login
    (docs/05_API_SPEC.md section 5.1). Nothing here is user-specific.
    """
    routes = await routes_service.list_routes(db)
    return RouteListResponse(routes=routes, total_count=len(routes))
