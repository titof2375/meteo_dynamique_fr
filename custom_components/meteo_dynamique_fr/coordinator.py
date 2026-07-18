"""Coordinators : interrogent l'API Météo-France avec la position GPS courante de l'entité suivie.

Trois coordinators partagent la MEME position GPS (celle de tracker_entity) :
- MeteoDynamiqueCoordinator      : météo courante + prévisions (weather.*)
- MeteoDynamiqueRainCoordinator  : pluie dans l'heure (rafraîchissement rapide)
- MeteoDynamiqueAlertCoordinator : vigilance météo, département déduit automatiquement
  du champ "dept" renvoyé par l'API forecast pour la position courante (donc recalculé
  à chaque déplacement de la personne/tracker suivie, sans appel API supplémentaire).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Callable

from meteofrance_api import MeteoFranceClient
from meteofrance_api.model import CurrentPhenomenons, Forecast, Rain

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL_ALERT_MINUTES, SCAN_INTERVAL_RAIN_MINUTES

_LOGGER = logging.getLogger(__name__)


def _get_tracked_position(hass: HomeAssistant, tracker_entity: str) -> tuple[float, float] | None:
    """Lit les attributs latitude/longitude de l'entité suivie (person/device_tracker/zone).

    Fonction commune aux 3 coordinators : garantit qu'ils suivent tous EXACTEMENT
    la même position GPS, au même instant de calcul.
    """
    state = hass.states.get(tracker_entity)
    if state is None:
        return None
    lat = state.attributes.get("latitude")
    lon = state.attributes.get("longitude")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


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
        return _get_tracked_position(self.hass, self.tracker_entity)

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
            # Prévisions de probabilités (pluie/neige/gel) pour les capteurs bonus.
            "probability": forecast.probability_forecast,
            "position": forecast.position,
            "updated_on": forecast.updated_on,
        }


class MeteoDynamiqueRainCoordinator(DataUpdateCoordinator):
    """Pluie dans l'heure (client.get_rain) : rafraîchissement plus fréquent que la météo générale."""

    def __init__(self, hass: HomeAssistant, tracker_entity: str, name: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"meteo_dynamique_fr_{name}_rain",
            update_interval=timedelta(minutes=SCAN_INTERVAL_RAIN_MINUTES),
        )
        self.tracker_entity = tracker_entity
        self.hass = hass
        self._client = MeteoFranceClient()

    def _get_position(self) -> tuple[float, float] | None:
        return _get_tracked_position(self.hass, self.tracker_entity)

    def _fetch_sync(self, lat: float, lon: float) -> Rain:
        return self._client.get_rain(latitude=lat, longitude=lon)

    async def _async_update_data(self) -> Rain:
        position = self._get_position()
        if position is None:
            raise UpdateFailed(
                f"Impossible de récupérer la position GPS de {self.tracker_entity} "
                "(entité absente ou sans attributs latitude/longitude)."
            )
        lat, lon = position

        try:
            return await self.hass.async_add_executor_job(self._fetch_sync, lat, lon)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Erreur lors de la récupération de la pluie à l'heure : {err}") from err


class MeteoDynamiqueAlertCoordinator(DataUpdateCoordinator):
    """Vigilance météo (client.get_warning_current_phenomenons) pour le département courant.

    Le département n'est PAS résolu via client.search_places (qui nécessite une
    requête texte, pas seulement des coordonnées GPS) : il est lu directement dans
    le champ "dept" de la position renvoyée par l'API forecast pour la position
    courante (déjà récupéré par MeteoDynamiqueCoordinator, donc aucun appel API
    supplémentaire). `get_department` est un callable qui renvoie ce code (ex: "76"),
    ou None si la position est hors de France métropolitaine/Andorre.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        get_department: Callable[[], str | None],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"meteo_dynamique_fr_{name}_alert",
            update_interval=timedelta(minutes=SCAN_INTERVAL_ALERT_MINUTES),
        )
        self.hass = hass
        self._get_department = get_department
        self._client = MeteoFranceClient()

    def _fetch_sync(self, department: str) -> CurrentPhenomenons:
        return self._client.get_warning_current_phenomenons(domain=department)

    async def _async_update_data(self) -> dict[str, Any]:
        department = self._get_department()
        if not department:
            raise UpdateFailed(
                "Département introuvable pour la position courante : la météo "
                "générale n'est pas encore chargée, ou la position suivie est hors "
                "de France métropolitaine/Andorre (vigilance non disponible)."
            )

        try:
            phenomenons = await self.hass.async_add_executor_job(self._fetch_sync, department)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(
                f"Erreur lors de la récupération de la vigilance météo (département {department}) : {err}"
            ) from err

        return {"department": department, "phenomenons": phenomenons}
