"""
mock_db.py  — Simulates the external database.
Returns deterministic values for all KEY_N lookups by ISIN.
In production: replace get() with a real SQL/JDBC call.
"""
from decimal import Decimal

# Simulated DB table: (isin, key) -> value
_DB: dict[tuple, str] = {}

# Generate deterministic DB values for every ISIN × KEY combo
ISINS   = ["INF000A1", "INF000B2", "INF000C3", "INF000D4", "INF000E5"]
DB_KEYS = [7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57, 62, 67, 72, 77, 82, 87, 92]

_BASE_VALUES = {
    "INF000A1": 1000.0,
    "INF000B2": 2000.0,
    "INF000C3": 3000.0,
    "INF000D4": 4000.0,
    "INF000E5": 5000.0,
}

for _isin in ISINS:
    for _key_num in DB_KEYS:
        # Each (isin, key) gets a unique deterministic value
        _DB[(_isin, f"KEY_{_key_num}")] = str(
            round(_BASE_VALUES[_isin] + _key_num * 10.5, 4)
        )


def db_lookup(isin: str, key: str) -> str:
    """Fetch a value from the database by ISIN and key name."""
    result = _DB.get((isin, key), "N/A")
    return result


def get_all_keys() -> list[str]:
    return [f"KEY_{n}" for n in DB_KEYS]
