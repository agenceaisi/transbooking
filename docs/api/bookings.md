# API — App `bookings`

Préfixe global : `/api/v1/`. Authentification via JWT (`Authorization: Bearer <access>`).

Cœur du système. Le siège est réservé sous **verrou ligne** (`select_for_update()` sur le
voyage, cf. `business_rules.md §1`) : pas de surréservation possible. Une contrainte d'unicité
DB `(trip, seat_number)` (hors réservations annulées) garantit qu'un siège actif est unique.

- `ticket_number` : `BF` + année + séquence à 6 chiffres (ex: `BF2026001234`).
- `qr_code` : PNG base64 encodant le `ticket_number` (jamais l'`id` DB).
- Annulation voyageur autorisée **uniquement** jusqu'à 2h avant le départ → sinon `409`.
  L'admin (`company_admin`/`super_admin`) annule sans restriction.
- Mode hors ligne : `is_offline=true` → `synced_at=null`, `ticket_number`/`qr_code` générés
  localement (l'agent fournit le `ticket_number`).

---

## Voyageur — `IsVoyageur`

`get_queryset()` filtré sur `user = request.user`.

### POST `/api/v1/bookings/`

Crée une réservation au statut `pending` (paiement à confirmer). L'identité passager reprend
par défaut le compte voyageur ; le siège est auto-attribué si non fourni.

| Champ         | Type   | Obligatoire | Notes                                  |
|---------------|--------|-------------|----------------------------------------|
| `trip`        | int    | oui         | FK `trips.Trip` (ni annulé ni terminé) |
| `seat_number` | string | non         | auto-attribué si absent                |
| `first_name`  | string | non         | défaut = `user.prenom`                 |
| `last_name`   | string | non         | défaut = `user.nom`                    |
| `phone`       | string | non         | défaut = `user.phone`                  |

```bash
curl -X POST "https://api.transbooking.bf/api/v1/bookings/" \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"trip": 42}'
```

**201 Created** — `BookingReadSerializer` (`ticket_number`, `qr_code`, `seat_number`, `status`…).
Erreurs : `400`, `401`, `403`, `409` (voyage complet / siège pris), `410` (voyage annulé/terminé).

### GET `/api/v1/bookings/`

Liste paginée de mes réservations.

### GET `/api/v1/bookings/{id}/`

Détail d'une réservation (`BookingReadSerializer`). `404` si réservation d'un autre voyageur.

### POST `/api/v1/bookings/{id}/cancel/`

Annule la réservation et **libère le siège** (`available_seats += 1`).

| Champ    | Type   | Obligatoire | Notes              |
|----------|--------|-------------|--------------------|
| `reason` | string | non         | motif d'annulation |

**200 OK** — réservation sérialisée (`status=cancelled`).
Erreurs : `401`, `403`, `404`, `409` (moins de 2h avant le départ).

### GET `/api/v1/bookings/{id}/ticket/`

Télécharge le billet **PDF** (ReportLab) avec QR code.

**200 OK** — `Content-Type: application/pdf`. Erreurs : `401`, `403`, `404`.

---

## Agent guichet — `IsAgentGuichet`

Périmètre résolu via `request.user.agent_profile.company` (sinon `404`).

### POST `/api/v1/agent/bookings/`

Enregistre un passager au guichet (statut `paid` — l'agent encaisse). **Fonctionne hors ligne.**

| Champ                | Type     | Obligatoire | Notes                                          |
|----------------------|----------|-------------|------------------------------------------------|
| `trip`               | int      | oui         | FK `trips.Trip`                                |
| `first_name`         | string   | oui         |                                                |
| `last_name`          | string   | oui         |                                                |
| `phone`              | string   | oui         | format `+226XXXXXXXX`                          |
| `payment_method`     | string   | oui         | `cash`·`orange_money`·`moov_money`…            |
| `transaction_ref`    | string   | cond.       | requis si `payment_method ≠ cash`              |
| `seat_number`        | string   | non         | auto-attribué si absent                        |
| `amount`             | decimal  | non         | défaut = `trip.price`                          |
| `ticket_number`      | string   | cond.       | fourni si saisie hors ligne                    |
| `is_offline`         | bool     | non         | défaut `false`                                 |
| `offline_created_at` | datetime | cond.       | requis si `is_offline=true`                    |

```bash
curl -X POST "https://api.transbooking.bf/api/v1/agent/bookings/" \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"trip": 42, "first_name": "Aminata", "last_name": "TRAORE",
       "phone": "+22670000001", "payment_method": "cash"}'
```

**201 Created** — `BookingReadSerializer`.
Erreurs : `400` (champ manquant, `transaction_ref` absent), `401`, `403`, `409`, `410`.

### GET `/api/v1/agent/bookings/{ticket_number}/`

Recherche un billet par numéro (jamais par `id`). Filtré sur la compagnie de l'agent.

**200 OK** — `BookingReadSerializer`. Erreurs : `401`, `403`, `404`.

---

## Contrôleur — embarquement — `IsControleur`

### POST `/api/v1/agent/scan/`

Décode un QR code et renvoie le statut du billet avec **code couleur** (feu tricolore).
Isolation : seul un billet de la compagnie du contrôleur est résolu.

| Champ           | Type   | Obligatoire | Notes                            |
|-----------------|--------|-------------|----------------------------------|
| `qr_data`       | string | cond.       | contenu scanné (= ticket_number) |
| `ticket_number` | string | cond.       | alternative à `qr_data`          |

**200 OK**
```json
{
  "status": "valid",
  "color": "green",
  "message": "Billet valide.",
  "booking": {"ticket_number": "BF2026001234", "passenger_name": "Aminata TRAORE",
              "seat_number": "A3", "status": "paid"}
}
```
Codes couleur : `green` (payé valide) · `orange` (paiement en attente / déjà embarqué) ·
`red` (annulé / remboursé). Erreurs : `400` (champ manquant), `401`, `403`, `404` (billet introuvable).

### POST `/api/v1/agent/trips/{id}/boarding/{booking_id}/`

Coche manuellement un passager comme embarqué (idempotent).

**201 Created** — `BoardingValidationSerializer`. Erreurs : `401`, `403`, `404`.

### POST `/api/v1/agent/trips/{id}/boarding/all/`

Embarque tous les passagers payés du voyage. **Confirmation requise.**

| Champ     | Type | Obligatoire | Notes                |
|-----------|------|-------------|----------------------|
| `confirm` | bool | oui         | doit valoir `true`   |

**200 OK** — `{"boarded": <int>}`. Erreurs : `400` (confirmation absente), `401`, `403`, `404`.

### POST `/api/v1/agent/trips/{id}/boarding/validate/`

Verrouille l'embarquement et renvoie le récapitulatif.

**200 OK** — `{"trip", "total_paid", "boarded", "not_boarded", "locked": true}`.

---

## Admin compagnie — `IsCompanyAdmin`

`get_queryset()` filtré sur `trip__route__company = request.user.administered_company`.

### GET `/api/v1/company/bookings/`

Liste paginée filtrable : `?status=`, `?trip=`, `?route=`, `?payment_method=`,
`?date_from=YYYY-MM-DD`, `?date_to=YYYY-MM-DD`.

### GET `/api/v1/company/bookings/export/?format=pdf|excel`

Export des réservations (filtres identiques). `excel` (openpyxl, `.xlsx`) par défaut, `pdf`
(ReportLab). Le paramètre `?format=` est réservé ici à l'export (négociation DRF neutralisée).

**200 OK** — fichier (`application/pdf` ou `…spreadsheetml.sheet`).

---

## Services (`bookings/services.py`)

- `create_booking(validated_data, agent=None) -> Booking` — réserve un siège sous
  `select_for_update()` sur le voyage, génère `ticket_number`/`qr_code`, envoie le SMS de
  confirmation. Lève `TripUnavailable` (410), `TripFull`/`SeatTaken` (409).
- `cancel_booking(booking, cancelled_by, reason="") -> Booking` — annule et libère le siège.
  Lève `CancellationTooLate` (409) si un voyageur annule à moins de 2h du départ.
- `scan_qr(qr_data, agent) -> dict` — statut + code couleur du billet (isolation par compagnie).
- `check_in(booking, agent, method) -> BoardingValidation` — enregistre l'embarquement (idempotent).
- `generate_ticket_number() -> str` — séquence `BF{année}{000000}` annuelle.
- `generate_ticket_pdf(booking) -> bytes` — billet PDF avec QR code.
