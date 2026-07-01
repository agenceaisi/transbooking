# API — App `trips`

Préfixe global : `/api/v1/`. Authentification via JWT (`Authorization: Bearer <access>`)
sauf endpoints publics.

Isolation multi-tenant stricte : un `company_admin` ne gère que les voyages de **sa propre**
compagnie (filtre `route__company`). Sans compagnie associée → `404`.

> `available_seats` est initialisé depuis `vehicle.total_seats` à la création et n'est
> jamais fixé manuellement. Sa décrémentation se fait **uniquement** via `select_for_update()`
> (réservations — voir app `bookings`, PROMPT 05).

---

## Voyages — `IsCompanyAdmin`

CRUD filtré par la compagnie de l'utilisateur courant. Filtres : `?route=`, `?status=`,
`?date=YYYY-MM-DD` (sur la date de départ).

### GET `/api/v1/company/trips/`

Liste paginée des voyages (`TripReadSerializer`).

### POST `/api/v1/company/trips/`

| Champ            | Type     | Obligatoire | Notes                                          |
|------------------|----------|-------------|------------------------------------------------|
| `route`          | int      | oui         | FK `routes.Route` (même compagnie)             |
| `vehicle`        | int      | oui         | FK `vehicles.Vehicle` (même compagnie)         |
| `departure_time` | datetime | oui         | ISO 8601                                       |
| `arrival_time`   | datetime | non         | estimée                                        |
| `price`          | decimal  | non         | défaut = `route.base_price`                    |
| `status`         | string   | non         | `scheduled` (défaut)/`in_progress`/`delayed`…  |

```bash
curl -X POST "https://api.transbooking.bf/api/v1/company/trips/" \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"route": 1, "vehicle": 3, "departure_time": "2026-07-01T06:00:00Z"}'
```

**201 Created** — voyage sérialisé. `available_seats` = `vehicle.total_seats`.
Erreurs : `400` (véhicule et trajet de compagnies différentes), `401`, `403`.

### GET/PATCH `/api/v1/company/trips/{id}/`

Détail / modification (véhicule, heure, prix). `404` si autre compagnie.

### DELETE `/api/v1/company/trips/{id}/`

**Annule** le voyage (status → `cancelled`) et notifie tous les passagers réservés par SMS.

| Champ    | Type   | Obligatoire | Notes                       |
|----------|--------|-------------|-----------------------------|
| `reason` | string | non         | motif d'annulation (SMS)    |

**200 OK** — voyage sérialisé (`status=cancelled`).
Erreurs : `400` (déjà annulé/terminé), `401`, `403`, `404`.

### POST `/api/v1/company/trips/generate/`

Génère des voyages à partir d'horaires types sur une fenêtre glissante de jours.

| Champ             | Type | Obligatoire | Notes                                                         |
|-------------------|------|-------------|---------------------------------------------------------------|
| `route_id`        | int  | oui         | trajet de la compagnie                                        |
| `schedule_config` | list | oui         | slots `{"time": "06:00", "days": [0..6], "vehicle_id": 3}`    |
| `days`            | int  | oui         | nombre de jours à générer (ex: 7, 15, 30, 90)                 |

`days` dans `schedule_config` = indices de jour de semaine (lundi = 0).

```bash
curl -X POST "https://api.transbooking.bf/api/v1/company/trips/generate/" \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"route_id": 1, "days": 7,
       "schedule_config": [{"time": "06:00", "days": [0,1,2,3,4,5,6], "vehicle_id": 3}]}'
```

**201 Created**
```json
{"created": 7, "trips": [ ... ]}
```
Erreurs : `400` (config invalide, véhicule en maintenance), `401`, `403`, `404` (trajet).

---

## Recherche publique — `AllowAny`

### GET `/api/v1/trips/search/`

Recherche de voyages programmés et à venir avec assez de places, triés par heure de départ.

| Query param   | Type | Notes                                            |
|---------------|------|--------------------------------------------------|
| `origin_city` | int  | id ville de départ                               |
| `dest_city`   | int  | id ville d'arrivée                               |
| `date`        | date | `YYYY-MM-DD` (date de départ)                    |
| `passengers`  | int  | `available_seats >= passengers`                  |
| `max_price`   | num  | prix maximum                                     |
| `direct`      | bool | `true`/`1` → trajets sans escale uniquement      |

**200 OK** — liste paginée (`TripReadSerializer`).

### GET `/api/v1/trips/{id}/`

Détail public d'un voyage + `available_seat_numbers` (liste des sièges libres).

**200 OK** — `TripDetailSerializer`. Erreurs : `404`.

---

## Agent — programme du jour — `IsAgent`

### GET `/api/v1/agent/trips/today/`

Voyages du jour rattachés à la gare et/ou au véhicule de l'agent connecté
(résolus via `request.user.agent_profile`). Non paginé.

**200 OK** — liste de voyages (`TripReadSerializer`).
Erreurs : `401`, `403`, `404` (aucun profil agent).

---

## Services (`trips/services.py`)

- `generate_trips(route_id, schedule_config, days) -> list[Trip]` — génère les voyages
  (transaction atomique). Vérifie que chaque véhicule est assignable (`active`).
- `cancel_trip(trip, reason) -> Trip` — passe le voyage en `cancelled`, enregistre le motif
  et envoie un SMS à chaque passager réservé. Lève `ValidationError` si déjà annulé/terminé.
