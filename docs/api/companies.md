# API — App `companies`

Préfixe global : `/api/v1/`. Authentification via JWT (`Authorization: Bearer <access>`).

Isolation multi-tenant stricte : un `company_admin` n'accède qu'à **sa propre** compagnie
(résolue via `request.user.administered_company`). Toute tentative d'accès sans compagnie
associée renvoie `404`.

---

## Super admin — `IsSuperAdmin`

### GET `/api/v1/super/companies/`

Liste toutes les compagnies. Filtres : `?status=`, `?city=`, `?created_after=YYYY-MM-DD`,
`?created_before=YYYY-MM-DD`. Pagination `?page=` / `?page_size=`.

```bash
curl "https://api.transbooking.bf/api/v1/super/companies/?status=active" \
  -H "Authorization: Bearer <access>"
```

**200 OK** — liste paginée de compagnies (cf. `CompanyDetailSerializer`).
Erreurs : `401` (non authentifié), `403` (pas super admin).

### POST `/api/v1/super/companies/`

Crée une compagnie (active immédiatement).

| Champ              | Type    | Obligatoire | Notes                       |
|--------------------|---------|-------------|-----------------------------|
| `name`             | string  | oui         | unique                      |
| `sigle`            | string  | non         |                             |
| `description`      | string  | non         |                             |
| `city`             | string  | non         |                             |
| `address`          | string  | non         |                             |
| `phone`            | string  | non         |                             |
| `email`            | string  | non         |                             |
| `responsible_name` | string  | non         |                             |
| `responsible_phone`| string  | non         | format BF                   |
| `rccm`             | string  | non         |                             |
| `ifu`              | string  | non         |                             |
| `commission_rate`  | decimal | non         | NULL → taux global appliqué |

```bash
curl -X POST https://api.transbooking.bf/api/v1/super/companies/ \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"name":"STAF Voyages","city":"Ouagadougou","commission_rate":"8.50"}'
```

**201 Created** — `{"id": 1, "name": "STAF Voyages", "status": "active", ...}`
Erreurs : `400` (nom déjà pris), `401`, `403`.

### GET / PATCH / DELETE `/api/v1/super/companies/{id}/`

Détail, modification partielle, suppression d'une compagnie.
Erreurs : `401`, `403`, `404`.

### POST `/api/v1/super/companies/{id}/activate/`

Réactive une compagnie suspendue (ou en attente). Envoie un SMS au responsable.

**200 OK** — compagnie avec `status: "active"`.
Erreurs : `400` (déjà active), `401`, `403`, `404`.

### POST `/api/v1/super/companies/{id}/suspend/`

Suspend une compagnie. Notifie le responsable par SMS.

| Champ    | Type   | Obligatoire |
|----------|--------|-------------|
| `reason` | string | oui         |

```bash
curl -X POST https://api.transbooking.bf/api/v1/super/companies/1/suspend/ \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"reason":"Abonnement impayé"}'
```

**200 OK** — compagnie avec `status: "suspended"`.
Erreurs : `400` (motif manquant), `401`, `403`, `404`.

### GET `/api/v1/super/company-requests/`

Liste les demandes de création en attente (`status=pending`).
**200 OK** — liste paginée. Erreurs : `401`, `403`.

### POST `/api/v1/super/company-requests/{id}/approve/`

Approuve une demande en attente → `status=active`, SMS de bienvenue au responsable.
**200 OK** — compagnie approuvée.
Erreurs : `400` (demande non en attente), `401`, `403`, `404`.

### POST `/api/v1/super/company-requests/{id}/reject/`

Rejette une demande. `reason` obligatoire ; SMS envoyé au responsable.

| Champ    | Type   | Obligatoire |
|----------|--------|-------------|
| `reason` | string | oui         |

**200 OK** — compagnie avec `status: "rejected"`.
Erreurs : `400` (motif manquant / demande non en attente), `401`, `403`, `404`.

---

## Company admin — `IsCompanyAdmin`

### GET / PATCH `/api/v1/company/settings/`

Lit / met à jour les paramètres de la compagnie de l'utilisateur courant
(`name`, `sigle`, `description`, `logo`, `banner`, `primary_color`, `welcome_message`,
`address`, `phone`, `email`, `responsible_name`, `responsible_phone`).

```bash
curl -X PATCH https://api.transbooking.bf/api/v1/company/settings/ \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"primary_color":"#1A73E8","welcome_message":"Bon voyage !"}'
```

**200 OK** — paramètres mis à jour.
Erreurs : `400`, `401`, `403`, `404` (aucune compagnie associée).

### GET / PATCH `/api/v1/company/settings/payment-methods/`

Lit / active-désactive les moyens de paiement. Le PATCH attend une liste
`payment_methods` de `{method, is_active}` (upsert par méthode).

```bash
curl -X PATCH https://api.transbooking.bf/api/v1/company/settings/payment-methods/ \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"payment_methods":[{"method":"orange_money","is_active":true},{"method":"cash","is_active":true}]}'
```

**200 OK** — liste à jour des moyens de paiement.
Méthodes valides : `cash`, `orange_money`, `moov_money`, `coris_money`, `telecel_money`, `card`.
Erreurs : `400`, `401`, `403`, `404`.

### GET / PATCH `/api/v1/company/settings/notifications/`

Lit / met à jour les 3 commutateurs SMS (`sms_booking_confirmation`,
`sms_departure_reminder`, `sms_parcel_arrival`). Créés automatiquement au premier accès.

**200 OK** — `{"sms_booking_confirmation": true, "sms_departure_reminder": true, "sms_parcel_arrival": true}`
Erreurs : `400`, `401`, `403`, `404`.

---

## Public — sans authentification

### GET `/api/v1/public/companies/`

Liste les compagnies **actives** uniquement (page d'accueil). Réponse **mise en cache 1 h**.

```bash
curl https://api.transbooking.bf/api/v1/public/companies/
```

**200 OK** — liste paginée : `{"id", "name", "sigle", "logo", "description", "city", "rating"}`.
`rating` = note moyenne (sera annotée depuis l'app `reviews`, `null` tant qu'indisponible).

### GET `/api/v1/public/companies/{id}/`

Fiche publique détaillée d'une compagnie active (ajoute `phone`, `email`, `reviews`).

**200 OK** — fiche compagnie. `reviews` = `[]` (branché sur l'app `reviews`, PROMPT 08).
Erreurs : `404` (compagnie inexistante ou non active).
