"""Coordinator : interroge l'API Météo-France avec la position GPS courante de l'entité suivie."""
from __future__ import annotations

import logging
from datetime import timedelta

from meteofrance_api import MeteoFranceClient
from meteofrance_api.model import Forecast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class MeteoDynamiqueCoordinator(DataUpdateCoordinator):
    """Récupère la météo Météo-France courante + prévisions pour la position actuelle de tracker_entity."""

    def __init__(self, hass: HomeAssistant, tracker_entity: str, name: str, scan_interval_minutes: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"meteo_dynamique_fr_{name}",
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self.tracker_entity = tracker_entity
        self.hass = hass
        self._client = MeteoFranceClient()

    def _get_position(self) -> tuple[float, float] | None:
        state = self.hass.states.get(self.tracker_entity)
        if state is None:
            return None
        lat = state.attributes.get("latitude")
        lon = state.attributes.get("longitude")
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)

    def _fetch_sync(self, lat: float, lon: float) -> Forecast:
        """Appel bloquant à la lib meteofrance-api (exécuté dans l'executor)."""
        return self._client.get_forecast(latitude=lat, longitude=lon)

    async def _async_update_data(self):
        position = self._get_position()
        if position is None:
            raise UpdateFailed(
                f"Impossible de récupérer la position GPS de {self.tracker_entity} "
                "(entité absente ou sans attributs latitude/longitude)."
            )
        lat, lon = position

        try:
            forecast: Forecast = await self.hass.async_add_executor_job(self._fetch_sync, lat, lon)
        except Exception as err:  # noqa: BLE001 - la lib peut lever plusieurs types d'erreurs réseau/API
            raise UpdateFailed(f"Erreur lors de l'appel à l'API Météo-France : {err}") from err

        return {
            "current": forecast.current_forecast,
            "daily": forecast.daily_forecast,
            "hourly": forecast.forecast,
            "position": forecast.position,
            "updated_on": forecast.updated_on,
        }
