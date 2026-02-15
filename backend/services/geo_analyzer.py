"""
GEO (Generative Engine Optimization) Analyzer.
Queries Claude, Gemini and ChatGPT with sector-specific questions, then analyses
which brands are mentioned, recommended, and in what order.
"""
import asyncio
import json
import logging
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sector-specific GEO queries
# ---------------------------------------------------------------------------

SECTOR_QUERIES: dict[str, list[dict]] = {
    "supermarche": [
        {"keyword": "courses en ligne", "query": "Quel est le meilleur service de courses en ligne en France ?"},
        {"keyword": "drive supermarche", "query": "Quel supermarche propose le meilleur service drive en France ?"},
        {"keyword": "livraison courses domicile", "query": "Quel service de livraison de courses a domicile recommandes-tu en France ?"},
        {"keyword": "promo supermarche", "query": "Quel supermarche propose les meilleures promotions en France ?"},
        {"keyword": "carte fidelite supermarche", "query": "Quelle est la meilleure carte de fidelite de supermarche en France ?"},
        {"keyword": "supermarche pas cher", "query": "Quel est le supermarche le moins cher en France ?"},
        {"keyword": "application courses", "query": "Quelle est la meilleure application pour faire ses courses en France ?"},
        {"keyword": "produits bio supermarche", "query": "Quel supermarche a le meilleur rayon bio en France ?"},
        {"keyword": "click and collect courses", "query": "Quel supermarche propose le meilleur click and collect en France ?"},
        {"keyword": "meilleur supermarche", "query": "Quel est le meilleur supermarche en France en 2026 ?"},
        {"keyword": "comparatif prix supermarche", "query": "Comparatif des prix entre les grandes enseignes : quel supermarche est le moins cher ?"},
        {"keyword": "marque distributeur", "query": "Quel supermarche a les meilleures marques distributeur en France ?"},
    ],
    "mode": [
        {"keyword": "meilleure marque mode", "query": "Quelles sont les meilleures marques de mode abordable en France ?"},
        {"keyword": "mode en ligne", "query": "Quel est le meilleur site de mode en ligne en France ?"},
        {"keyword": "vetements tendance", "query": "Ou acheter des vetements tendance a petit prix en France ?"},
        {"keyword": "fast fashion france", "query": "Quelles sont les enseignes de fast fashion les plus populaires en France ?"},
        {"keyword": "mode durable", "query": "Quelle marque de mode propose les meilleurs vetements durables en France ?"},
        {"keyword": "application mode", "query": "Quelle est la meilleure application pour acheter des vetements en France ?"},
        {"keyword": "soldes mode", "query": "Quelle enseigne de mode propose les meilleures soldes en France ?"},
        {"keyword": "mode homme", "query": "Ou acheter des vetements homme tendance et pas cher en France ?"},
        {"keyword": "mode femme", "query": "Quelles sont les meilleures enseignes de mode femme en France ?"},
        {"keyword": "programme fidelite mode", "query": "Quelle enseigne de mode a le meilleur programme de fidelite ?"},
        {"keyword": "livraison vetements", "query": "Quel site de mode offre la livraison la plus rapide en France ?"},
        {"keyword": "mode enfant", "query": "Ou acheter des vetements enfant de qualite a bon prix en France ?"},
    ],
    "beaute": [
        {"keyword": "meilleure parfumerie", "query": "Quelle est la meilleure parfumerie en France ?"},
        {"keyword": "cosmetiques en ligne", "query": "Quel est le meilleur site pour acheter des cosmetiques en ligne en France ?"},
        {"keyword": "soins visage", "query": "Ou acheter les meilleurs soins visage en France ?"},
        {"keyword": "maquillage pas cher", "query": "Quelle enseigne propose le meilleur maquillage a petit prix en France ?"},
        {"keyword": "beaute bio", "query": "Quelle enseigne propose la meilleure selection de beaute bio en France ?"},
        {"keyword": "programme fidelite beaute", "query": "Quelle enseigne de beaute a le meilleur programme de fidelite ?"},
        {"keyword": "application beaute", "query": "Quelle est la meilleure application beaute en France ?"},
        {"keyword": "parfum pas cher", "query": "Ou acheter du parfum de marque au meilleur prix en France ?"},
        {"keyword": "coffret beaute", "query": "Quelle enseigne propose les meilleurs coffrets beaute ?"},
        {"keyword": "conseil beaute", "query": "Quelle enseigne offre les meilleurs conseils beaute personnalises ?"},
        {"keyword": "livraison beaute", "query": "Quel site de beaute a la meilleure livraison en France ?"},
        {"keyword": "marques exclusives beaute", "query": "Quelle parfumerie a les meilleures marques exclusives ?"},
    ],
    "electromenager": [
        {"keyword": "meilleur electromenager", "query": "Quelle est la meilleure enseigne d'electromenager en France ?"},
        {"keyword": "electromenager en ligne", "query": "Quel est le meilleur site pour acheter de l'electromenager en France ?"},
        {"keyword": "electromenager pas cher", "query": "Ou acheter de l'electromenager au meilleur prix en France ?"},
        {"keyword": "service apres-vente", "query": "Quelle enseigne d'electromenager a le meilleur SAV en France ?"},
        {"keyword": "television", "query": "Ou acheter une television au meilleur prix en France ?"},
        {"keyword": "smartphone", "query": "Quelle enseigne propose les meilleurs prix sur les smartphones en France ?"},
        {"keyword": "livraison electromenager", "query": "Quelle enseigne d'electromenager a la meilleure livraison et installation ?"},
        {"keyword": "comparatif electromenager", "query": "Comparatif des enseignes d'electromenager : laquelle est la meilleure ?"},
        {"keyword": "garantie electromenager", "query": "Quelle enseigne propose la meilleure garantie sur l'electromenager ?"},
        {"keyword": "reconditionne", "query": "Ou acheter des produits high-tech reconditionnes de qualite en France ?"},
        {"keyword": "application high-tech", "query": "Quelle enseigne tech a la meilleure application mobile ?"},
        {"keyword": "promotions tech", "query": "Quelle enseigne propose les meilleures promos sur la tech en France ?"},
    ],
    "bricolage": [
        {"keyword": "meilleur magasin bricolage", "query": "Quel est le meilleur magasin de bricolage en France ?"},
        {"keyword": "bricolage en ligne", "query": "Quel est le meilleur site de bricolage en ligne en France ?"},
        {"keyword": "bricolage pas cher", "query": "Ou acheter du materiel de bricolage au meilleur prix en France ?"},
        {"keyword": "conseil bricolage", "query": "Quelle enseigne de bricolage offre les meilleurs conseils ?"},
        {"keyword": "peinture", "query": "Ou acheter de la peinture au meilleur rapport qualite-prix en France ?"},
        {"keyword": "outillage", "query": "Quelle enseigne a le meilleur rayon outillage en France ?"},
        {"keyword": "livraison bricolage", "query": "Quelle enseigne de bricolage propose la meilleure livraison a domicile ?"},
        {"keyword": "renovation maison", "query": "Quelle enseigne recommandes-tu pour un projet de renovation en France ?"},
        {"keyword": "salle de bain", "query": "Ou acheter une salle de bain complete au meilleur prix en France ?"},
        {"keyword": "jardin et exterieur", "query": "Quelle enseigne de bricolage a le meilleur rayon jardin ?"},
        {"keyword": "carte fidelite bricolage", "query": "Quelle enseigne de bricolage a le meilleur programme de fidelite ?"},
        {"keyword": "location outillage", "query": "Quelle enseigne de bricolage propose le meilleur service de location d'outils ?"},
    ],
    "sport": [
        {"keyword": "meilleur magasin sport", "query": "Quel est le meilleur magasin de sport en France ?"},
        {"keyword": "equipement sport en ligne", "query": "Quel est le meilleur site pour acheter du materiel de sport en France ?"},
        {"keyword": "sport pas cher", "query": "Ou acheter du materiel de sport au meilleur prix en France ?"},
        {"keyword": "chaussures running", "query": "Ou acheter des chaussures de running au meilleur prix en France ?"},
        {"keyword": "velo", "query": "Quelle enseigne propose les meilleurs velos en France ?"},
        {"keyword": "fitness", "query": "Ou acheter du materiel de fitness au meilleur prix en France ?"},
        {"keyword": "randonnee", "query": "Quelle enseigne de sport est la meilleure pour la randonnee ?"},
        {"keyword": "sport enfant", "query": "Ou acheter de l'equipement de sport pour enfant en France ?"},
        {"keyword": "marque distributeur sport", "query": "Quelle enseigne de sport a les meilleures marques distributeur ?"},
        {"keyword": "application sport", "query": "Quelle enseigne de sport a la meilleure application mobile ?"},
        {"keyword": "seconde main sport", "query": "Quelle enseigne propose le meilleur service de seconde main pour le sport ?"},
        {"keyword": "conseil sport", "query": "Quelle enseigne de sport offre les meilleurs conseils personnalises ?"},
    ],
    "ameublement": [
        {"keyword": "meilleur magasin meubles", "query": "Quel est le meilleur magasin de meubles en France ?"},
        {"keyword": "meubles en ligne", "query": "Quel est le meilleur site pour acheter des meubles en ligne en France ?"},
        {"keyword": "meubles pas cher", "query": "Ou acheter des meubles pas cher et de qualite en France ?"},
        {"keyword": "decoration interieure", "query": "Quelle est la meilleure enseigne de decoration interieure en France ?"},
        {"keyword": "canape", "query": "Ou acheter un canape au meilleur rapport qualite-prix en France ?"},
        {"keyword": "cuisine equipee", "query": "Quelle enseigne propose les meilleures cuisines equipees en France ?"},
        {"keyword": "meuble scandinave", "query": "Ou acheter des meubles de style scandinave en France ?"},
        {"keyword": "literie", "query": "Quelle enseigne propose la meilleure literie en France ?"},
        {"keyword": "rangement", "query": "Quelle enseigne a les meilleures solutions de rangement ?"},
        {"keyword": "livraison meuble", "query": "Quelle enseigne de meubles a la meilleure livraison et montage ?"},
        {"keyword": "deco tendance", "query": "Quelle enseigne propose la decoration la plus tendance en 2026 ?"},
        {"keyword": "comparatif meubles", "query": "Comparatif des enseignes de meubles et deco : laquelle est la meilleure en France ?"},
    ],
    "restauration": [
        {"keyword": "meilleure chaine restaurant", "query": "Quelle est la meilleure chaine de restaurant en France ?"},
        {"keyword": "fast food france", "query": "Quel est le meilleur fast food en France ?"},
        {"keyword": "livraison repas", "query": "Quelle chaine de restaurant propose la meilleure livraison ?"},
        {"keyword": "burger", "query": "Quelle chaine de fast food fait les meilleurs burgers en France ?"},
        {"keyword": "restaurant pas cher", "query": "Quelle chaine de restaurant offre le meilleur rapport qualite-prix ?"},
        {"keyword": "application restaurant", "query": "Quelle chaine de restaurant a la meilleure application mobile ?"},
        {"keyword": "menu enfant", "query": "Quelle chaine de restaurant a le meilleur menu enfant ?"},
        {"keyword": "programme fidelite restaurant", "query": "Quelle chaine de restaurant a le meilleur programme de fidelite ?"},
        {"keyword": "restaurant healthy", "query": "Quelle chaine de restaurant propose les meilleures options healthy ?"},
        {"keyword": "petit dejeuner", "query": "Quelle chaine propose le meilleur petit-dejeuner en France ?"},
        {"keyword": "restaurant drive", "query": "Quel fast food a le meilleur service drive en France ?"},
        {"keyword": "pizza chaine", "query": "Quelle chaine de pizza est la meilleure en France ?"},
    ],
    "pharmacie": [
        {"keyword": "meilleure pharmacie en ligne", "query": "Quelle est la meilleure pharmacie en ligne en France ?"},
        {"keyword": "parapharmacie", "query": "Ou acheter de la parapharmacie au meilleur prix en France ?"},
        {"keyword": "medicaments en ligne", "query": "Quelle pharmacie en ligne est la plus fiable en France ?"},
        {"keyword": "cosmetiques pharmacie", "query": "Quelle enseigne de pharmacie a le meilleur rayon cosmetiques ?"},
        {"keyword": "pharmacie pas cher", "query": "Quelle pharmacie propose les meilleurs prix en France ?"},
        {"keyword": "livraison pharmacie", "query": "Quelle pharmacie propose la meilleure livraison en France ?"},
        {"keyword": "conseil pharmacie", "query": "Quelle enseigne de pharmacie offre les meilleurs conseils sante ?"},
        {"keyword": "vitamines complements", "query": "Ou acheter des vitamines et complements au meilleur prix en France ?"},
        {"keyword": "pharmacie bio", "query": "Quelle pharmacie a la meilleure selection de produits bio et naturels ?"},
        {"keyword": "application pharmacie", "query": "Quelle pharmacie a la meilleure application mobile ?"},
        {"keyword": "programme fidelite pharmacie", "query": "Quelle pharmacie a le meilleur programme de fidelite ?"},
        {"keyword": "pharmacie de garde", "query": "Quelle application ou enseigne facilite la recherche de pharmacie de garde ?"},
    ],
    "optique": [
        {"keyword": "meilleur opticien", "query": "Quel est le meilleur opticien en France ?"},
        {"keyword": "lunettes en ligne", "query": "Quel est le meilleur site pour acheter des lunettes en ligne en France ?"},
        {"keyword": "lunettes pas cher", "query": "Ou acheter des lunettes au meilleur prix en France ?"},
        {"keyword": "lentilles de contact", "query": "Ou acheter des lentilles de contact au meilleur prix en France ?"},
        {"keyword": "lunettes de soleil", "query": "Quel opticien propose les meilleures lunettes de soleil ?"},
        {"keyword": "mutuelle opticien", "query": "Quel opticien propose le meilleur remboursement mutuelle ?"},
        {"keyword": "examen vue", "query": "Quel opticien propose le meilleur service d'examen de vue ?"},
        {"keyword": "verres progressifs", "query": "Quel opticien est le meilleur pour les verres progressifs ?"},
        {"keyword": "application opticien", "query": "Quel opticien a la meilleure application mobile ?"},
        {"keyword": "essayage virtuel lunettes", "query": "Quel opticien propose le meilleur essayage virtuel de lunettes ?"},
        {"keyword": "comparatif opticiens", "query": "Comparatif des opticiens en France : lequel est le meilleur ?"},
        {"keyword": "garantie lunettes", "query": "Quel opticien offre la meilleure garantie sur les lunettes ?"},
    ],
    "telecom": [
        {"keyword": "meilleur operateur", "query": "Quel est le meilleur operateur telecom en France ?"},
        {"keyword": "forfait mobile pas cher", "query": "Quel operateur propose le forfait mobile le moins cher en France ?"},
        {"keyword": "fibre optique", "query": "Quel operateur propose la meilleure fibre optique en France ?"},
        {"keyword": "couverture reseau", "query": "Quel operateur a la meilleure couverture reseau en France ?"},
        {"keyword": "5G france", "query": "Quel operateur a le meilleur reseau 5G en France ?"},
        {"keyword": "box internet", "query": "Quelle est la meilleure box internet en France ?"},
        {"keyword": "service client telecom", "query": "Quel operateur a le meilleur service client ?"},
        {"keyword": "forfait sans engagement", "query": "Quel est le meilleur forfait mobile sans engagement ?"},
        {"keyword": "application operateur", "query": "Quel operateur a la meilleure application mobile ?"},
        {"keyword": "comparatif operateurs", "query": "Comparatif des operateurs mobiles en France : lequel choisir ?"},
        {"keyword": "forfait famille", "query": "Quel operateur propose les meilleurs forfaits famille ?"},
        {"keyword": "roaming international", "query": "Quel operateur propose le meilleur forfait pour voyager ?"},
    ],
    "banque": [
        {"keyword": "meilleure banque", "query": "Quelle est la meilleure banque en France ?"},
        {"keyword": "banque en ligne", "query": "Quelle est la meilleure banque en ligne en France ?"},
        {"keyword": "compte gratuit", "query": "Quelle banque propose le meilleur compte gratuit ?"},
        {"keyword": "credit immobilier", "query": "Quelle banque propose le meilleur taux de credit immobilier ?"},
        {"keyword": "application bancaire", "query": "Quelle banque a la meilleure application mobile ?"},
        {"keyword": "carte bancaire", "query": "Quelle banque propose la meilleure carte bancaire ?"},
        {"keyword": "service client banque", "query": "Quelle banque a le meilleur service client ?"},
        {"keyword": "epargne", "query": "Quelle banque propose les meilleurs produits d'epargne ?"},
        {"keyword": "neobanque", "query": "Quelle est la meilleure neobanque en France ?"},
        {"keyword": "assurance banque", "query": "Quelle banque propose les meilleures assurances ?"},
        {"keyword": "paiement mobile", "query": "Quelle banque propose le meilleur service de paiement mobile ?"},
        {"keyword": "banque jeune", "query": "Quelle est la meilleure banque pour les jeunes en France ?"},
    ],
    "jardinerie": [
        {"keyword": "meilleure jardinerie", "query": "Quelle est la meilleure jardinerie en France ?"},
        {"keyword": "plantes en ligne", "query": "Quel est le meilleur site pour acheter des plantes en ligne en France ?"},
        {"keyword": "jardinerie pas cher", "query": "Quelle jardinerie propose les meilleurs prix en France ?"},
        {"keyword": "animalerie", "query": "Quelle jardinerie a le meilleur rayon animalerie ?"},
        {"keyword": "conseil jardinage", "query": "Quelle jardinerie offre les meilleurs conseils jardinage ?"},
        {"keyword": "amenagement exterieur", "query": "Quelle enseigne est la meilleure pour l'amenagement de jardin ?"},
        {"keyword": "salon de jardin", "query": "Ou acheter un salon de jardin au meilleur prix ?"},
        {"keyword": "terreau et engrais", "query": "Quelle jardinerie a le meilleur choix de terreau et engrais ?"},
        {"keyword": "jardinerie bio", "query": "Quelle jardinerie propose la meilleure selection bio ?"},
        {"keyword": "application jardinerie", "query": "Quelle jardinerie a la meilleure application mobile ?"},
        {"keyword": "livraison jardinerie", "query": "Quelle jardinerie propose la meilleure livraison a domicile ?"},
        {"keyword": "programme fidelite jardinerie", "query": "Quelle jardinerie a le meilleur programme de fidelite ?"},
    ],
    "jouets": [
        {"keyword": "meilleur magasin jouets", "query": "Quel est le meilleur magasin de jouets en France ?"},
        {"keyword": "jouets en ligne", "query": "Quel est le meilleur site pour acheter des jouets en ligne en France ?"},
        {"keyword": "jouets pas cher", "query": "Ou acheter des jouets au meilleur prix en France ?"},
        {"keyword": "noel jouets", "query": "Quelle enseigne recommandes-tu pour acheter les cadeaux de Noel ?"},
        {"keyword": "jeux educatifs", "query": "Ou trouver les meilleurs jeux educatifs en France ?"},
        {"keyword": "lego", "query": "Quelle enseigne a le meilleur choix de Lego en France ?"},
        {"keyword": "jeux de societe", "query": "Ou acheter les meilleurs jeux de societe en France ?"},
        {"keyword": "jouets bebe", "query": "Quelle enseigne propose les meilleurs jouets pour bebe ?"},
        {"keyword": "livraison jouets", "query": "Quelle enseigne de jouets a la meilleure livraison ?"},
        {"keyword": "catalogue jouets", "query": "Quelle enseigne de jouets a le catalogue le plus complet ?"},
        {"keyword": "jouets durables", "query": "Quelle enseigne propose les meilleurs jouets eco-responsables ?"},
        {"keyword": "programme fidelite jouets", "query": "Quelle enseigne de jouets a le meilleur programme de fidelite ?"},
    ],
    "luxe": [
        {"keyword": "meilleure marque luxe", "query": "Quelles sont les meilleures marques de luxe francaises ?"},
        {"keyword": "maroquinerie luxe", "query": "Quelle marque de luxe propose la meilleure maroquinerie ?"},
        {"keyword": "luxe en ligne", "query": "Quel est le meilleur site pour acheter du luxe en ligne ?"},
        {"keyword": "joaillerie luxe", "query": "Quelle est la meilleure maison de joaillerie de luxe ?"},
        {"keyword": "parfum luxe", "query": "Quelle marque de luxe fait les meilleurs parfums ?"},
        {"keyword": "mode luxe homme", "query": "Quelle est la meilleure marque de mode luxe homme ?"},
        {"keyword": "mode luxe femme", "query": "Quelle est la meilleure marque de mode luxe femme ?"},
        {"keyword": "montre luxe", "query": "Quelle marque de montre de luxe recommandes-tu ?"},
        {"keyword": "experience client luxe", "query": "Quelle maison de luxe offre la meilleure experience client ?"},
        {"keyword": "luxe durable", "query": "Quelle marque de luxe est la plus engagee en developpement durable ?"},
        {"keyword": "outlet luxe", "query": "Ou acheter du luxe a prix reduit en France ?"},
        {"keyword": "investissement luxe", "query": "Quels articles de luxe prennent le plus de valeur avec le temps ?"},
    ],
    "voyage": [
        {"keyword": "meilleure agence voyage", "query": "Quelle est la meilleure agence de voyage en France ?"},
        {"keyword": "voyage en ligne", "query": "Quel est le meilleur site pour reserver un voyage en ligne ?"},
        {"keyword": "vol pas cher", "query": "Quel site propose les vols les moins chers ?"},
        {"keyword": "hotel pas cher", "query": "Quel site propose les meilleurs tarifs d'hotel ?"},
        {"keyword": "voyage tout compris", "query": "Quelle agence propose les meilleurs voyages tout compris ?"},
        {"keyword": "location vacances", "query": "Quel site est le meilleur pour la location de vacances ?"},
        {"keyword": "croisiere", "query": "Quelle compagnie de croisiere est la meilleure ?"},
        {"keyword": "assurance voyage", "query": "Quelle assurance voyage recommandes-tu ?"},
        {"keyword": "application voyage", "query": "Quelle est la meilleure application de voyage ?"},
        {"keyword": "comparateur voyage", "query": "Quel est le meilleur comparateur de voyages en France ?"},
        {"keyword": "sejour ski", "query": "Quel site est le meilleur pour reserver un sejour au ski ?"},
        {"keyword": "voyage derniere minute", "query": "Quel site propose les meilleures offres de derniere minute ?"},
    ],
    "bio": [
        {"keyword": "meilleur magasin bio", "query": "Quel est le meilleur magasin bio en France ?"},
        {"keyword": "bio en ligne", "query": "Quel est le meilleur site pour acheter du bio en ligne en France ?"},
        {"keyword": "bio pas cher", "query": "Ou acheter des produits bio au meilleur prix en France ?"},
        {"keyword": "panier bio", "query": "Quel service de panier bio livre recommandes-tu ?"},
        {"keyword": "vrac bio", "query": "Quel magasin bio a le meilleur rayon vrac ?"},
        {"keyword": "cosmetiques bio", "query": "Ou acheter les meilleurs cosmetiques bio en France ?"},
        {"keyword": "fruits legumes bio", "query": "Ou acheter les meilleurs fruits et legumes bio en France ?"},
        {"keyword": "supermarche bio", "query": "Quel supermarche bio recommandes-tu en France ?"},
        {"keyword": "complement alimentaire bio", "query": "Ou acheter des complements alimentaires bio de qualite ?"},
        {"keyword": "application bio", "query": "Quelle application aide a trouver des produits bio ?"},
        {"keyword": "marque distributeur bio", "query": "Quel magasin bio a les meilleures marques distributeur ?"},
        {"keyword": "livraison bio", "query": "Quel magasin bio propose la meilleure livraison a domicile ?"},
    ],
    "automobile": [
        {"keyword": "meilleur concessionnaire", "query": "Quel est le meilleur concessionnaire automobile en France ?"},
        {"keyword": "voiture neuve", "query": "Ou acheter une voiture neuve au meilleur prix en France ?"},
        {"keyword": "voiture occasion", "query": "Quel est le meilleur site pour acheter une voiture d'occasion en France ?"},
        {"keyword": "voiture electrique", "query": "Quelle marque propose les meilleures voitures electriques ?"},
        {"keyword": "leasing voiture", "query": "Quelle enseigne propose le meilleur leasing automobile ?"},
        {"keyword": "entretien voiture", "query": "Quel garage ou enseigne propose le meilleur entretien auto en France ?"},
        {"keyword": "assurance auto", "query": "Quelle assurance auto est la meilleure en France ?"},
        {"keyword": "comparateur auto", "query": "Quel est le meilleur comparateur de voitures en France ?"},
        {"keyword": "pneus", "query": "Ou acheter des pneus au meilleur prix en France ?"},
        {"keyword": "pieces auto", "query": "Ou acheter des pieces auto au meilleur prix en France ?"},
        {"keyword": "application auto", "query": "Quelle est la meilleure application automobile ?"},
        {"keyword": "SUV france", "query": "Quel est le meilleur SUV disponible en France ?"},
    ],
}


def _generate_fallback_queries(sector_label: str, brand_names: list[str]) -> list[dict]:
    """Generate generic queries for unknown sectors."""
    brands_str = ", ".join(brand_names[:4])
    return [
        {"keyword": f"meilleur {sector_label}", "query": f"Quelle est la meilleure enseigne de {sector_label} en France ?"},
        {"keyword": f"{sector_label} en ligne", "query": f"Quel est le meilleur site de {sector_label} en ligne en France ?"},
        {"keyword": f"{sector_label} pas cher", "query": f"Ou trouver les meilleurs prix en {sector_label} en France ?"},
        {"keyword": f"comparatif {sector_label}", "query": f"Comparatif entre {brands_str} : lequel est le meilleur ?"},
        {"keyword": f"application {sector_label}", "query": f"Quelle enseigne de {sector_label} a la meilleure application mobile ?"},
        {"keyword": f"fidelite {sector_label}", "query": f"Quelle enseigne de {sector_label} a le meilleur programme de fidelite ?"},
        {"keyword": f"avis {sector_label}", "query": f"Quelle est l'enseigne de {sector_label} la mieux notee par les clients ?"},
        {"keyword": f"livraison {sector_label}", "query": f"Quelle enseigne de {sector_label} propose la meilleure livraison ?"},
        {"keyword": f"service client {sector_label}", "query": f"Quelle enseigne de {sector_label} a le meilleur service client ?"},
        {"keyword": f"tendances {sector_label}", "query": f"Quelles sont les tendances en {sector_label} en France en 2026 ?"},
        {"keyword": f"conseil {sector_label}", "query": f"Quelle enseigne de {sector_label} offre les meilleurs conseils ?"},
        {"keyword": f"durabilite {sector_label}", "query": f"Quelle enseigne de {sector_label} est la plus engagee en RSE ?"},
    ]


def get_geo_queries(sector: str, sector_label: str, brand_names: list[str]) -> list[dict]:
    """Get GEO queries for a given sector."""
    return SECTOR_QUERIES.get(sector, _generate_fallback_queries(sector_label, brand_names))


SYSTEM_PROMPT = (
    "Tu es un assistant qui aide les consommateurs francais a choisir "
    "les meilleures enseignes et marques. Reponds de facon concise "
    "et factuelle, en citant les enseignes par leur nom."
)

ANALYSIS_PROMPT = """Analyse cette reponse d'un moteur IA a la question "{query}".
Identifie les marques mentionnees parmi : {brand_names}.

Reponds UNIQUEMENT avec du JSON valide, sans markdown ni texte autour.
JSON attendu :
{{
  "brands_mentioned": [
    {{
      "name": "NomMarque",
      "position": 1,
      "recommended": true,
      "sentiment": "positif",
      "context": "cite comme leader du drive"
    }}
  ],
  "total_brands_mentioned": 3,
  "primary_recommendation": "NomMarque",
  "answer_quality": "comparative",
  "key_criteria": ["prix", "reseau", "qualite"]
}}

IMPORTANT: Cherche TOUTES les variantes des noms de marques (avec/sans accents, abreviations, etc.).
Par exemple "E.Leclerc" = "Leclerc", "IKEA" = "Ikea", etc.
Si une marque de la liste est mentionnee, elle DOIT figurer dans brands_mentioned.

Reponse a analyser :
{answer}"""


class GeoAnalyzer:
    """Queries AI engines and analyses brand visibility in their responses."""

    def __init__(self):
        self.errors: list[str] = []

    def get_available_platforms(self) -> dict[str, bool]:
        """Check which API keys are configured."""
        return {
            "claude": bool(settings.ANTHROPIC_API_KEY),
            "gemini": bool(settings.GEMINI_API_KEY),
            "chatgpt": bool(settings.OPENAI_API_KEY),
            "mistral": bool(settings.MISTRAL_API_KEY),
        }

    async def _query_claude(self, query: str) -> str:
        """Query Claude Haiku via Anthropic API."""
        if not settings.ANTHROPIC_API_KEY:
            self.errors.append("claude: ANTHROPIC_API_KEY manquante")
            return ""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 1000,
                        "system": SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": query}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]
        except httpx.HTTPStatusError as e:
            msg = f"claude: HTTP {e.response.status_code}"
            try:
                body = e.response.json()
                msg += f" - {body.get('error', {}).get('message', str(body))}"
            except Exception:
                pass
            logger.error(f"Claude query error: {msg}")
            self.errors.append(msg)
            return ""
        except Exception as e:
            msg = f"claude: {type(e).__name__}: {e}"
            logger.error(f"Claude query error: {msg}")
            self.errors.append(msg)
            return ""

    async def _query_gemini(self, query: str) -> str:
        """Query Gemini via Google AI REST API."""
        if not settings.GEMINI_API_KEY:
            self.errors.append("gemini: GEMINI_API_KEY manquante")
            return ""
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}"
            )
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    headers={"content-type": "application/json"},
                    json={
                        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                        "contents": [{"parts": [{"text": query}]}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except httpx.HTTPStatusError as e:
            msg = f"gemini: HTTP {e.response.status_code}"
            try:
                body = e.response.json()
                msg += f" - {body.get('error', {}).get('message', str(body))}"
            except Exception:
                pass
            logger.error(f"Gemini query error: {msg}")
            self.errors.append(msg)
            return ""
        except Exception as e:
            msg = f"gemini: {type(e).__name__}: {e}"
            logger.error(f"Gemini query error: {msg}")
            self.errors.append(msg)
            return ""

    async def _query_chatgpt(self, query: str) -> str:
        """Query ChatGPT via OpenAI API."""
        if not settings.OPENAI_API_KEY:
            self.errors.append("chatgpt: OPENAI_API_KEY manquante")
            return ""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "max_tokens": 1000,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": query},
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            msg = f"chatgpt: HTTP {e.response.status_code}"
            try:
                body = e.response.json()
                msg += f" - {body.get('error', {}).get('message', str(body))}"
            except Exception:
                pass
            logger.error(f"ChatGPT query error: {msg}")
            self.errors.append(msg)
            return ""
        except Exception as e:
            msg = f"chatgpt: {type(e).__name__}: {e}"
            logger.error(f"ChatGPT query error: {msg}")
            self.errors.append(msg)
            return ""

    async def _query_mistral(self, query: str) -> str:
        """Query Mistral via Mistral API (Le Chat)."""
        if not settings.MISTRAL_API_KEY:
            self.errors.append("mistral: MISTRAL_API_KEY manquante")
            return ""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "mistral-small-latest",
                        "max_tokens": 1000,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": query},
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            msg = f"mistral: HTTP {e.response.status_code}"
            try:
                body = e.response.json()
                msg += f" - {body.get('message', str(body))}"
            except Exception:
                pass
            logger.error(f"Mistral query error: {msg}")
            self.errors.append(msg)
            return ""
        except Exception as e:
            msg = f"mistral: {type(e).__name__}: {e}"
            logger.error(f"Mistral query error: {msg}")
            self.errors.append(msg)
            return ""

    async def _analyze_response(self, query: str, answer: str, brand_names: list[str]) -> dict | None:
        """Use Claude Haiku to extract structured brand mentions from a raw AI answer."""
        if not answer or not settings.ANTHROPIC_API_KEY:
            return None
        prompt = ANALYSIS_PROMPT.format(
            query=query,
            brand_names=", ".join(brand_names),
            answer=answer,
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 1000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                text = resp.json()["content"][0]["text"]
                # Strip possible markdown code fences
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text.rsplit("```", 1)[0]
                return json.loads(text.strip())
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return None

    async def _process_single_query(
        self, keyword: str, query: str, brand_names: list[str],
    ) -> list[dict[str, Any]]:
        """Process a single GEO query across all platforms in parallel."""
        results: list[dict[str, Any]] = []

        # Query all engines in parallel
        claude_task = asyncio.create_task(self._query_claude(query))
        gemini_task = asyncio.create_task(self._query_gemini(query))
        chatgpt_task = asyncio.create_task(self._query_chatgpt(query))
        mistral_task = asyncio.create_task(self._query_mistral(query))

        answers_raw = await asyncio.gather(mistral_task, claude_task, gemini_task, chatgpt_task)
        platform_names = ["mistral", "claude", "gemini", "chatgpt"]

        answers = {
            name: ans for name, ans in zip(platform_names, answers_raw) if ans
        }

        if not answers:
            return results

        # Analyse all responses in parallel
        analysis_tasks = {
            platform: asyncio.create_task(
                self._analyze_response(query, answer, brand_names)
            )
            for platform, answer in answers.items()
        }

        for platform, task in analysis_tasks.items():
            analysis = await task
            if not analysis:
                continue

            primary_rec = analysis.get("primary_recommendation", "")
            brands_mentioned = analysis.get("brands_mentioned", [])

            for mention in brands_mentioned:
                results.append({
                    "keyword": keyword,
                    "query": query,
                    "platform": platform,
                    "raw_answer": answers[platform],
                    "analysis": json.dumps(analysis, ensure_ascii=False),
                    "brand_name": mention.get("name", ""),
                    "position_in_answer": mention.get("position"),
                    "recommended": mention.get("recommended", False),
                    "sentiment": mention.get("sentiment", "neutre"),
                    "context_snippet": mention.get("context", ""),
                    "primary_recommendation": primary_rec,
                    "key_criteria": analysis.get("key_criteria", []),
                })

        return results

    async def run_full_analysis(
        self, brand_names: list[str], sector: str = "supermarche", sector_label: str = ""
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Run all GEO queries against Claude + Gemini + ChatGPT and return structured results.

        Queries are processed in batches of 3 with parallel platform calls for speed.
        Returns (results, errors) where results is a list of dicts and errors is a list of error messages.
        """
        self.errors = []  # Reset errors for this run
        queries = get_geo_queries(sector, sector_label or sector, brand_names)
        results: list[dict[str, Any]] = []

        # Log available platforms upfront
        platforms = self.get_available_platforms()
        logger.info(f"GEO starting: {len(queries)} queries, platforms: {platforms}")
        for name, available in platforms.items():
            if not available:
                logger.warning(f"GEO: {name} API key NOT configured — skipping")

        # Process queries in batches of 3 for speed (parallel within each batch)
        batch_size = 3
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i + batch_size]
            batch_tasks = [
                self._process_single_query(q["keyword"], q["query"], brand_names)
                for q in batch
            ]
            batch_results = await asyncio.gather(*batch_tasks)
            for batch_result in batch_results:
                results.extend(batch_result)

            done = min(i + batch_size, len(queries))
            logger.info(f"GEO [{done}/{len(queries)}] done, {len(results)} mentions so far")

            # Small delay between batches to avoid rate limits
            if done < len(queries):
                await asyncio.sleep(0.5)

        # Deduplicate errors (same missing key logged for each query)
        unique_errors = list(dict.fromkeys(self.errors))
        if not results:
            logger.warning(f"GEO finished with 0 results. Errors: {unique_errors}")

        return results, unique_errors


geo_analyzer = GeoAnalyzer()
