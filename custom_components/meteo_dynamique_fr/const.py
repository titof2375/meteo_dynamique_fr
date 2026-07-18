"""Constantes pour l'intégration Météo Dynamique (Météo-France)."""

from meteofrance_api.const import ALERT_COLOR_LIST_FR, ALERT_TYPE_DICTIONARY_FR

DOMAIN = "meteo_dynamique_fr"

CONF_TRACKER_ENTITY = "tracker_entity"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL_MINUTES = 15

# Clés utilisées pour stocker les 3 coordinators d'une même entrée dans hass.data.
DATA_WEATHER = "weather"
DATA_RAIN = "rain"
DATA_ALERT = "alert"

# La pluie à l'heure évolue vite : rafraîchissement bien plus fréquent que la
# météo générale (indépendant de CONF_SCAN_INTERVAL choisi par l'utilisateur).
SCAN_INTERVAL_RAIN_MINUTES = 5

# La vigilance météo change rarement en cours de journée, un intervalle
# intermédiaire suffit (entre la pluie et la météo générale).
SCAN_INTERVAL_ALERT_MINUTES = 20

# Attributs du capteur next_rain (prévision minute par minute des 60 prochaines
# minutes, cadrans de 5 en 5 minutes comme le renvoie l'API Météo-France).
ATTR_RAIN_FORECAST = "prevision_minute_par_minute"
ATTR_RAIN_REFERENCE_TIME = "heure_reference"
ATTR_RAIN_QUALITY = "qualite_prevision"

# Niveau de pluie renvoyé par l'API 'rain' : 1 = pas de pluie, 2 = pluie faible,
# 3 = pluie modérée, 4 = pluie forte. Reprise du comportement de
# Rain.next_rain_date_locale() dans meteofrance-api (rain > 1 = de la pluie).
RAIN_LEVEL_DESCRIPTIONS = {
    1: "Pas de pluie",
    2: "Pluie faible",
    3: "Pluie modérée",
    4: "Pluie forte",
}

# Couleurs de vigilance Météo-France, reprises telles quelles de la librairie
# (index = phenomenon_max_color_id renvoyé par l'API v3/warning/currentphenomenons).
WEATHER_ALERT_LEVELS = ALERT_COLOR_LIST_FR  # [None, "Vert", "Jaune", "Orange", "Rouge"]

# Libellés des 9 phénomènes de vigilance, repris tels quels de la librairie.
WEATHER_ALERT_PHENOMENONS = ALERT_TYPE_DICTIONARY_FR

WEATHER_ALERT_ICONS = {
    None: "mdi:help-circle-outline",
    "Vert": "mdi:check-circle-outline",
    "Jaune": "mdi:alert-outline",
    "Orange": "mdi:alert",
    "Rouge": "mdi:alert-octagon",
}

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
