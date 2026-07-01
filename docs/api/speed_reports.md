# API — App `speed_reports`

Préfixe global : `/api/v1/`. Authentification via JWT (`Authorization: Bearer <access>`).

Signalements d'excès de vitesse déposés par un voyageur.

- `reported_at` : horodaté automatiquement à la création si absent.
- Position GPS facultative (`latitude`, `longitude`) — l'agent/voyageur peut être hors couverture.
- `status` : `pending → reviewed → closed` (modifiable par le super admin).
- Isolation multi-tenant : un admin ne voit que les signalements de sa compagnie.

---

## Voyageur — `IsVoyageur`

### POST `/api/v1/speed-reports/`

Dépose un signalement. La compagnie est fournie directement ou déduite du voyage référencé.

| Champ             | Type    | Obligatoire | Description                             |
|-------------------|---------|-------------|-----------------------------------------|
| `company`         | int     | Cond.       | Obligatoire si `trip` absent            |
| `trip`            | int     | Non         | Voyage concerné (déduit la compagnie)   |
| `estimated_speed` | int     | Non         | Vitesse estimée en km/h                 |
| `description`     | str     | Non         | Détail                                  |
| `latitude`        | decimal | Non         | Position GPS                            |
| `longitude`       | decimal | Non         | Position GPS                            |
| `reported_at`     | datetime| Non         | Défaut : maintenant                     |

```bash
curl -X POST https://api.transbooking.bf/api/v1/speed-reports/ \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"trip": 42, "estimated_speed": 130, "description": "Largement au-dessus de la limite."}'
```

Réponse `201` :

```json
{
  "id": 5, "company": 1, "company_name": "STAF", "trip": 42, "estimated_speed": 130,
  "description": "Largement au-dessus de la limite.", "latitude": null, "longitude": null,
  "reported_at": "2026-06-30T08:00:00Z", "status": "pending", "status_display": "En attente",
  "created_at": "2026-06-30T08:00:00Z"
}
```

Erreurs : `400` (ni compagnie ni voyage), `401`, `403`.

---

## Admin compagnie — `IsCompanyAdmin`

### GET `/api/v1/company/speed-reports/`

Signalements reçus par la compagnie de l'admin courant (paginé).

---

## Super admin — `IsSuperAdmin`

### GET `/api/v1/super/speed-reports/`

Tous les signalements de la plateforme.

### PATCH `/api/v1/super/speed-reports/{id}/`

Change le statut.

| Champ    | Type | Obligatoire | Description                     |
|----------|------|-------------|---------------------------------|
| `status` | str  | Oui         | `pending · reviewed · closed`   |

Réponse `200` : le signalement mis à jour. Erreurs : `400` (statut invalide), `401`, `403`, `404`.
