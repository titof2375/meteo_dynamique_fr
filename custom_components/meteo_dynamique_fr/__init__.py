"""Intégration Météo Dynamique (Open-Meteo) - suit la position GPS d'un tracker/personne."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TRACKER_ENTITY,
    DATA_ALERT,
    DATA_RAIN,
    DATA_WEATHER,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)
from .coordinator import (
    MeteoDynamiqueAlertCoordinator,
    MeteoDynamiqueCoordinator,
    MeteoDynamiqueRainCoordinator,
)

PLATFORMS = ["weather", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
    )
    tracker_entity = entry.data[CONF_TRACKER_ENTITY]
    name = entry.data[CONF_NAME]

    # 1) Météo générale (weather.*) : chargée en premier, car le département de la
    #    vigilance est déduit de sa donnée "position.dept".
    weather_coordinator = MeteoDynamiqueCoordinator(
        hass,
        tracker_entity=tracker_entity,
        name=name,
        scan_interval_minutes=scan_interval,
    )
    await weather_coordinator.async_config_entry_first_refresh()

    # 2) Pluie dans l'heure : même position GPS, rafraîchissement plus fréquent.
    rain_coordinator = MeteoDynamiqueRainCoordinator(
        hass,
        tracker_entity=tracker_entity,
        name=name,
    )
    await rain_coordinator.async_config_entry_first_refresh()

    # 3) Vigilance météo : département recalculé à chaque update à partir de la
    #    dernière position connue du coordinator météo (donc suit la même personne).
    def _get_department() -> str | None:
        position = (weather_coordinator.data or {}).get("position") or {}
        return position.get("dept")

    alert_coordinator = MeteoDynamiqueAlertCoordinator(
        hass,
        name=name,
        get_department=_get_department,
    )
    await alert_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_WEATHER: weather_coordinator,
        DATA_RAIN: rain_coordinator,
        DATA_ALERT: alert_coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'entrée si les options (intervalle) changent."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
