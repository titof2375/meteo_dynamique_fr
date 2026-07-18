"""Entité weather.* pour Météo Dynamique (Météo-France).

Le parsing des champs (T, weather/weather12H, humidity, wind, rain,
precipitation) reproduit fidèlement celui de l'intégration officielle
homeassistant/components/meteo_france/weather.py, adapté pour une
position GPS dynamique (device_tracker/person) au lieu d'une position fixe.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, CONF_TRACKER_ENTITY, DATA_WEATHER, DOMAIN, format_condition
from .coordinator import MeteoDynamiqueCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MeteoDynamiqueCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_WEATHER]
    async_add_entities([MeteoDynamiqueWeather(coordinator, entry)])


def _ts_to_iso(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class MeteoDynamiqueWeather(CoordinatorEntity[MeteoDynamiqueCoordinator], WeatherEntity):
    """Météo Météo-France actuelle + prévisions pour la position GPS courante de tracker_entity."""

    _attr_has_entity_name = True
    _attr_attribution = "Données fournies par Météo-France"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    # Unité native = m/s, comme l'intégration officielle Météo-France (pas de conversion).
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY

    def __init__(self, coordinator: MeteoDynamiqueCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.data[CONF_TRACKER_ENTITY]}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data[CONF_NAME],
            "manufacturer": "Météo-France",
            "model": "Météo suivant la position GPS (API mobile Météo-France)",
            "entry_type": "service",
        }

    @property
    def name(self) -> str:
        return self._entry.data[CONF_NAME]

    @property
    def _current(self) -> dict:
        return (self.coordinator.data or {}).get("current") or {}

    @property
    def condition(self) -> str | None:
        weather = self._current.get("weather") or {}
        return format_condition(weather.get("desc"))

    @property
    def native_temperature(self) -> float | None:
        temp = self._current.get("T") or {}
        return temp.get("value")

    @property
    def humidity(self) -> float | None:
        return self._current.get("humidity")

    @property
    def native_pressure(self) -> float | None:
        return self._current.get("sea_level")

    @property
    def native_wind_speed(self) -> float | None:
        wind = self._current.get("wind") or {}
        return wind.get("speed")

    @property
    def native_wind_gust_speed(self) -> float | None:
        wind = self._current.get("wind") or {}
        return wind.get("gust")

    @property
    def wind_bearing(self) -> float | None:
        wind = self._current.get("wind") or {}
        bearing = wind.get("direction")
        # Météo-France renvoie -1 quand la direction n'est pas disponible.
        return bearing if bearing not in (None, -1) else None

    @property
    def extra_state_attributes(self) -> dict:
        position = (self.coordinator.data or {}).get("position") or {}
        return {
            "tracker_entity": self._entry.data[CONF_TRACKER_ENTITY],
            "latitude_suivie": position.get("lat"),
            "longitude_suivie": position.get("lon"),
            "nom_lieu_meteo_france": position.get("name"),
            # Département déduit par Météo-France pour cette position : c'est celui
            # utilisé automatiquement par le capteur sensor.*_weather_alert.
            "departement": position.get("dept"),
        }

    async def async_forecast_daily(self) -> list[Forecast] | None:
        daily = (self.coordinator.data or {}).get("daily")
        if not daily:
            return None

        forecasts: list[Forecast] = []
        for day in daily:
            # Comme l'intégration officielle : on s'arrête si "weather12H" est absent
            # (peut arriver en fin de fenêtre de prévision, jusqu'à 14 jours).
            weather12h = day.get("weather12H")
            if not weather12h:
                break

            temp = day.get("T") or {}
            humidity = day.get("humidity") or {}
            precipitation = day.get("precipitation") or {}

            forecasts.append(
                Forecast(
                    datetime=_ts_to_iso(day.get("dt")),
                    condition=format_condition(weather12h.get("desc"), force_day=True),
                    native_temperature=temp.get("max"),
                    native_templow=temp.get("min"),
                    humidity=humidity.get("max"),
                    precipitation=precipitation.get("24h"),
                )
            )
        return forecasts

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        hourly = (self.coordinator.data or {}).get("hourly")
        if not hourly:
            return None

        now_ts = time.time()
        forecasts: list[Forecast] = []
        for hour in hourly:
            # Comme l'intégration officielle : on ignore les entrées déjà passées.
            if hour.get("dt", 0) < now_ts:
                continue

            temp = hour.get("T") or {}
            weather = hour.get("weather") or {}
            rain = hour.get("rain") or {}
            wind = hour.get("wind") or {}
            bearing = wind.get("direction")

            forecasts.append(
                Forecast(
                    datetime=_ts_to_iso(hour.get("dt")),
                    condition=format_condition(weather.get("desc")),
                    native_temperature=temp.get("value"),
                    humidity=hour.get("humidity"),
                    native_precipitation=rain.get("1h"),
                    native_wind_speed=wind.get("speed"),
                    native_wind_gust_speed=wind.get("gust"),
                    wind_bearing=bearing if bearing not in (None, -1) else None,
                )
            )
            if len(forecasts) >= 48:
                break
        return forecasts
