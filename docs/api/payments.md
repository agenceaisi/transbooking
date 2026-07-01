# API — App `payments`

Préfixe global : `/api/v1/`. Authentification via JWT (`Authorization: Bearer <access>`).

Gestion des paiements de réservations. **Mobile Money manuel** (cf. `business_rules.md §2`) :
l'agent demande la référence de transaction au client et la saisit — le système ne vérifie
**pas** en temps réel. La confirmation d'un paiement passe la réservation à `paid`.

- Le siège est déjà réservé à la **création** de la réservation (décrément de `available_seats`
  sous verrou ligne, cf. `apps.bookings.services.create_booking`). La confirmation du paiement
  ne re-décrémente donc pas : elle marque seulement la réservation `paid`.
- `transaction_ref` est une **donnée sensible** : masquée dans les logs et les réponses API
  (`****` + 4 derniers caractères).
- Commission plateforme figée à la confirmation : `montant × company.commission_rate / 100`
  (taux global `COMMISSION_RATE_DEFAULT` si `commission_rate` est NULL).
- `method` : `cash · orange_money · moov_money · coris_money · telecel_money · card`.
- `status` : `pending · paid · failed · refunded`.

> **Colis** : le paiement de colis (`parcel_id`) sera disponible après l'implémentation du
> module `parcels` (PROMPT 07). Actuellement, fournir `parcel_id` renvoie `400`.

---

## Voyageur / authentifié

`get_queryset()` est filtré par périmètre : le voyageur ne voit que les paiements de **ses**
réservations ; l'agent/admin uniquement ceux de **sa** compagnie ; le super admin voit tout.

### POST `/api/v1/payments/`

Initie un paiement au statut `pending`.

| Champ        | Type   | Obligatoire | Notes                                        |
|--------------|--------|-------------|----------------------------------------------|
| `booking_id` | int    | oui*        | FK `bookings.Booking` (\*ou `parcel_id`)     |
| `parcel_id`  | int    | non         | Non encore supporté → `400`                  |
| `method`     | string | oui         | un des moyens de paiement                    |
| `phone`      | string | non         | numéro du payeur (Mobile Money)              |

```bash
curl -X POST "https://api.transbooking.bf/api/v1/payments/" \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"booking_id": 42, "method": "orange_money", "phone": "+22670000001"}'
```

**201 Created**
```json
{
  "id": 7,
  "ticket_number": "BF2026001234",
  "amount": "5000.00",
  "method": "orange_money",
  "method_display": "Orange Money",
  "status": "pending",
  "status_display": "En attente",
  "transaction_ref": "",
  "phone": "+22670000001",
  "receipt_url": "",
  "paid_at": null,
  "created_at": "2026-06-30T09:12:00Z"
}
```

Erreurs : `400` (champ manquant / `parcel_id` non supporté), `401`, `409` (réservation déjà réglée).

### GET `/api/v1/payments/{id}/`

Renvoie le statut d'un paiement. `404` si hors périmètre de l'utilisateur.

### POST `/api/v1/payments/{id}/verify/`

Confirme le paiement (saisie de la `transaction_ref` pour le Mobile Money / carte).
Met à jour `booking.status = 'paid'` et fige la commission.

| Champ             | Type   | Obligatoire | Notes                                   |
|-------------------|--------|-------------|-----------------------------------------|
| `transaction_ref` | string | cond.       | Obligatoire si `method ≠ cash`          |

```bash
curl -X POST "https://api.transbooking.bf/api/v1/payments/7/verify/" \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"transaction_ref": "OM240630ABCD"}'
```

**200 OK** → paiement `paid` (`transaction_ref` masqué : `****ABCD`).

Erreurs : `400` (réf manquante hors espèces), `401`, `404`, `409` (déjà confirmé).

### GET `/api/v1/payments/{id}/receipt/`

Télécharge le reçu PDF (`application/pdf`) : n° de transaction, montant, date, compagnie,
trajet, passager, QR code.

---

## Agent guichet — `IsAgentGuichet`

### POST `/api/v1/agent/payments/`

Encaisse au guichet (espèces ou Mobile Money) : initie **et** confirme en une étape.
Isolation multi-tenant : la réservation doit appartenir à la compagnie de l'agent (`404` sinon).

| Champ             | Type   | Obligatoire | Notes                                   |
|-------------------|--------|-------------|-----------------------------------------|
| `booking_id`      | int    | oui         | FK `bookings.Booking` de sa compagnie   |
| `method`          | string | oui         | un des moyens de paiement               |
| `transaction_ref` | string | cond.       | Obligatoire si `method ≠ cash`          |
| `phone`           | string | non         | numéro du payeur                        |

```bash
curl -X POST "https://api.transbooking.bf/api/v1/agent/payments/" \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"booking_id": 42, "method": "cash"}'
```

**201 Created** → paiement `paid`, réservation `paid`.

Erreurs : `400` (réf manquante hors espèces), `401`, `403` (rôle), `404` (réservation hors compagnie).
