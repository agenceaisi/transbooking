# API — App `dashboard` (statistiques agrégées)

Préfixe global : `/api/v1/`. Authentification via JWT (`Authorization: Bearer <access>`).

Tableaux de bord **en lecture seule** (aucun modèle propre). Toutes les statistiques sont
calculées via les agrégations de l'ORM Django (`Count`, `Sum`, `Avg`, `annotate`, `Trunc*`) —
jamais de SQL brut.

- **Cache** : chaque endpoint est mis en cache 5 minutes (`cache_page(300)`).
- **Isolation multi-tenant** : le cache est varié sur l'en-tête `Authorization`, donc la réponse
  d'un utilisateur n'est **jamais** servie à un autre. Les vues `company` filtrent toujours par la
  compagnie de l'admin courant (`request.user.administered_company`).
- **Période** (vues `company` et super `bookings-chart`) : query param `?period=` parmi
  `today` · `week` · `month` (défaut) · `year` · `custom`. Pour `custom`, fournir `start_date` et
  `end_date` au format `AAAA-MM-JJ` (sinon `400`). La fenêtre de comparaison `vs_previous_period`
  est toujours la période précédente de même durée.

---

## GET `/api/v1/dashboard/traveler/`

Accueil voyageur : prochains voyages, compteurs de réservations, notifications récentes.

**Auth** : JWT requis — rôle `voyageur` (`IsVoyageur`).

**Réponse `200`**

```json
{
  "next_trips": [
    {
      "ticket_number": "BF2026001234",
      "origin": "Ouagadougou",
      "destination": "Bobo-Dioulasso",
      "departure_time": "2026-07-02T06:00:00Z",
      "seat_number": "A3",
      "status": "paid"
    }
  ],
  "active_bookings_count": 2,
  "pending_count": 1,
  "recent_notifications": []
}
```

> `recent_notifications` reste `[]` tant que l'app `notifications` n'expose pas de modèle (PROMPT 11).

**Erreurs** : `401` (non authentifié), `403` (rôle non voyageur).

---

## GET `/api/v1/agent/dashboard/`

Tableau de bord agent : 3 prochains départs de sa gare/véhicule, alertes en attente, état de
connexion.

**Auth** : JWT requis — rôle `agent_guichet` ou `controleur` (`IsAgent`).

**Réponse `200`**

```json
{
  "next_departures": [
    {
      "trip_id": 12,
      "origin": "Ouagadougou",
      "destination": "Koudougou",
      "departure_time": "2026-06-30T14:00:00Z",
      "available_seats": 18,
      "passenger_count": 12
    }
  ],
  "pending_alerts": 0,
  "connection_status": "online"
}
```

**Erreurs** : `401`, `403`.

---

## GET `/api/v1/company/dashboard/`

KPI de la compagnie sur la période, avec deltas vs période précédente.

**Auth** : JWT requis — rôle `company_admin` (`IsCompanyAdmin`).

**Query params** : `period`, `start_date`, `end_date` (cf. en-tête).

**Réponse `200`**

```json
{
  "period": "Ce mois",
  "revenue_total": 1250000.0,
  "fill_rate_avg": 72.5,
  "bookings_count": 340,
  "avg_rating": 4.2,
  "vs_previous_period": {
    "revenue_total": 150000.0,
    "fill_rate_avg": 4.1,
    "bookings_count": 28
  }
}
```

**Erreurs** : `400` (`custom` sans bornes ou date invalide), `401`, `403`, `404` (aucune compagnie
rattachée).

---

## GET `/api/v1/company/dashboard/revenue-chart/`

Recettes confirmées regroupées par jour (ou par semaine si la période dépasse 92 jours).

**Réponse `200`** : `[{ "date": "2026-06-29", "revenue": 85000.0 }, ...]`

---

## GET `/api/v1/company/dashboard/fill-rate-by-route/`

Taux de remplissage moyen par trajet sur la période.

**Réponse `200`** : `[{ "route_label": "Ouagadougou -> Bobo-Dioulasso", "fill_rate_pct": 78.3 }]`

---

## GET `/api/v1/company/dashboard/payment-breakdown/`

Répartition des paiements confirmés par méthode.

**Réponse `200`** : `[{ "method": "cash", "amount": 600000.0, "pct": 60.0 }]`

---

## GET `/api/v1/company/dashboard/top-routes/`

Top 5 des trajets par recette confirmée.

**Réponse `200`** : `[{ "route": "Ouagadougou -> Bobo-Dioulasso", "revenue": 450000.0, "passengers": 90 }]`

---

## GET `/api/v1/company/dashboard/agent-activity/`

Activité du **jour** par agent de la compagnie (réservations et colis saisis).

**Réponse `200`** : `[{ "agent_name": "Awa Ouedraogo", "bookings_today": 12, "parcels_today": 3 }]`

---

## GET `/api/v1/company/dashboard/alerts/`

Compteurs d'alertes opérationnelles en temps réel.

**Réponse `200`**

```json
{
  "unresolved_claims": 4,
  "unreturned_parcels": 7,
  "speed_reports_pending": 2
}
```

---

## GET `/api/v1/company/dashboard/export/?format=pdf|excel`

Rapport complet (synthèse + top trajets + répartition paiements). **Non mis en cache.**

**Query params** : `format` = `excel` (défaut, `.xlsx`) ou `pdf` ; plus `period` / `start_date` /
`end_date`.

**Réponse `200`** : fichier binaire (`Content-Disposition: attachment`).
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` ou `application/pdf`.
Si `openpyxl` est absent, repli automatique sur un export CSV.

---

## GET `/api/v1/super/dashboard/`

Vue plateforme globale.

**Auth** : JWT requis — rôle `super_admin` (`IsSuperAdmin`).

**Réponse `200`**

```json
{
  "total_companies": 18,
  "active_companies": 14,
  "total_bookings": 12450,
  "total_commission_revenue": 1875000.0,
  "active_users": 3120
}
```

---

## GET `/api/v1/super/dashboard/revenue-by-company/`

Recettes et commissions agrégées par compagnie.

**Réponse `200`** : `[{ "company": "Rakieta", "revenue": 4500000.0, "commission": 450000.0 }]`

---

## GET `/api/v1/super/dashboard/bookings-chart/`

Réservations globales dans le temps (jour ou semaine selon la période).

**Query params** : `period`, `start_date`, `end_date`.

**Réponse `200`** : `[{ "date": "2026-06-29", "count": 142 }, ...]`

**Erreurs** : `400` (`custom` sans bornes), `401`, `403`.

---

## Exemple cURL

```bash
curl -H "Authorization: Bearer $ACCESS" \
  "https://api.transbooking.bf/api/v1/company/dashboard/?period=custom&start_date=2026-06-01&end_date=2026-06-30"
```
