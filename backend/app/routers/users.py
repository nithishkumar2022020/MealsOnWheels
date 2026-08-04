"""User routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import CurrentUser
from app.schemas import UserResponse

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/profile", response_model=UserResponse)
async def get_profile(user: CurrentUser) -> UserResponse:
    """Return the authenticated caller's own profile.

    There is no `GET /user/{id}`: a traveller only ever reads themselves, so the
    identifier comes from the token and no ownership check can be forgotten.
    """
    return UserResponse.model_validate(user)
