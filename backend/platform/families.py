"""Safe, lagged feature families inspired by the genetic notebooks.

The notebooks combine technical, macro and cross-asset data. This module only
defines the reproducible feature contract; data providers and vintage feeds are
intentionally outside of it.
"""

FAMILIES = [
    {"id": "lagged_technical", "name": "Laglı teknik", "category": "technical",
     "description": "Fiyat ve volatilite sinyalleri; bar kapanışında oluşur.",
     "source": "genetikv3lag.ipynb"},
    {"id": "macro_lagged", "name": "Laglı makro", "category": "lagged_external",
     "description": "macro__ ile başlayan serilerin bir bar gecikmeli seviye/değişimi.",
     "source": "genetikv3lag.ipynb", "requires": "macro__<name> ve tercihen __available_at"},
    {"id": "cross_asset_lagged", "name": "Laglı cross-asset", "category": "lagged_external",
     "description": "cross_asset__, fx__ veya rates__ serilerinin bir bar gecikmeli dönüşümü.",
     "source": "genetikv3lag.ipynb", "requires": "cross_asset__/fx__/rates__ <name>"},
]


def family_registry():
    return FAMILIES


def family_for_column(column: str) -> str | None:
    if column.startswith("macro__"):
        return "macro_lagged"
    if column.startswith(("cross_asset__", "fx__", "rates__")):
        return "cross_asset_lagged"
    return None
