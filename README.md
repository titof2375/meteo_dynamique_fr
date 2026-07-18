# Météo Dynamique (Météo-France) pour Home Assistant

Intégration personnalisée qui crée une entité `weather.*` dont la météo (actuelle + prévisions 15 jours + prévisions horaires) est recalculée automatiquement selon la position GPS **courante** d'une personne ou d'un `device_tracker` — en utilisant la même API mobile Météo-France que l'intégration officielle `meteo_france` de Home Assistant (via le package Python `meteofrance-api`).

## Pourquoi Météo-France et pas une autre source

- Même source de données que ton `weather.saint_fiel` existant (cohérence)
- Gratuite, sans clé API (API mobile publique utilisée par l'appli officielle)
- Résolution fine sur la France (modèle AROME)
- Mapping des conditions météo identique à celui de l'intégration officielle HA (même table `CONDITION_CLASSES`), donc un comportement familier

## Fonctionnalités

- ✅ Suivi GPS dynamique via n'importe quelle entité `person.xxx` ou `device_tracker.xxx`
- ✅ Une entité `weather.*` complète : condition, température, humidité, pression, vent (vitesse, rafales, direction)
- ✅ Prévisions journalières et horaires, compatibles avec les cartes météo standards de HA
- ✅ Plusieurs instances possibles : une par personne à suivre
- ✅ Intervalle de rafraîchissement configurable (5 à 120 min, 15 min par défaut)

## Installation

1. **Copiez le dossier** `meteo_dynamique_fr` dans votre dossier Home Assistant :

   ```
   homeassistant/custom_components/meteo_dynamique_fr/
   ```

2. **Redémarrez Home Assistant** (le package Python `meteofrance-api` sera installé automatiquement au démarrage grâce au `manifest.json`)

3. **Allez dans** Paramètres → Appareils et services → Ajouter une intégration

4. **Recherchez** "Météo Dynamique" et suivez le formulaire de configuration

## Configuration

Chaque instance suit **une seule** position (une personne ou un tracker). Pour suivre plusieurs personnes, ajoutez l'intégration plusieurs fois, une fois par personne.

### Champs du formulaire

| Champ            | Exemple                          | Description                                                     |
| ----------------- | --------------------------------- | ----------------------------------------------------------------- |
| `name`            | `Météo Christophe`                | Nom donné à cette instance (et à l'entité créée)                 |
| `tracker_entity`  | `person.christophe`               | Entité GPS à suivre — une personne ou un device_tracker           |
| `scan_interval`   | `15`                              | Fréquence de rafraîchissement en minutes                          |

## Utilisation

### Entité créée

Une entité `weather.<nom>` est créée par instance, exposant :

- `condition` : ensoleillé, nuageux, pluvieux, etc. (mapping identique à `weather.saint_fiel`)
- `native_temperature`, `humidity`, `native_pressure`
- `native_wind_speed`, `native_wind_gust_speed`, `wind_bearing` (vitesse du vent en m/s, comme l'intégration officielle)
- Attributs : `tracker_entity`, `latitude_suivie`, `longitude_suivie`, `nom_lieu_meteo_france`
- Prévisions journalières et horaires via les services standards `weather.get_forecasts`

### Exemple de template

```jinja2
{{ state_attr('weather.meteo_christophe', 'temperature') }}°C, {{ states('weather.meteo_christophe') }}
```

## Notes

- Repose sur l'API mobile publique de Météo-France via le package `meteofrance-api` (utilisé aussi par l'intégration officielle HA) — non documentée officiellement par Météo-France, mais stable et largement utilisée par la communauté HA.
- Si l'entité suivie (`person.xxx`) n'a pas encore de position GPS connue (ex: au premier démarrage), l'entité météo passe en `unavailable` jusqu'à la prochaine position valide.
- Le mapping condition → icône reprend exactement la table `CONDITION_CLASSES` de l'intégration officielle `meteo_france`, donc le comportement visuel (icônes, cartes météo) sera cohérent avec `weather.saint_fiel`.
