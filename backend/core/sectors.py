"""
Secteurs et concurrents pré-configurés.
Base de connaissance métier pour le retail français.
"""

SECTORS = {
    "supermarche": {
        "name": "Grande Distribution",
        "competitors": [
            {
                "name": "Carrefour",
                "website": "https://www.carrefour.fr",
                "playstore_app_id": "com.carrefour.smartphone",
                "appstore_app_id": "378498296",
                "instagram_username": "carrefourfrance",
                "tiktok_username": "carrefourfrance",
                "youtube_channel_id": "UCfhwXXWV0MT9hbXR3SJMXjQ",
            },
            {
                "name": "Leclerc",
                "website": "https://www.e.leclerc",
                "playstore_app_id": "com.eleclerc.moneleclerc",
                "appstore_app_id": "1193842898",
                "instagram_username": "e.leclerc",
                "tiktok_username": "e.leclerc",
            },
            {
                "name": "Auchan",
                "website": "https://www.auchan.fr",
                "playstore_app_id": "com.auchan.auchanfrance",
                "appstore_app_id": "541227977",
                "instagram_username": "auchan_france",
            },
            {
                "name": "Intermarché",
                "website": "https://www.intermarche.com",
                "playstore_app_id": "com.intermarche.mobile.courses",
                "appstore_app_id": "1447048498",
                "instagram_username": "intermarche",
            },
            {
                "name": "Lidl",
                "website": "https://www.lidl.fr",
                "playstore_app_id": "com.lidl.eci.lidlplus",
                "appstore_app_id": "1276382498",
                "instagram_username": "lidlfrance",
                "tiktok_username": "lidlfrance",
            },
            {
                "name": "Monoprix",
                "website": "https://www.monoprix.fr",
                "playstore_app_id": "fr.monoprix.monoprix",
                "appstore_app_id": "966459890",
                "instagram_username": "monoprix",
            },
        ],
    },
    "mode": {
        "name": "Mode & Habillement",
        "competitors": [
            {
                "name": "Zara",
                "website": "https://www.zara.com/fr",
                "playstore_app_id": "com.inditex.zara",
                "appstore_app_id": "547347221",
                "instagram_username": "zara",
                "tiktok_username": "zara",
            },
            {
                "name": "H&M",
                "website": "https://www.hm.com/fr",
                "playstore_app_id": "com.hm.goe",
                "appstore_app_id": "834465911",
                "instagram_username": "hm",
                "tiktok_username": "hm",
            },
            {
                "name": "Kiabi",
                "website": "https://www.kiabi.com",
                "playstore_app_id": "com.kiabi.app",
                "appstore_app_id": "495571498",
                "instagram_username": "kiabi_official",
            },
            {
                "name": "Decathlon",
                "website": "https://www.decathlon.fr",
                "playstore_app_id": "com.decathlon.app",
                "appstore_app_id": "1079647629",
                "instagram_username": "decathlon",
                "tiktok_username": "decathlon",
            },
        ],
    },
    "beaute": {
        "name": "Beauté & Cosmétiques",
        "competitors": [
            {
                "name": "Sephora",
                "website": "https://www.sephora.fr",
                "playstore_app_id": "com.sephora.android",
                "appstore_app_id": "393328150",
                "instagram_username": "sephorafrance",
                "tiktok_username": "sephora",
            },
            {
                "name": "Nocibé",
                "website": "https://www.nocibe.fr",
                "playstore_app_id": "com.douglas.nocibe",
                "appstore_app_id": "1123649654",
                "instagram_username": "nocibe_france",
            },
            {
                "name": "Yves Rocher",
                "website": "https://www.yves-rocher.fr",
                "playstore_app_id": "com.ysl.yvesrocher",
                "instagram_username": "yvesrocherusa",
            },
        ],
    },
    "electromenager": {
        "name": "Électroménager & High-Tech",
        "competitors": [
            {
                "name": "Darty",
                "website": "https://www.darty.com",
                "playstore_app_id": "com.darty.app",
                "appstore_app_id": "352210890",
                "instagram_username": "darty_officiel",
            },
            {
                "name": "Boulanger",
                "website": "https://www.boulanger.com",
                "playstore_app_id": "fr.boulanger.shoppingapp",
                "appstore_app_id": "412042787",
                "instagram_username": "boulanger",
            },
            {
                "name": "Fnac",
                "website": "https://www.fnac.com",
                "playstore_app_id": "com.fnac.android",
                "appstore_app_id": "378498309",
                "instagram_username": "fnac_officiel",
            },
        ],
    },
    "bricolage": {
        "name": "Bricolage & Maison",
        "competitors": [
            {
                "name": "Leroy Merlin",
                "website": "https://www.leroymerlin.fr",
                "playstore_app_id": "com.leroymerlin.franceapp",
                "appstore_app_id": "522478918",
                "instagram_username": "leroymerlin",
            },
            {
                "name": "Castorama",
                "website": "https://www.castorama.fr",
                "playstore_app_id": "com.castorama.selfcare",
                "appstore_app_id": "1163490666",
                "instagram_username": "castoramafrance",
            },
        ],
    },
}


def get_sector_label(sector_code: str) -> str:
    """Retourne le nom complet d'un secteur."""
    return SECTORS.get(sector_code, {}).get("name", sector_code)


def get_competitors_for_sector(sector_code: str) -> list:
    """Retourne la liste des concurrents pré-configurés pour un secteur."""
    return SECTORS.get(sector_code, {}).get("competitors", [])


def list_sectors() -> list:
    """Retourne la liste des secteurs disponibles."""
    return [
        {"code": code, "name": data["name"], "competitors_count": len(data["competitors"])}
        for code, data in SECTORS.items()
    ]
