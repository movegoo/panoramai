"""Shared utility functions."""


def get_logo_url(website: str | None) -> str | None:
    """Generate a logo URL from a website domain using Clearbit Logo API."""
    if not website:
        return None
    domain = website.replace("https://", "").replace("http://", "").split("/")[0].removeprefix("www.")
    if not domain or "." not in domain:
        return None
    return f"https://logo.clearbit.com/{domain}"
