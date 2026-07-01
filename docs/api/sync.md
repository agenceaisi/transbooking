# API — App `sync` (synchronisation hors ligne)

Préfixe global : `/api/v1/`. Authentification via JWT (`Authorization: Bearer <access>`).
Tous les endpoints requièrent le rôle `agent_guichet` **ou** `controleur` (permission `IsAgent`)
et un `AgentProfile` rattaché à une compagnie (sinon `404`).

Moteur de synchronisation différée des données saisies sans connexion par les agents
(cf. `business_rules.md §6`).

- L'intégralité d'une synchronisation s'exécute dans **une seule transaction atomique**.
- **Idempotence** : un `ticket_number` / `tracking_number` déjà synchronisé est ignoré
  silencieusement (un re-`POST` du même lot ne crée rien).
- **Conflit de siège** : si le siège saisi hors ligne est déjà occupé, le prochain siège libre
  est attribué automatiquement et un `SyncConflict` (résolu) est journalisé avec une `resolution`
  en français clair (ex : `Siege A3 deja attribue. Nouveau siege attribue : B7.`).
- **Rejets** : voyage complet (`trip_full`), annulé/terminé (`trip_unavailable`), donnée invalide
  ou hors compagnie (`invalid`) → retournés dans `errors[]` (non résolus).
- **Isolation multi-tenant** : un agent ne synchronise que les voyages/colis de sa compagnie.

---

## POST `/api/v1/agent/sync/`

Synchronise un lot de données hors ligne (réservations, colis, embarquements).

**Auth** : JWT requis — rôle `agent_guichet` ou `controleur`.

**Body (JSON)**

| Champ         | Type  | Obligatoire | Description                                  |
|---------------|-------|-------------|----------------------------------------------|
| `bookings`    | array | Non         | Réservations saisies hors ligne              |
| `parcels`     | array | Non         | Colis enregistrés hors ligne                 |
| `validations` | array | Non         | Embarquements validés hors ligne             |

Objet `bookings[]` :

| Champ                | Type     | Obligatoire | Description                                |
|----------------------|----------|-------------|--------------------------------------------|
| `ticket_number`      | string   | Oui         | Numéro de billet généré localement (`BF…`) |
| `trip_id`            | int      | Oui         | ID du voyage (de la compagnie de l'agent)  |
| `first_name`         | string   | Oui         | Prénom du passager                         |
| `last_name`          | string   | Oui         | Nom du passager                            |
| `phone`              | string   | Oui         | Téléphone du passager                      |
| `seat_number`        | string   | Non         | Siège saisi (réattribué si déjà pris)      |
| `amount`             | decimal  | Non         | Montant (défaut : prix du voyage)          |
| `payment_method`     | string   | Non         | `cash` · `orange_money` · …                |
| `offline_created_at` | datetime | Oui         | Date de saisie hors ligne                  |

Objet `parcels[]` :

| Champ                  | Type     | Obligatoire | Description                              |
|------------------------|----------|-------------|------------------------------------------|
| `tracking_number`      | string   | Oui         | Numéro de suivi généré localement (`COL…`) |
| `origin_city`          | int      | Oui         | ID ville de départ                       |
| `destination_city`     | int      | Oui         | ID ville d'arrivée                       |
| `destination_station`  | int      | Non         | ID gare d'arrivée (même compagnie)       |
| `trip`                 | int      | Non         | ID voyage transporteur (même compagnie)  |
| `sender_name`          | string   | Oui         | Nom expéditeur                           |
| `sender_phone`         | string   | Oui         | Téléphone expéditeur                     |
| `recipient_name`       | string   | Oui         | Nom destinataire                         |
| `recipient_phone`      | string   | Oui         | Téléphone destinataire                   |
| `description`          | string   | Non         | Description du colis                     |
| `weight_kg`            | decimal  | Oui         | Poids (sert au calcul du tarif)          |
| `offline_created_at`   | datetime | Oui         | Date de saisie hors ligne                |

Objet `validations[]` :

| Champ                | Type     | Obligatoire | Description                            |
|----------------------|----------|-------------|----------------------------------------|
| `ticket_number`      | string   | Oui         | Billet embarqué (de la compagnie)      |
| `offline_created_at` | datetime | Oui         | Date de validation hors ligne          |

**Exemple de requête**

```bash
curl -X POST https://api.transbooking.bf/api/v1/agent/sync/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "bookings": [
      {
        "ticket_number": "BF2026001234",
        "trip_id": 42,
        "first_name": "Aminata",
        "last_name": "TRAORE",
        "phone": "+22670000001",
        "seat_number": "A3",
        "amount": "5000.00",
        "payment_method": "cash",
        "offline_created_at": "2026-06-01T08:23:00Z"
      }
    ],
    "parcels": [],
    "validations": []
  }'
```

**Réponse `200`**

```json
{
  "synced": { "bookings": 1, "parcels": 0, "validations": 0 },
  "conflicts": [
    {
      "type": "seat_conflict",
      "ticket_number": "BF2026001234",
      "original_seat": "A3",
      "assigned_seat": "B7",
      "message": "Siege A3 deja attribue. Nouveau siege attribue : B7."
    }
  ],
  "errors": []
}
```

**Erreurs** : `400` (payload invalide), `401` (non authentifié), `403` (rôle non agent),
`404` (aucun profil agent).

---

## GET `/api/v1/agent/sync/logs/`

Historique paginé des synchronisations de l'agent courant (le plus récent en premier).

**Réponse `200`** (extrait `results[]`)

```json
{
  "id": 12,
  "bookings_synced": 3,
  "parcels_synced": 1,
  "validations_synced": 5,
  "conflicts_count": 2,
  "errors_count": 0,
  "conflicts": [
    {
      "id": 7,
      "entity": "booking",
      "conflict_type": "seat_conflict",
      "conflict_type_display": "Conflit de siege",
      "reference": "BF2026001234",
      "original_seat": "A3",
      "assigned_seat": "B7",
      "resolution": "Siege A3 deja attribue. Nouveau siege attribue : B7.",
      "resolved": true,
      "created_at": "2026-06-01T09:00:00Z"
    }
  ],
  "created_at": "2026-06-01T09:00:00Z"
}
```

---

## GET `/api/v1/agent/sync/conflicts/`

Conflits **résolus** (siège réattribué) lors de la **dernière** synchronisation de l'agent.
Non paginé. Renvoie `[]` si l'agent n'a jamais synchronisé.

**Réponse `200`**

```json
[
  {
    "id": 7,
    "entity": "booking",
    "conflict_type": "seat_conflict",
    "conflict_type_display": "Conflit de siege",
    "reference": "BF2026001234",
    "original_seat": "A3",
    "assigned_seat": "B7",
    "resolution": "Siege A3 deja attribue. Nouveau siege attribue : B7.",
    "resolved": true,
    "created_at": "2026-06-01T09:00:00Z"
  }
]
```

---

## GET `/api/v1/agent/offline-data/`

Télécharge tout ce dont l'agent a besoin pour travailler hors ligne aujourd'hui, dans le
périmètre de sa gare et/ou de son véhicule (voyages du jour non annulés, réservations actives
de ces voyages, colis arrivés en attente de remise). Non paginé.

**Réponse `200`**

```json
{
  "trips": [
    {
      "id": 42,
      "origin_city": "Ouagadougou",
      "destination_city": "Bobo-Dioulasso",
      "departure_time": "2026-06-30T06:00:00Z",
      "available_seats": 18,
      "vehicle": "11-AA-0042",
      "seat_plan": { "layout": [[1, 2], [3, 4]], "reserved": [0] },
      "status": "scheduled"
    }
  ],
  "bookings": [
    {
      "ticket_number": "BF2026001234",
      "trip_id": 42,
      "passenger_name": "Aminata TRAORE",
      "phone": "+22670000001",
      "seat_number": "A3",
      "qr_code": "<base64-png>",
      "status": "paid"
    }
  ],
  "parcel_arrivals": [
    {
      "tracking_number": "COL2026000456",
      "recipient_name": "Fatou DIALLO",
      "recipient_phone": "+22660000011",
      "destination_city": "Bobo-Dioulasso",
      "status": "arrived"
    }
  ]
}
```

**Erreurs** : `401` (non authentifié), `403` (rôle non agent), `404` (aucun profil agent).
