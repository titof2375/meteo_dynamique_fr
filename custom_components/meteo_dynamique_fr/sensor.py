"""Capteurs sensor.* pour Météo Dynamique (Météo-France).

Complète weather.py avec les capteurs absents de l'entité weather (mais présents
dans l'intégration officielle homeassistant/components/meteo_france) :

- next_rain     : pluie dans l'heure (client.get_rain), rafraîchie toutes les
                  SCAN_INTERVAL_RAIN_MINUTES minutes via MeteoDynamiqueRainCoordinator.
- weather_alert : vigilance météo (client.get_warning_current_phenomenons), pour le
                  département déduit de la position GPS courante, via
                  MeteoDynamiqueAlertCoordinator.
- uv, cloud_cover, rain_probability, snow_probability, freeze_probability :
  capteurs bonus, réutilisant les données déjà récupérées par
  MeteoDynamiqueCoordinator (aucun appel API supplémentaire).

Tous les capteurs suivent automatiquement la même position GPS que weather.*,
puisqu'ils partagent le même tracker_entity et les mêmes coordinators.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_RAIN_FORECAST,
    ATTR_RAIN_QUALITY,
    ATTR_RAIN_REFERENCE_TIME,
    CONF_NAME,
    CONF_TRACKER_ENTITY,
    DATA_ALERT,
    DATA_RAIN,
    DATA_WEATHER,
    DOMAIN,
    RAIN_LEVEL_DESCRIPTIONS,
    WEATHER_ALERT_ICONS,
    WEATHER_ALERT_LEVELS,
    WEATHER_ALERT_PHENOMENONS,
)
from .coordinator import (
    MeteoDynamiqueAlertCoordinator,
    MeteoDynamiqueCoordinator,
    MeteoDynamiqueRainCoordinator,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    weather_coordinator: MeteoDynamiqueCoordinator = data[DATA_WEATHER]
    rain_coordinator: MeteoDynamiqueRainCoordinator = data[DATA_RAIN]
    alert_coordinator: MeteoDynamiqueAlertCoordinator = data[DATA_ALERT]

    async_add_entities(
        [
            MeteoDynamiqueNextRainSensor(rain_coordinator, entry),
            MeteoDynamiqueWeatherAlertSensor(alert_coordinator, entry),
            MeteoDynamiqueUvSensor(weather_coordinator, entry),
            MeteoDynamiqueCloudCoverSensor(weather_coordinator, entry),
            MeteoDynamiqueProbabilitySensor(
                weather_coordinator, entry, kind="rain", name="Probabilité de pluie"
            ),
            MeteoDynamiqueProbabilitySensor(
                weather_coordinator, entry, kind="snow", name="Probabilité de neige"
            ),
            MeteoDynamiqueProbabilitySensor(
                weather_coordinator, entry, kind="freezing", name="Probabilité de gel"
            ),
        ]
    )


def _device_info(entry: ConfigEntry) -> dict[str, Any]:
    """Même device que weather.py : regroupe tous les capteurs sous la même entité suivie."""
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": entry.data[CONF_NAME],
        "manufacturer": "Météo-France",
        "model": "Météo suivant la position GPS (API mobile Météo-France)",
        "entry_type": "service",
    }


def _ts_to_utc(ts: int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


class MeteoDynamiqueSensorBase(CoordinatorEntity, SensorEntity):
    """Base commune : has_entity_name + device_info alignés sur weather.py."""

    _attr_has_entity_name = True
    _attr_attribution = "Données fournies par Météo-France"

    def __init__(self, coordinator, entry: ConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.data[CONF_TRACKER_ENTITY]}_{key}"
        self._attr_device_info = _device_info(entry)


class MeteoDynamiqueNextRainSensor(MeteoDynamiqueSensorBase):
    """Prochaine pluie dans l'heure : état = timestamp, attributs = détail minute par minute."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:weather-pouring"

    def __init__(self, coordinator: MeteoDynamiqueRainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, key="next_rain", name="Pluie dans l'heure")

    @property
    def native_value(self) -> datetime | None:
        rain = self.coordinator.data
        if rain is None:
            return None
        # next_rain_date_locale() renvoie un datetime tz-aware (fuseau du lieu),
        # ou None si aucune pluie n'est prévue dans l'heure : HA gère les deux.
        return rain.next_rain_date_locale()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rain = self.coordinator.data
        if rain is None:
            return {}

        # Prévision minute par minute (cadrans ~5 minutes renvoyés par l'API) des
        # 60 prochaines minutes : {"HH:MM:SS+TZ": "Pluie faible", ...}.
        forecast_detail: dict[str, str] = {}
        for cadran in rain.forecast:
            dt_cadran = rain.timestamp_to_locale_time(cadran["dt"])
            level = cadran.get("rain")
            forecast_detail[dt_cadran.isoformat()] = RAIN_LEVEL_DESCRIPTIONS.get(
                level, f"Niveau {level}"
            )

        return {
            ATTR_RAIN_FORECAST: forecast_detail,
            ATTR_RAIN_REFERENCE_TIME: _ts_to_utc(rain.updated_on),
            ATTR_RAIN_QUALITY: rain.quality,
        }


class MeteoDynamiqueWeatherAlertSensor(MeteoDynamiqueSensorBase):
    """Vigilance météo du département courant : état = niveau max (Vert/Jaune/Orange/Rouge)."""

    _attr_icon = "mdi:alert-decagram-outline"

    def __init__(self, coordinator: MeteoDynamiqueAlertCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, key="weather_alert", name="Vigilance météo")

    @property
    def _phenomenons(self):
        data = self.coordinator.data or {}
        return data.get("phenomenons")

    @property
    def native_value(self) -> str | None:
        phenomenons = self._phenomenons
        if phenomenons is None:
            return None
        return WEATHER_ALERT_LEVELS[phenomenons.get_domain_max_color()]

    @property
    def icon(self) -> str:
        return WEATHER_ALERT_ICONS.get(self.native_value, "mdi:help-circle-outline")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        phenomenons = data.get("phenomenons")
        if phenomenons is None:
            return {"departement": data.get("department")}

        # Détail par phénomène (orages, inondation, etc.), libellé français officiel.
        detail = {
            WEATHER_ALERT_PHENOMENONS.get(str(item["phenomenon_id"]), f"Phénomène {item['phenomenon_id']}"):
                WEATHER_ALERT_LEVELS[item["phenomenon_max_color_id"]]
            for item in phenomenons.phenomenons_max_colors
        }
        return {
            "departement": data.get("department"),
            "phenomenes": detail,
            "heure_maj": _ts_to_utc(phenomenons.update_time),
            "fin_validite": _ts_to_utc(phenomenons.end_validity_time),
        }


class MeteoDynamiqueUvSensor(MeteoDynamiqueSensorBase):
    """Indice UV max du jour (bonus), tiré de la prévision quotidienne déjà chargée."""

    _attr_icon = "mdi:sun-wireless-outline"
    _attr_state_class = "measurement"

    def __init__(self, coordinator: MeteoDynamiqueCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, key="uv", name="Indice UV")

    @property
    def native_value(self) -> float | None:
        daily = (self.coordinator.data or {}).get("daily") or []
        if not daily:
            return None
        # daily[0] = aujourd'hui, "uv" est l'indice UV max de la journée.
        return daily[0].get("uv")


class MeteoDynamiqueCloudCoverSensor(MeteoDynamiqueSensorBase):
    """Couverture nuageuse actuelle en % (bonus), tirée de la prévision horaire courante."""

    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:cloud-percent-outline"
    _attr_state_class = "measurement"

    def __init__(self, coordinator: MeteoDynamiqueCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, key="cloud_cover", name="Couverture nuageuse")

    @property
    def native_value(self) -> float | None:
        current = (self.coordinator.data or {}).get("current") or {}
        return current.get("clouds")


# Clés candidates dans probability_forecast pour chaque type d'événement : selon
# l'horizon de la prévision, Météo-France renvoie soit une clé "à 3h"/"à 6h" (jours
# proches), soit une clé simple (jours lointains). On prend la première présente.
# ATTENTION : ces sous-clés n'ont pas pu être vérifiées de façon certaine (le format
# exact varie selon les versions de l'API) ; vérifiez avec Outils de développement >
# Modèles sur `probability_forecast[0]` de votre position et ajustez si besoin.
_PROBABILITY_CANDIDATE_KEYS: dict[str, tuple[str, ...]] = {
    "rain": ("rain 3h", "rain 6h", "rain"),
    "snow": ("snow 3h", "snow 6h", "snow"),
    "freezing": ("freezing",),
}
_PROBABILITY_ICONS = {
    "rain": "mdi:weather-rainy",
    "snow": "mdi:weather-snowy",
    "freezing": "mdi:snowflake-alert",
}


class MeteoDynamiqueProbabilitySensor(MeteoDynamiqueSensorBase):
    """Probabilité de pluie / neige / gel (bonus), depuis Forecast.probability_forecast."""

    _attr_native_unit_of_measurement = "%"
    _attr_state_class = "measurement"

    def __init__(
        self, coordinator: MeteoDynamiqueCoordinator, entry: ConfigEntry, kind: str, name: str
    ) -> None:
        super().__init__(coordinator, entry, key=f"{kind}_probability", name=name)
        self._kind = kind
        self._attr_icon = _PROBABILITY_ICONS[kind]

    @property
    def native_value(self) -> float | None:
        probability = (self.coordinator.data or {}).get("probability") or []
        if not probability:
            return None
        nearest = probability[0]
        for candidate_key in _PROBABILITY_CANDIDATE_KEYS[self._kind]:
            if candidate_key in nearest and nearest[candidate_key] is not None:
                return nearest[candidate_key]
        return None
