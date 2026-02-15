"""
ASO (App Store Optimization) Analysis Router.
Computes ASO scores from stored app data + live enrichment.
"""
import asyncio
import json
import logging
import math
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header
from sqlalchemy import desc
from sqlalchemy.orm import Session

from database import get_db, Competitor, AppData, User
from core.auth import get_current_user
from core.permissions import get_user_competitors, parse_advertiser_header
from core.trends import parse_download_count

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── ASO Score Weights ───────────────────────────────────────────────────────
WEIGHTS = {
    "metadata": 0.25,
    "visual": 0.20,
    "rating": 0.25,
    "reviews": 0.15,
    "freshness": 0.15,
}


# ─── Live enrichment: fetch extra ASO fields not stored in DB ────────────────

def _enrich_playstore(app_id: str) -> dict:
    """Fetch extra Play Store fields for ASO analysis."""
    try:
        from google_play_scraper import app as gp_app
        result = gp_app(app_id, lang="fr", country="fr")
        return {
            "icon_url": result.get("icon"),
            "screenshot_urls": result.get("screenshots", []),
            "video_url": result.get("video"),
            "header_image": result.get("headerImage"),
            "short_description": result.get("summary", ""),
            "content_rating": result.get("contentRating"),
            "size": result.get("size"),
            "histogram": result.get("histogram"),  # [1star, 2star, 3star, 4star, 5star]
            "installs": result.get("realInstalls") or result.get("minInstalls"),
            "developer_email": result.get("developerEmail"),
            "developer_website": result.get("developerWebsite"),
            "android_version": result.get("androidVersion"),
            "genre": result.get("genre"),
            "ad_supported": result.get("adSupported", False),
            "contains_ads": result.get("containsAds", False),
            "in_app_purchases": result.get("offersIAP", False),
            "free": result.get("free", True),
        }
    except Exception as e:
        logger.warning(f"Play Store ASO enrichment failed for {app_id}: {e}")
        return {}


async def _enrich_appstore(app_id: str) -> dict:
    """Fetch extra App Store fields for ASO analysis."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://itunes.apple.com/lookup",
                params={"id": app_id, "country": "fr"},
            )
            data = resp.json()
            if not data.get("results"):
                return {}
            info = data["results"][0]
            return {
                "icon_url": info.get("artworkUrl512") or info.get("artworkUrl100"),
                "screenshot_urls": info.get("screenshotUrls", []),
                "ipad_screenshot_urls": info.get("ipadScreenshotUrls", []),
                "subtitle": "",  # Not available via lookup API
                "file_size_bytes": info.get("fileSizeBytes"),
                "content_rating": info.get("contentAdvisoryRating"),
                "min_os_version": info.get("minimumOsVersion"),
                "languages": info.get("languageCodesISO2A", []),
                "genre": info.get("primaryGenreName"),
                "seller_name": info.get("sellerName"),
                "price": info.get("price", 0),
                "current_version_rating": info.get("averageUserRatingForCurrentVersion"),
                "current_version_reviews": info.get("userRatingCountForCurrentVersion"),
            }
    except Exception as e:
        logger.warning(f"App Store ASO enrichment failed for {app_id}: {e}")
        return {}


# ─── Score Calculation ───────────────────────────────────────────────────────

def _compute_metadata_score(
    title: str,
    description: str,
    changelog: str | None,
    short_desc: str = "",
    store: str = "playstore",
) -> dict:
    """Metadata optimization score (0-100)."""
    scores = {}

    # Title: optimal is 25-30 chars with brand + keyword
    title_len = len(title or "")
    title_max = 30
    scores["title_length"] = min(title_len / title_max, 1.0) * 100
    scores["title_length_detail"] = f"{title_len}/{title_max} caracteres"

    # Description: GP indexes it, iOS doesn't (but it still matters for conversion)
    desc_len = len(description or "")
    if store == "playstore":
        ideal_min, ideal_max = 2500, 4000
        scores["description_length"] = min(desc_len / ideal_min, 1.0) * 100 if desc_len < ideal_max else 100
    else:
        ideal_min = 1500
        scores["description_length"] = min(desc_len / ideal_min, 1.0) * 100
    scores["description_length_detail"] = f"{desc_len} caracteres"

    # Description structure (bullet points, formatting)
    has_bullets = any(c in (description or "") for c in ["•", "✓", "✔", "★", "►", "-", "·"])
    has_paragraphs = (description or "").count("\n\n") >= 2
    struct_score = 0
    if has_bullets:
        struct_score += 50
    if has_paragraphs:
        struct_score += 50
    scores["description_structure"] = struct_score
    scores["description_structure_detail"] = ("Listes" if has_bullets else "Pas de listes") + " | " + ("Paragraphes" if has_paragraphs else "Bloc unique")

    # Short description / subtitle
    if store == "playstore":
        sd_len = len(short_desc or "")
        scores["short_description"] = min(sd_len / 80, 1.0) * 100
        scores["short_description_detail"] = f"{sd_len}/80 caracteres"
    else:
        # iOS subtitle not available via API, give neutral score
        scores["short_description"] = 50
        scores["short_description_detail"] = "Subtitle non disponible via API"

    # Changelog (release notes)
    cl_len = len(changelog or "")
    if cl_len > 100:
        scores["changelog"] = 100
    elif cl_len > 30:
        scores["changelog"] = 60
    elif cl_len > 0:
        scores["changelog"] = 30
    else:
        scores["changelog"] = 0
    scores["changelog_detail"] = f"{cl_len} caracteres" if cl_len > 0 else "Aucun changelog"

    # Composite
    weights = {"title_length": 0.25, "description_length": 0.25, "description_structure": 0.15, "short_description": 0.20, "changelog": 0.15}
    total = sum(scores.get(k, 0) * w for k, w in weights.items())
    scores["total"] = round(total, 1)

    return scores


def _compute_visual_score(
    screenshot_urls: list,
    video_url: str | None,
    header_image: str | None = None,
    icon_url: str | None = None,
    store: str = "playstore",
) -> dict:
    """Visual asset optimization score (0-100)."""
    scores = {}

    # Screenshots
    max_screenshots = 8 if store == "playstore" else 10
    count = len(screenshot_urls or [])
    scores["screenshot_count"] = min(count / max_screenshots, 1.0) * 100
    scores["screenshot_count_detail"] = f"{count}/{max_screenshots} screenshots"

    # Video
    scores["video_present"] = 100 if video_url else 0
    scores["video_present_detail"] = "Video presente" if video_url else "Pas de video"

    # Header/feature graphic (Play Store)
    if store == "playstore":
        scores["header_image"] = 100 if header_image else 0
        scores["header_image_detail"] = "Feature graphic presente" if header_image else "Pas de feature graphic"

    # Icon
    scores["icon_present"] = 100 if icon_url else 50  # Should always have one
    scores["icon_present_detail"] = "Icone presente" if icon_url else "Icone non verifiee"

    # Composite
    if store == "playstore":
        weights = {"screenshot_count": 0.45, "video_present": 0.25, "header_image": 0.15, "icon_present": 0.15}
    else:
        weights = {"screenshot_count": 0.50, "video_present": 0.30, "icon_present": 0.20}
    total = sum(scores.get(k, 0) * w for k, w in weights.items())
    scores["total"] = round(total, 1)

    return scores


def _compute_rating_score(rating: float | None, histogram: list | None = None) -> dict:
    """Rating health score (0-100)."""
    scores = {}

    if rating is None:
        return {"total": 0, "rating_normalized": 0, "rating_detail": "Aucune note"}

    scores["rating_normalized"] = round((rating / 5.0) * 100, 1)
    scores["rating_detail"] = f"{rating:.1f}/5"

    # Histogram analysis (Play Store only)
    if histogram and len(histogram) == 5:
        total_ratings = sum(histogram)
        if total_ratings > 0:
            # Percentage of 4-5 star ratings
            positive_pct = ((histogram[3] + histogram[4]) / total_ratings) * 100
            scores["positive_ratio"] = round(positive_pct, 1)
            scores["positive_ratio_detail"] = f"{positive_pct:.0f}% d'avis 4-5 etoiles"

            # 1-star ratio (problem indicator)
            negative_pct = (histogram[0] / total_ratings) * 100
            scores["negative_ratio"] = round(100 - negative_pct, 1)  # Higher = better
            scores["negative_ratio_detail"] = f"{negative_pct:.0f}% d'avis 1 etoile"

            scores["histogram"] = histogram
        else:
            scores["positive_ratio"] = 0
            scores["negative_ratio"] = 100

    # Composite
    if "positive_ratio" in scores:
        total = scores["rating_normalized"] * 0.6 + scores["positive_ratio"] * 0.25 + scores["negative_ratio"] * 0.15
    else:
        total = scores["rating_normalized"]
    scores["total"] = round(total, 1)

    return scores


def _compute_reviews_score(reviews_count: int | None, max_reviews: int = 1) -> dict:
    """Review health score (0-100), relative to the best competitor."""
    scores = {}

    if not reviews_count or reviews_count == 0:
        return {"total": 0, "volume_detail": "Aucun avis"}

    # Log-normalized volume (avoids huge disparities)
    if max_reviews > 0:
        log_score = math.log10(reviews_count + 1) / math.log10(max_reviews + 1) * 100
    else:
        log_score = 50
    scores["volume_normalized"] = round(min(log_score, 100), 1)
    scores["volume_detail"] = f"{reviews_count:,} avis"

    scores["total"] = scores["volume_normalized"]
    return scores


def _compute_freshness_score(last_updated: datetime | None) -> dict:
    """App freshness score based on last update date (0-100)."""
    scores = {}

    if not last_updated:
        return {"total": 0, "freshness_detail": "Date de MAJ inconnue"}

    days_ago = (datetime.utcnow() - last_updated).days
    if days_ago <= 14:
        score = 100
        label = "Tres recent"
    elif days_ago <= 30:
        score = 90
        label = "Recent"
    elif days_ago <= 60:
        score = 70
        label = "Acceptable"
    elif days_ago <= 90:
        score = 50
        label = "A surveiller"
    elif days_ago <= 180:
        score = 30
        label = "Ancien"
    else:
        score = 10
        label = "Tres ancien"

    scores["days_since_update"] = days_ago
    scores["freshness_detail"] = f"{days_ago}j depuis la MAJ ({label})"
    scores["total"] = score
    return scores


def _generate_aso_recommendations(competitor_scores: list, brand_name: str | None) -> list:
    """Generate actionable ASO recommendations based on scores."""
    recs = []
    if not competitor_scores:
        return recs

    brand_score = next((s for s in competitor_scores if brand_name and s["competitor_name"].lower() == brand_name.lower()), None)
    if not brand_score:
        return recs

    # Find weakest dimension
    dimensions = [
        ("metadata", "Metadata", "Optimisez le titre (30 chars max), enrichissez la description avec des mots-cles et des bullet points, et ajoutez un changelog detaille a chaque mise a jour."),
        ("visual", "Assets visuels", "Ajoutez plus de screenshots (idealement le maximum), une video de presentation, et verifiez que votre feature graphic est impactante."),
        ("rating", "Note utilisateurs", "Ameliorez l'UX, repondez aux avis negatifs, et lancez des campagnes de rating pour augmenter votre note moyenne."),
        ("reviews", "Volume d'avis", "Encouragez les utilisateurs a laisser un avis via des in-app prompts intelligents apres une experience positive."),
        ("freshness", "Fraicheur", "Publiez des mises a jour regulieres (idealement toutes les 2-4 semaines) avec des changelogs detailles."),
    ]

    brand_ps = brand_score.get("playstore", {})
    brand_as = brand_score.get("appstore", {})

    for key, label, advice in dimensions:
        ps_score = brand_ps.get(f"{key}_score", {}).get("total", 0) if brand_ps else 0
        as_score = brand_as.get(f"{key}_score", {}).get("total", 0) if brand_as else 0
        avg_score = (ps_score + as_score) / 2 if brand_ps and brand_as else (ps_score or as_score)

        if avg_score < 60:
            store_label = ""
            if brand_ps and brand_as:
                if ps_score < as_score:
                    store_label = " (surtout sur Play Store)"
                elif as_score < ps_score:
                    store_label = " (surtout sur App Store)"
            recs.append({
                "dimension": label,
                "score": round(avg_score, 1),
                "advice": f"{label}{store_label} : score {avg_score:.0f}/100. {advice}",
                "priority": "high" if avg_score < 40 else "medium",
            })

    # Compare with leader
    best = max(competitor_scores, key=lambda s: s.get("aso_score_avg", 0))
    if best["competitor_name"] != brand_score["competitor_name"]:
        gap = best.get("aso_score_avg", 0) - brand_score.get("aso_score_avg", 0)
        if gap > 10:
            recs.insert(0, {
                "dimension": "Score global",
                "score": round(brand_score.get("aso_score_avg", 0), 1),
                "advice": f"{best['competitor_name']} domine l'ASO avec un score de {best.get('aso_score_avg', 0):.0f}/100 contre {brand_score.get('aso_score_avg', 0):.0f} pour {brand_name}. Ecart de {gap:.0f} points a combler.",
                "priority": "high" if gap > 20 else "medium",
            })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 2))

    return recs


# ─── Main Endpoint ───────────────────────────────────────────────────────────

@router.get("/analysis")
async def get_aso_analysis(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    x_advertiser_id: str | None = Header(None),
):
    """
    Full ASO analysis for all competitors.
    Enriches stored data with live store metadata, computes scores.
    Auto-loaded on page load.
    """
    adv_id = parse_advertiser_header(x_advertiser_id)
    competitors = [
        c for c in get_user_competitors(db, user, advertiser_id=adv_id)
        if c.is_active and (c.playstore_app_id or c.appstore_app_id)
    ]

    if not competitors:
        return {"competitors": [], "recommendations": [], "brand_name": None}

    # Get brand name
    from database import Advertiser
    brand_name = None
    if adv_id:
        adv = db.query(Advertiser).get(int(adv_id))
        if adv:
            brand_name = adv.company_name
    elif user:
        adv = db.query(Advertiser).filter(Advertiser.user_id == user.id).first()
        if adv:
            brand_name = adv.company_name

    # Gather latest DB data + live enrichment in parallel
    results = []
    max_reviews_ps = 1
    max_reviews_as = 1

    # First pass: get latest DB data and max reviews
    competitor_db_data = {}
    for comp in competitors:
        ps_latest = None
        as_latest = None
        if comp.playstore_app_id:
            ps_latest = (
                db.query(AppData)
                .filter(AppData.competitor_id == comp.id, AppData.store == "playstore")
                .order_by(desc(AppData.recorded_at))
                .first()
            )
            if ps_latest and ps_latest.reviews_count:
                max_reviews_ps = max(max_reviews_ps, ps_latest.reviews_count)
        if comp.appstore_app_id:
            as_latest = (
                db.query(AppData)
                .filter(AppData.competitor_id == comp.id, AppData.store == "appstore")
                .order_by(desc(AppData.recorded_at))
                .first()
            )
            if as_latest and as_latest.reviews_count:
                max_reviews_as = max(max_reviews_as, as_latest.reviews_count)
        competitor_db_data[comp.id] = (ps_latest, as_latest)

    # Live enrichment (parallel)
    async def enrich_competitor(comp):
        ps_extra = {}
        as_extra = {}
        loop = asyncio.get_event_loop()
        tasks = []
        if comp.playstore_app_id:
            tasks.append(("ps", loop.run_in_executor(None, _enrich_playstore, comp.playstore_app_id)))
        if comp.appstore_app_id:
            tasks.append(("as", _enrich_appstore(comp.appstore_app_id)))

        for label, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=15)
                if label == "ps":
                    ps_extra = result
                else:
                    as_extra = result
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"ASO enrichment timeout for {comp.name} ({label}): {e}")

        return comp.id, ps_extra, as_extra

    enrichment_tasks = [enrich_competitor(comp) for comp in competitors]
    enrichment_results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)

    enrichment_map = {}
    for r in enrichment_results:
        if isinstance(r, tuple):
            enrichment_map[r[0]] = (r[1], r[2])

    # Second pass: compute scores
    competitor_scores = []
    for comp in competitors:
        ps_latest, as_latest = competitor_db_data.get(comp.id, (None, None))
        ps_extra, as_extra = enrichment_map.get(comp.id, ({}, {}))

        entry = {
            "competitor_id": comp.id,
            "competitor_name": comp.name,
            "is_brand": brand_name and comp.name.lower() == brand_name.lower(),
        }

        scores_list = []

        # Play Store ASO
        if ps_latest:
            metadata = _compute_metadata_score(
                title=ps_latest.app_name or "",
                description=ps_latest.description or "",
                changelog=ps_latest.changelog,
                short_desc=ps_extra.get("short_description", ""),
                store="playstore",
            )
            visual = _compute_visual_score(
                screenshot_urls=ps_extra.get("screenshot_urls", []),
                video_url=ps_extra.get("video_url"),
                header_image=ps_extra.get("header_image"),
                icon_url=ps_extra.get("icon_url"),
                store="playstore",
            )
            rating = _compute_rating_score(ps_latest.rating, ps_extra.get("histogram"))
            reviews = _compute_reviews_score(ps_latest.reviews_count, max_reviews_ps)
            freshness = _compute_freshness_score(ps_latest.last_updated)

            ps_total = (
                metadata["total"] * WEIGHTS["metadata"]
                + visual["total"] * WEIGHTS["visual"]
                + rating["total"] * WEIGHTS["rating"]
                + reviews["total"] * WEIGHTS["reviews"]
                + freshness["total"] * WEIGHTS["freshness"]
            )

            entry["playstore"] = {
                "app_name": ps_latest.app_name,
                "app_id": comp.playstore_app_id,
                "rating": ps_latest.rating,
                "reviews_count": ps_latest.reviews_count,
                "downloads": ps_latest.downloads,
                "version": ps_latest.version,
                "last_updated": ps_latest.last_updated.isoformat() if ps_latest.last_updated else None,
                "icon_url": ps_extra.get("icon_url"),
                "screenshot_count": len(ps_extra.get("screenshot_urls", [])),
                "screenshot_urls": ps_extra.get("screenshot_urls", [])[:3],  # First 3 for preview
                "has_video": bool(ps_extra.get("video_url")),
                "has_header_image": bool(ps_extra.get("header_image")),
                "short_description": ps_extra.get("short_description", ""),
                "histogram": ps_extra.get("histogram"),
                "content_rating": ps_extra.get("content_rating"),
                "ad_supported": ps_extra.get("ad_supported", False),
                "in_app_purchases": ps_extra.get("in_app_purchases", False),
                "metadata_score": metadata,
                "visual_score": visual,
                "rating_score": rating,
                "reviews_score": reviews,
                "freshness_score": freshness,
                "aso_score": round(ps_total, 1),
            }
            scores_list.append(ps_total)

        # App Store ASO
        if as_latest:
            metadata = _compute_metadata_score(
                title=as_latest.app_name or "",
                description=as_latest.description or "",
                changelog=as_latest.changelog,
                store="appstore",
            )
            visual = _compute_visual_score(
                screenshot_urls=as_extra.get("screenshot_urls", []),
                video_url=None,  # Not available via API
                icon_url=as_extra.get("icon_url"),
                store="appstore",
            )
            rating = _compute_rating_score(as_latest.rating)
            reviews = _compute_reviews_score(as_latest.reviews_count, max_reviews_as)
            freshness = _compute_freshness_score(as_latest.last_updated)

            as_total = (
                metadata["total"] * WEIGHTS["metadata"]
                + visual["total"] * WEIGHTS["visual"]
                + rating["total"] * WEIGHTS["rating"]
                + reviews["total"] * WEIGHTS["reviews"]
                + freshness["total"] * WEIGHTS["freshness"]
            )

            entry["appstore"] = {
                "app_name": as_latest.app_name,
                "app_id": comp.appstore_app_id,
                "rating": as_latest.rating,
                "reviews_count": as_latest.reviews_count,
                "version": as_latest.version,
                "last_updated": as_latest.last_updated.isoformat() if as_latest.last_updated else None,
                "icon_url": as_extra.get("icon_url"),
                "screenshot_count": len(as_extra.get("screenshot_urls", [])),
                "screenshot_urls": as_extra.get("screenshot_urls", [])[:3],
                "has_video": False,
                "content_rating": as_extra.get("content_rating"),
                "file_size_bytes": as_extra.get("file_size_bytes"),
                "languages_count": len(as_extra.get("languages", [])),
                "current_version_rating": as_extra.get("current_version_rating"),
                "metadata_score": metadata,
                "visual_score": visual,
                "rating_score": rating,
                "reviews_score": reviews,
                "freshness_score": freshness,
                "aso_score": round(as_total, 1),
            }
            scores_list.append(as_total)

        entry["aso_score_avg"] = round(sum(scores_list) / len(scores_list), 1) if scores_list else 0
        competitor_scores.append(entry)

    # Sort by average ASO score
    competitor_scores.sort(key=lambda x: x["aso_score_avg"], reverse=True)

    # Generate recommendations
    recommendations = _generate_aso_recommendations(competitor_scores, brand_name)

    return {
        "competitors": competitor_scores,
        "recommendations": recommendations,
        "brand_name": brand_name,
        "weights": WEIGHTS,
    }
