"""Hardcoded menus — the authoritative price source.

**This module is the only place a price comes from.** `POST /bookings/create`
resolves every line item against it and computes the total itself; a client-sent
price is refused by `extra="forbid"` and never read
(docs/05_API_SPEC.md sections 6.2 and 7.1). What `GET /restaurants/{id}` displays
is therefore exactly what the booking will charge.

Prices are `Decimal`, never `float`. `0.1 + 0.2 != 0.3` in binary floating point,
and these values are summed into a `NUMERIC(10,2)` column that money is owed
against.

Menus are per-restaurant and hardcoded in MVP; `menu_items` CRUD is Phase 1
(docs/04_DATABASE_DESIGN.md section 4.1). Adding a dish is a code change until
then, which is a known cost of keeping the price boundary server-side.
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


# The menu served to any restaurant without a specific one — every OSM-promoted
# POI, and any self-registered restaurant. They were never onboarded, so nobody
# supplied a menu; serving a plausible default keeps them bookable.
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
    """The menu a restaurant serves.

    Falls back to DEFAULT_MENU rather than returning empty: an empty menu makes a
    restaurant unbookable, and OSM-promoted POIs exist precisely to cover
    corridors where seeded data is thin.
    """
    return MENUS_BY_NAME.get(restaurant_name, DEFAULT_MENU)


def price_of(restaurant_name: str, item_name: str) -> Decimal | None:
    """Resolve one item's unit price. `None` means "not on this menu".

    Stage 11 turns `None` into a 400 rather than a guess — an unknown dish must
    not be silently priced at zero.
    """
    for item in menu_for(restaurant_name):
        if item.name == item_name:
            return item.price
    return None
