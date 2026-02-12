"""Shared utility functions."""


def get_logo_url(website: str | None) -> str | None:
    """Generate a logo URL from a website domain using Google Favicon API."""
    if not website:
        return None
    domain = website.replace("https://", "").replace("http://", "").split("/")[0].removeprefix("www.")
    if not domain or "." not in domain:
        return None
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
