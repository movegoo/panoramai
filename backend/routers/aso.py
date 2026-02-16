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


def _find_dimension_leader(competitor_scores: list, dim_key: str, store: str | None = None) -> dict | None:
    """Find the competitor with the highest score for a given dimension."""
    best = None
    best_score = -1
    for cs in competitor_scores:
        if store:
            s = cs.get(store, {}).get(f"{dim_key}_score", {}).get("total", 0)
        else:
            ps = cs.get("playstore", {}).get(f"{dim_key}_score", {}).get("total", 0)
            _as = cs.get("appstore", {}).get(f"{dim_key}_score", {}).get("total", 0)
            s = max(ps, _as)
        if s > best_score:
            best_score = s
            best = cs
    return best


def _generate_aso_recommendations(competitor_scores: list, brand_name: str | None) -> list:
    """Generate expert-level ASO recommendations with competitor benchmarking."""
    recs = []
    if not competitor_scores:
        return recs

    brand = next((s for s in competitor_scores if brand_name and s["competitor_name"].lower() == brand_name.lower()), None)
    if not brand:
        return recs

    leader = max(competitor_scores, key=lambda s: s.get("aso_score_avg", 0))
    brand_ps = brand.get("playstore", {})
    brand_as = brand.get("appstore", {})

    # ── 1. Global positioning ──
    brand_avg = brand.get("aso_score_avg", 0)
    leader_avg = leader.get("aso_score_avg", 0)
    gap = leader_avg - brand_avg
    rank = next((i + 1 for i, s in enumerate(competitor_scores) if s["competitor_name"] == brand["competitor_name"]), len(competitor_scores))

    if gap > 5 and leader["competitor_name"] != brand["competitor_name"]:
        recs.append({
            "dimension": "Positionnement global",
            "score": round(brand_avg, 1),
            "priority": "high" if gap > 15 else "medium",
            "advice": f"Vous etes {rank}e/{len(competitor_scores)} en ASO ({brand_avg:.0f}/100). "
                       f"{leader['competitor_name']} mene a {leader_avg:.0f}/100 — ecart de {gap:.0f} pts. "
                       f"Concentrez vos efforts sur les dimensions ou l'ecart est le plus grand pour un impact rapide.",
        })

    # ── 2. Metadata deep-dive ──
    for store_key, store_label in [("playstore", "Play Store"), ("appstore", "App Store")]:
        sd = brand.get(store_key, {})
        if not sd:
            continue
        ms = sd.get("metadata_score", {})
        total = ms.get("total", 0)
        if total >= 80:
            continue

        advices = []
        leader_md = _find_dimension_leader(competitor_scores, "metadata", store_key)
        leader_name = leader_md["competitor_name"] if leader_md else None

        # Title analysis
        title_score = ms.get("title_length", 0)
        title_detail = ms.get("title_length_detail", "")
        app_name = sd.get("app_name", "")
        if title_score < 80:
            advices.append(
                f"Titre ({title_detail}) : votre titre \"{app_name}\" est sous-optimise. "
                f"Sur {store_label}, le titre doit combiner marque + mot-cle principal (ex: \"[Marque] - [benefice cle]\"). "
                f"Visez 25-30 caracteres, chaque mot compte pour l'indexation."
            )

        # Description
        desc_score = ms.get("description_length", 0)
        desc_detail = ms.get("description_length_detail", "")
        if desc_score < 70:
            if store_key == "playstore":
                advices.append(
                    f"Description ({desc_detail}) : Google indexe les 4000 premiers caracteres de la description Play Store. "
                    f"Visez 2500-4000 caracteres avec vos mots-cles cibles dans les 5 premieres lignes (above the fold). "
                    f"Integrez naturellement 3-5 mots-cles principaux avec une densite de 2-3%."
                )
            else:
                advices.append(
                    f"Description ({desc_detail}) : meme si Apple n'indexe pas la description, elle est essentielle pour la conversion. "
                    f"Utilisez les 3 premieres lignes pour accrocher (visibles avant \"En savoir plus\"). "
                    f"Structurez avec des emojis/bullets et focalisez sur les benefices, pas les features."
                )

        # Structure
        struct_score = ms.get("description_structure", 0)
        if struct_score < 80:
            advices.append(
                "Structure de description faible : les listings structures (bullet points ✓, emojis, sous-titres en majuscules) "
                "augmentent le taux de conversion de 15-25%. Segmentez par cas d'usage, pas par fonctionnalite."
            )

        # Short description / subtitle
        sd_score = ms.get("short_description", 0)
        if sd_score < 70 and store_key == "playstore":
            sd_detail = ms.get("short_description_detail", "")
            advices.append(
                f"Description courte ({sd_detail}) : ce champ de 80 caracteres est un des plus importants pour l'indexation Play Store. "
                f"Placez-y votre mot-cle principal + proposition de valeur. C'est aussi le premier texte visible sur la fiche."
            )

        # Changelog
        cl_score = ms.get("changelog", 0)
        if cl_score < 60:
            advices.append(
                "Changelog insuffisant : les notes de version detaillees ameliorent la retention et signalent aux stores que l'app est maintenue. "
                "Decrivez les nouvelles fonctionnalites, corrections de bugs, et ameliorations de performance. "
                "Un bon changelog rassure les utilisateurs hesitants a mettre a jour."
            )

        if advices:
            # Add leader benchmark
            if leader_md and leader_name and leader_name != brand_name:
                leader_ms = leader_md.get(store_key, {}).get("metadata_score", {})
                advices.append(
                    f"Benchmark : {leader_name} obtient {leader_ms.get('total', 0):.0f}/100 en metadata {store_label} vs {total:.0f} pour vous."
                )

            recs.append({
                "dimension": f"Metadata {store_label}",
                "score": round(total, 1),
                "priority": "high" if total < 40 else "medium",
                "advice": " | ".join(advices),
            })

    # ── 3. Visual assets ──
    for store_key, store_label in [("playstore", "Play Store"), ("appstore", "App Store")]:
        sd = brand.get(store_key, {})
        if not sd:
            continue
        vs = sd.get("visual_score", {})
        total = vs.get("total", 0)
        if total >= 85:
            continue

        advices = []
        leader_vis = _find_dimension_leader(competitor_scores, "visual", store_key)

        # Screenshots
        sc_count = sd.get("screenshot_count", 0)
        max_sc = 8 if store_key == "playstore" else 10
        if sc_count < max_sc:
            advices.append(
                f"{sc_count}/{max_sc} screenshots : les fiches avec le maximum de screenshots convertissent 25% mieux. "
                f"Utilisez les 2 premiers pour le message cle (visibles dans les resultats de recherche). "
                f"Privilegiez des screenshots contextuels (lifestyle) plutot que des captures d'ecran brutes. "
                f"Testez le format panorama/paysage qui occupe plus d'espace visuel dans les SERPs."
            )

        # Video
        has_video = sd.get("has_video", False)
        if not has_video:
            if store_key == "playstore":
                advices.append(
                    "Pas de video promotionnelle : les fiches avec video ont un taux d'installation 35% superieur sur Play Store. "
                    "Creez une video de 30-90 secondes axee sur les 3 benefices principaux. "
                    "Les 5 premieres secondes sont critiques — commencez par le probleme resolu, pas par votre logo."
                )
            else:
                advices.append(
                    "Pas d'App Preview : les previews video App Store se lisent en autoplay dans les resultats de recherche. "
                    "C'est un avantage concurrentiel enorme. Limitez a 30 secondes, focalisez sur l'UX in-app."
                )

        # Feature graphic (Play Store only)
        if store_key == "playstore" and not sd.get("has_header_image"):
            advices.append(
                "Pas de feature graphic : cet asset de 1024x500px est affiche en haut de votre fiche et dans les selections editoriales Google. "
                "C'est obligatoire pour etre mis en avant par l'equipe editoriale du Play Store."
            )

        if advices:
            if leader_vis and leader_vis["competitor_name"] != brand_name:
                lv = leader_vis.get(store_key, {})
                advices.append(
                    f"Benchmark : {leader_vis['competitor_name']} a {lv.get('screenshot_count', '?')} screenshots"
                    f"{', une video' if lv.get('has_video') else ''}"
                    f"{', un feature graphic' if lv.get('has_header_image') else ''}"
                    f" ({lv.get('visual_score', {}).get('total', 0):.0f}/100)."
                )

            recs.append({
                "dimension": f"Assets visuels {store_label}",
                "score": round(total, 1),
                "priority": "high" if total < 40 else "medium",
                "advice": " | ".join(advices),
            })

    # ── 4. Rating & reviews strategy ──
    for store_key, store_label in [("playstore", "Play Store"), ("appstore", "App Store")]:
        sd = brand.get(store_key, {})
        if not sd:
            continue
        rs = sd.get("rating_score", {})
        rv = sd.get("reviews_score", {})
        rating = sd.get("rating", 0) or 0
        reviews_count = sd.get("reviews_count", 0) or 0
        rating_total = rs.get("total", 0)
        reviews_total = rv.get("total", 0)

        advices = []

        # Rating analysis
        if rating < 4.0:
            advices.append(
                f"Note critique ({rating:.1f}/5) : en dessous de 4.0, votre taux de conversion chute de 40-50%. "
                f"Priorite absolue : identifiez les crash reports et bugs recurrents dans les avis 1-2 etoiles. "
                f"Repondez systematiquement aux avis negatifs (delai < 24h) — 70% des utilisateurs modifient leur avis apres une reponse."
            )
        elif rating < 4.3:
            advices.append(
                f"Note a optimiser ({rating:.1f}/5) : la moyenne des apps top 100 est de 4.4. "
                f"Implementez un in-app rating prompt (StoreKit pour iOS, Play In-App Review pour Android) "
                f"declenche apres une action positive (achat reussi, milestone atteint, 3 sessions en 7 jours)."
            )
        elif rating < 4.5:
            advices.append(
                f"Bonne note ({rating:.1f}/5), mais optimisable. "
                f"Segmentez vos prompts de notation : demandez un feedback interne aux utilisateurs mecontents "
                f"et redirigez vers le store uniquement les satisfaits (technique du \"happiness gate\")."
            )

        # Histogram analysis
        histogram = rs.get("histogram")
        if histogram and len(histogram) == 5:
            total_r = sum(histogram)
            if total_r > 0:
                one_star_pct = (histogram[0] / total_r) * 100
                if one_star_pct > 15:
                    advices.append(
                        f"Alerte : {one_star_pct:.0f}% d'avis 1 etoile — signe de bugs critiques ou UX frustrant. "
                        f"Analysez les themes recurrents (crash, lenteur, UX, fonctionnalite manquante) pour prioriser votre roadmap."
                    )

        # Review volume
        if reviews_count < 1000:
            advices.append(
                f"Volume d'avis faible ({reviews_count:,}) : un volume eleve d'avis recents ameliore votre indexation. "
                f"Lancez des campagnes de sollicitation ciblees : email post-achat, notification apres une livraison reussie, "
                f"in-app prompt contextuel. Objectif : +50-100 avis/semaine minimum."
            )

        # Benchmark vs leader
        leader_rat = _find_dimension_leader(competitor_scores, "rating", store_key)
        if leader_rat and leader_rat["competitor_name"] != brand_name:
            lr = leader_rat.get(store_key, {})
            lr_rating = lr.get("rating", 0) or 0
            lr_reviews = lr.get("reviews_count", 0) or 0
            if lr_rating > rating or lr_reviews > reviews_count * 2:
                advices.append(
                    f"Benchmark {leader_rat['competitor_name']} : {lr_rating:.1f}/5 avec {lr_reviews:,} avis "
                    f"vs vos {rating:.1f}/5 et {reviews_count:,} avis."
                )

        if advices and (rating_total < 80 or reviews_total < 60):
            recs.append({
                "dimension": f"Notes & avis {store_label}",
                "score": round((rating_total + reviews_total) / 2, 1),
                "priority": "high" if rating < 4.0 or reviews_total < 30 else "medium",
                "advice": " | ".join(advices),
            })

    # ── 5. Freshness & update cadence ──
    brand_ps_fresh = brand_ps.get("freshness_score", {})
    brand_as_fresh = brand_as.get("freshness_score", {})
    ps_days = brand_ps_fresh.get("days_since_update", 999)
    as_days = brand_as_fresh.get("days_since_update", 999)

    # Find competitors' update frequencies
    competitor_days = []
    for cs in competitor_scores:
        if cs["competitor_name"] == brand_name:
            continue
        for sk in ["playstore", "appstore"]:
            d = cs.get(sk, {}).get("freshness_score", {}).get("days_since_update")
            if d is not None:
                competitor_days.append((cs["competitor_name"], d, sk))

    freshness_advices = []
    for store_key, days, store_label in [("playstore", ps_days, "Play Store"), ("appstore", as_days, "App Store")]:
        if days == 999:
            continue
        if days > 60:
            freshness_advices.append(
                f"{store_label} : derniere MAJ il y a {days}j — les algorithmes de classement penalisent les apps inactives. "
                f"Google et Apple favorisent les apps mises a jour regulierement (toutes les 2-4 semaines ideal). "
                f"Meme sans nouvelles fonctionnalites, poussez des correctifs mineurs et des optimisations de performance."
            )
        elif days > 30:
            freshness_advices.append(
                f"{store_label} : MAJ il y a {days}j. Visez un cycle de release toutes les 2-3 semaines. "
                f"Les apps avec des MAJ frequentes apparaissent plus souvent dans les selections editoriales."
            )

    # Competitor freshness benchmark
    if competitor_days:
        faster = [(n, d, s) for n, d, s in competitor_days if d < min(ps_days, as_days)]
        if faster:
            fastest = min(faster, key=lambda x: x[1])
            freshness_advices.append(
                f"{fastest[0]} est plus reactif (MAJ il y a {fastest[1]}j sur {fastest[2]}). "
                f"Un rythme de mise a jour plus frequent ameliore votre ranking et signale un produit vivant aux utilisateurs."
            )

    if freshness_advices:
        avg_fresh = ((brand_ps_fresh.get("total", 0) or 0) + (brand_as_fresh.get("total", 0) or 0)) / max(
            (1 if brand_ps_fresh.get("total") else 0) + (1 if brand_as_fresh.get("total") else 0), 1
        )
        if avg_fresh < 80:
            recs.append({
                "dimension": "Cadence de mise a jour",
                "score": round(avg_fresh, 1),
                "priority": "high" if avg_fresh < 40 else "medium",
                "advice": " | ".join(freshness_advices),
            })

    # ── 6. Cross-store consistency ──
    if brand_ps and brand_as:
        ps_total = brand_ps.get("aso_score", 0)
        as_total = brand_as.get("aso_score", 0)
        store_gap = abs(ps_total - as_total)
        if store_gap > 15:
            weaker = "Play Store" if ps_total < as_total else "App Store"
            stronger = "App Store" if ps_total < as_total else "Play Store"
            recs.append({
                "dimension": "Coherence cross-store",
                "score": round(min(ps_total, as_total), 1),
                "priority": "medium",
                "advice": f"Ecart de {store_gap:.0f} pts entre {stronger} ({max(ps_total, as_total):.0f}/100) et {weaker} ({min(ps_total, as_total):.0f}/100). "
                           f"Les utilisateurs multi-devices attendent une experience coherente. "
                           f"Alignez vos assets visuels, votre messaging et votre cadence de MAJ entre les deux stores. "
                           f"Chaque store a ses specificites (keywords field iOS, description indexee Android) mais la qualite globale doit etre homogene.",
            })

    # ── 7. Conversion Rate Optimization tips (always useful) ──
    # Check if any competitor has significantly better downloads
    if brand_ps:
        brand_downloads = brand_ps.get("downloads", "0")
        try:
            brand_dl_num = int(str(brand_downloads).replace(",", "").replace("+", "").replace(" ", "").replace(".", ""))
        except (ValueError, TypeError):
            brand_dl_num = 0
        brand_rating_val = brand_ps.get("rating", 0) or 0
        brand_sc = brand_ps.get("screenshot_count", 0) or 0

        if brand_dl_num > 0 and brand_rating_val >= 4.0 and brand_sc >= 5:
            # App has basics covered, give advanced CRO tips
            recs.append({
                "dimension": "CRO avance",
                "score": round(brand_avg, 1),
                "priority": "low",
                "advice": "Optimisations avancees pour maximiser votre taux de conversion : "
                           "1) Testez vos screenshots via Google Play Experiments (A/B natif) — variez l'ordre et le messaging. "
                           "2) Localisez votre fiche dans les 5 langues europeennes principales pour capter le trafic organique non-francophone. "
                           "3) Creez des custom store listings par source d'acquisition (campagne UA vs organique). "
                           "4) Monitorez votre taux de retention J1/J7/J30 — un bon ASO attire, mais c'est la retention qui compte pour le ranking long-terme.",
            })

    # Sort: high > medium > low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: (priority_order.get(r["priority"], 2), r.get("score", 100)))

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

    # AI diagnostic (optional, from editable prompt in DB)
    ai_diagnostic = None
    try:
        ai_diagnostic = await _generate_ai_diagnostic(
            competitor_scores, brand_name, brand.sector if brand else ""
        )
    except Exception as e:
        logger.warning(f"ASO AI diagnostic skipped: {e}")

    result = {
        "competitors": competitor_scores,
        "recommendations": recommendations,
        "brand_name": brand_name,
        "weights": WEIGHTS,
    }
    if ai_diagnostic:
        result["ai_diagnostic"] = ai_diagnostic
    return result


async def _generate_ai_diagnostic(
    competitor_scores: list, brand_name: str | None, sector: str
) -> dict | None:
    """Generate an AI-powered ASO diagnostic using the editable prompt template."""
    import httpx
    import os
    from core.config import settings

    api_key = (
        os.getenv("ANTHROPIC_API_KEY", "")
        or os.getenv("CLAUDE_KEY", "")
        or settings.ANTHROPIC_API_KEY
    )
    if not api_key:
        return None

    # Load prompt from DB
    from database import SessionLocal, PromptTemplate
    db = SessionLocal()
    try:
        row = db.query(PromptTemplate).filter(PromptTemplate.key == "aso_analysis").first()
        if not row:
            return None
        prompt_text = row.prompt_text
        model_id = row.model_id or "claude-haiku-4-5-20251001"
        max_tokens = row.max_tokens or 1024
    finally:
        db.close()

    # Build summary data for the prompt (strip heavy detail)
    aso_summary = []
    for cs in competitor_scores:
        entry = {
            "name": cs["competitor_name"],
            "is_brand": cs.get("is_brand", False),
            "aso_score_avg": cs.get("aso_score_avg", 0),
        }
        for store in ["playstore", "appstore"]:
            if store in cs:
                sd = cs[store]
                entry[store] = {
                    "aso_score": sd.get("aso_score", 0),
                    "rating": sd.get("rating"),
                    "reviews_count": sd.get("reviews_count"),
                    "metadata_score": sd.get("metadata_score", {}).get("total", 0),
                    "visual_score": sd.get("visual_score", {}).get("total", 0),
                    "rating_score": sd.get("rating_score", {}).get("total", 0),
                    "freshness_score": sd.get("freshness_score", {}).get("total", 0),
                }
        aso_summary.append(entry)

    import json
    prompt = prompt_text.format(
        brand_name=brand_name or "",
        sector=sector or "",
        aso_data=json.dumps(aso_summary, ensure_ascii=False, indent=2),
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model_id,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        if response.status_code != 200:
            logger.warning(f"ASO AI diagnostic API error: {response.status_code}")
            return None

        text = response.json().get("content", [{}])[0].get("text", "")
        # Parse JSON response
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        return json.loads(text.strip())
    except Exception as e:
        logger.warning(f"ASO AI diagnostic parse error: {e}")
        return None
