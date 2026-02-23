"""Helpers de formatage pour les résultats MCP."""
from typing import Optional


def format_number(value: Optional[float], suffix: str = "") -> str:
    """Formate un nombre : 1.2M, 45K, 2 500."""
    if value is None:
        return "N/A"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M{suffix}"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K{suffix}"
    return f"{value:.0f}{suffix}"


def format_euros(value: Optional[float]) -> str:
    """Formate un montant en euros : 2 500 EUR."""
    if value is None or value == 0:
        return "N/A"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M EUR"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K EUR"
    return f"{value:.0f} EUR"


def truncate(text: Optional[str], max_len: int = 150) -> str:
    """Tronque un texte à max_len caractères."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def format_date(dt) -> str:
    """Formate une datetime en chaîne lisible."""
    if dt is None:
        return "N/A"
    try:
        return dt.strftime("%d/%m/%Y")
    except (AttributeError, ValueError):
        return str(dt)[:10]


def format_percent(value: Optional[float]) -> str:
    """Formate un pourcentage."""
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def format_rating(value: Optional[float]) -> str:
    """Formate une note sur 5."""
    if value is None:
        return "N/A"
    return f"{value:.1f}/5"
