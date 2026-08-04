"""Route listing.

The lat/lon extraction happens in SQL rather than by decoding WKB in Python.
PostGIS already has the accessors, and a hand-rolled decoder is one more place
for the axis order to get flipped.

`ST_X` is longitude and `ST_Y` is latitude — the reverse of how coordinates are
written in `lat, lon` form. Swapping them puts Delhi in the Indian Ocean, which
is why tests/test_routes.py asserts the seeded values round-trip
(docs/05_API_SPEC.md section 5.1).
"""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Route
from app.schemas import RouteResponse


async def list_routes(db: AsyncSession) -> list[RouteResponse]:
    """Every route, ordered by id so the client dropdown is stable.

    No pagination: the MVP has five rows and the API contract returns full lists
    (docs/05_API_SPEC.md section 1).
    """
    # ST_X/ST_Y take a geometry; the columns are geography, hence the cast.
    origin = cast(Route.origin_point, Geometry)
    dest = cast(Route.dest_point, Geometry)

    stmt = select(
        Route.id,
        Route.name,
        Route.origin_name,
        Route.dest_name,
        func.ST_Y(origin).label("origin_lat"),
        func.ST_X(origin).label("origin_lon"),
        func.ST_Y(dest).label("dest_lat"),
        func.ST_X(dest).label("dest_lon"),
        Route.distance_km,
    ).order_by(Route.id)

    result = await db.execute(stmt)
    return [RouteResponse.model_validate(dict(row)) for row in result.mappings()]
