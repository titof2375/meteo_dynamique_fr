"""Constantes pour l'intégration Météo Dynamique (Météo-France)."""

DOMAIN = "meteo_dynamique_fr"

CONF_TRACKER_ENTITY = "tracker_entity"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL_MINUTES = 15

# Table de correspondance EXACTE reprise de l'intégration officielle
# homeassistant/components/meteo_france/const.py (CONDITION_CLASSES),
# pour garantir le même comportement que weather.saint_fiel.
CONDITION_CLASSES: dict[str, list[str]] = {
    "clear-night": ["Nuit Claire", "Nuit claire", "Ciel clair"],
    "cloudy": ["Très nuageux", "Couvert"],
    "fog": [
        "Brume ou bancs de brouillard",
        "Brume",
        "Brouillard",
        "Brouillard givrant",
        "Bancs de Brouillard",
        "Brouillard dense",
        "Brouillard dense givrant",
    ],
    "hail": ["Risque de grêle", "Averses de grêle"],
    "lightning": ["Risque d'orages", "Orages", "Orage avec grêle"],
    "lightning-rainy": [
        "Pluie orageuses",
        "Pluies orageuses",
        "Averses orageuses",
    ],
    "partlycloudy": [
        "Ciel voilé",
        "Ciel voilé nuit",
        "Éclaircies",
        "Eclaircies",
        "Peu nuageux",
        "Variable",
    ],
    "pouring": ["Pluie forte"],
    "rainy": [
        "Bruine / Pluie faible",
        "Bruine",
        "Pluie faible",
        "Pluies éparses / Rares averses",
        "Pluies éparses",
        "Rares averses",
        "Pluie modérée",
        "Pluie / Averses",
        "Averses",
        "Averses faibles",
        "Pluie",
    ],
    "snowy": [
        "Neige / Averses de neige",
        "Neige",
        "Averses de neige",
        "Neige forte",
        "Neige faible",
        "Averses de neige faible",
        "Quelques flocons",
    ],
    "snowy-rainy": [
        "Pluie et neige",
        "Pluie verglaçante",
        "Averses de pluie et neige",
    ],
    "sunny": ["Ensoleillé"],
    "windy": [],
    "windy-variant": [],
    "exceptional": [],
}

CONDITION_MAP = {
    desc: condition for condition, descs in CONDITION_CLASSES.items() for desc in descs
}


def format_condition(desc: str | None, force_day: bool = False) -> str | None:
    """Convertit une description texte Météo-France en condition HA (mapping officiel)."""
    if not desc:
        return None
    mapped = CONDITION_MAP.get(desc, desc)
    if force_day and mapped == "clear-night":
        # Météo-France peut renvoyer "nuit claire" pour une prévision journalière ;
        # dans ce cas on le convertit en "sunny" (même logique que l'intégration officielle).
        return "sunny"
    return mapped
