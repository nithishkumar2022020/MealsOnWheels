"""Seed menus. **Not** the runtime price source any more.

Retained solely so `scripts/seed.py` has plausible dishes to write into
`menu_items` for the seeded corridor. Nothing in the request path reads this
module: prices are resolved from the database by `app/services/menus.py`, and
`GET /restaurants/{id}` renders whatever rows the owner actually maintains.

**Do not add a lookup here.** If a restaurant has no menu rows it is listed but
not bookable, and that is deliberate. Falling back to these constants would quote
a traveller a dish and a price that the restaurant never agreed to — for an
OSM-promoted dhaba, one nobody has even spoken to — and the failure would surface
at the roadside rather than in the API. `is_bookable` and `unbookable_reason` on
the detail response carry that state instead.

Prices are `Decimal`, never `float`. `0.1 + 0.2 != 0.3` in binary floating point,
and these values land in a `NUMERIC(10,2)` column that money is owed against.
"""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple


class MenuItem(NamedTuple):
    name: str
    price: Decimal
    category: str


def _item(name: str, price: str, category: str) -> MenuItem:
    # Decimal from a string, never from a float: Decimal(80.10) carries the
    # float's representation error, Decimal("80.10") does not.
    return MenuItem(name, Decimal(price), category)


# Fallback dishes for a seeded restaurant with no named menu above, so every
# seeded row has something orderable. This is NOT served to OSM-promoted POIs
# or self-registrations — nothing writes menu rows for those, and they are
# listed as unbookable until an owner supplies a real menu.
DEFAULT_MENU: tuple[MenuItem, ...] = (
    _item("Paneer Paratha", "80.00", "Main"),
    _item("Aloo Paratha", "60.00", "Main"),
    _item("Dal Makhani", "120.00", "Main"),
    _item("Veg Thali", "150.00", "Main"),
    _item("Lassi", "40.00", "Beverage"),
    _item("Masala Chai", "20.00", "Beverage"),
)

# Per-restaurant overrides, keyed by the seeded name. Keyed on name rather than
# id because ids are serial and differ between a fresh database and a seeded one.
MENUS_BY_NAME: dict[str, tuple[MenuItem, ...]] = {
    "Murthal Dhaba": (
        _item("Paneer Paratha", "80.00", "Main"),
        _item("Aloo Paratha", "60.00", "Main"),
        _item("Dal Makhani", "120.00", "Main"),
        _item("Lassi", "40.00", "Beverage"),
        _item("Masala Chai", "20.00", "Beverage"),
    ),
    "Amrik Sukhdev": (
        _item("Amritsari Kulcha", "110.00", "Main"),
        _item("Chole Bhature", "130.00", "Main"),
        _item("Paneer Butter Masala", "180.00", "Main"),
        _item("Sweet Lassi", "50.00", "Beverage"),
        _item("Gulab Jamun", "60.00", "Dessert"),
    ),
    "Gulshan Dhaba": (
        _item("Tandoori Roti", "15.00", "Main"),
        _item("Rajma Chawal", "110.00", "Main"),
        _item("Shahi Paneer", "170.00", "Main"),
        _item("Buttermilk", "30.00", "Beverage"),
    ),
    "Highway Kitchen": (
        _item("Veg Biryani", "140.00", "Main"),
        _item("Chicken Biryani", "220.00", "Main"),
        _item("Raita", "40.00", "Side"),
        _item("Cold Coffee", "70.00", "Beverage"),
    ),
    "Sukhdev Vaishno Dhaba": (
        _item("Chana Masala", "100.00", "Main"),
        _item("Missi Roti", "25.00", "Main"),
        _item("Kadhi Chawal", "95.00", "Main"),
        _item("Masala Chai", "20.00", "Beverage"),
    ),
    "Pehalwan Dhaba": (
        _item("Butter Chicken", "260.00", "Main"),
        _item("Naan", "35.00", "Main"),
        _item("Egg Curry", "150.00", "Main"),
        _item("Lassi", "45.00", "Beverage"),
    ),
    "Garam Dharam Dhaba": (
        _item("Sarson Ka Saag", "160.00", "Main"),
        _item("Makki Ki Roti", "40.00", "Main"),
        _item("Paneer Tikka", "200.00", "Starter"),
        _item("Jalebi", "70.00", "Dessert"),
    ),
    "Jhilmil Dhaba": (
        _item("Veg Pulao", "90.00", "Main"),
        _item("Mix Veg", "120.00", "Main"),
        _item("Plain Paratha", "35.00", "Main"),
        _item("Nimbu Pani", "25.00", "Beverage"),
    ),
    "Z Blue Jays": (
        _item("Veg Burger", "120.00", "Snack"),
        _item("French Fries", "90.00", "Snack"),
        _item("Paneer Wrap", "140.00", "Snack"),
        _item("Cold Coffee", "80.00", "Beverage"),
    ),
    "Haveli Restaurant": (
        _item("Dal Baati Churma", "220.00", "Main"),
        _item("Laal Maas", "320.00", "Main"),
        _item("Ker Sangri", "180.00", "Main"),
        _item("Masala Chaas", "50.00", "Beverage"),
    ),
}


def menu_for(restaurant_name: str) -> tuple[MenuItem, ...]:
    """Seed dishes for a named restaurant, or a generic set.

    Called only by scripts/seed.py. The DEFAULT_MENU fallback is a seeding
    convenience — every seeded restaurant should have something orderable — and
    emphatically not a runtime fallback: a restaurant with no menu rows is listed
    and unbookable, not silently given someone else's dishes.
    """
    return MENUS_BY_NAME.get(restaurant_name, DEFAULT_MENU)


def price_of(restaurant_name: str, item_name: str) -> Decimal | None:
    """Seed-time price lookup. `None` means "not in the seed data".

    **Not the booking path.** That reads `app/services/menus.price_lookup`, which
    queries menu_items and excludes anything currently unavailable.
    """
    for item in menu_for(restaurant_name):
        if item.name == item_name:
            return item.price
    return None
