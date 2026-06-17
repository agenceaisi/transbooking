# TransBooking BF

> Plateforme de gestion du transport interurbain au Burkina Faso — API REST Django

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.x-green)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.15-red)](https://www.django-rest-framework.org)
[![License](https://img.shields.io/badge/License-Proprietary-lightgrey)]()

---

## Présentation

TransBooking BF est une solution web/mobile permettant aux compagnies de transport burkinabè de gérer leurs voyages, billets, colis et agents. Elle offre un mode **hors ligne** pour les agents en zone à faible connectivité, avec synchronisation automatique au retour de la connexion.

**5 acteurs** : Super Administrateur · Admin Compagnie · Agent Guichet · Contrôleur · Voyageur

---

## Stack technique

| Composant | Choix |
|-----------|-------|
| Backend | Django 5.x + Django REST Framework |
| Auth | SimpleJWT (access + refresh tokens) |
| Base de données | PostgreSQL 16 |
| Cache / Broker | Redis |
| Tâches async | Celery + Celery Beat |
| Paiement | Orange Money · Moov Money · Coris Money · Telecel Money · Espèces |
| SMS | Abstraction provider (configurable) |
| Export | ReportLab (PDF) · openpyxl (Excel) |
| QR Code | `qrcode` lib → base64 PNG |

---

## Structure du projet

```
transbooking/
├── config/                   # Paramètres, URLs, Celery
│   └── settings/
│       ├── base.py
│       ├── dev.py
│       └── prod.py
├── apps/
│   ├── users/                # Utilisateurs, rôles, profils agents
│   ├── companies/            # Compagnies, paiements, notifications
│   ├── subscriptions/        # Forfaits, abonnements, factures
│   ├── geography/            # Villes, gares
│   ├── vehicles/             # Véhicules, plan des sièges
│   ├── routes/               # Trajets, escales
│   ├── trips/                # Voyages planifiés
│   ├── bookings/             # Réservations, billets, embarquement
│   ├── payments/             # Paiements
│   ├── parcels/              # Colis, notifications destinataire
│   ├── claims/               # Réclamations clients
│   ├── reviews/              # Avis clients
│   ├── speed_reports/        # Signalements excès de vitesse
│   ├── messaging/            # Messagerie agent ↔ client
│   ├── notifications/        # Notifications in-app
│   ├── sync/                 # Synchronisation hors ligne
│   └── dashboard/            # Statistiques & tableaux de bord
└── utils/
    ├── permissions.py        # Classes de permissions par rôle
    ├── pagination.py
    ├── sms.py
    └── qr.py
```

---

## Installation

### Prérequis

- Python 3.12+
- PostgreSQL 16+
- Redis 7+

### Démarrage rapide

```bash
# 1. Cloner le repo
git clone https://github.com/<org>/transbooking-bf.git
cd transbooking-bf

# 2. Environnement virtuel
python -m venv venv
source venv/bin/activate

# 3. Dépendances
pip install -r requirements.txt

# 4. Variables d'environnement
cp .env.example .env
# Éditer .env avec vos valeurs

# 5. Base de données
python manage.py migrate

# 6. Super administrateur initial
python manage.py createsuperuser

# 7. Lancer le serveur
python manage.py runserver
```

### Variables d'environnement (`.env`)

```env
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=postgres://user:password@localhost:5432/transbooking
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=60
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# SMS
SMS_PROVIDER=console          # console | orange | moov
SMS_API_KEY=
SMS_SENDER_ID=TransBookingBF

# Stockage fichiers
STORAGE_BACKEND=local         # local | s3
AWS_BUCKET_NAME=

# Commission par défaut (%)
COMMISSION_RATE_DEFAULT=5.00
```

### Lancer Celery

```bash
# Worker
celery -A config worker -l info

# Scheduler (tâches planifiées)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Acteurs & permissions

| Rôle | Préfixe API | Accès principal |
|------|-------------|-----------------|
| `super_admin` | `/api/v1/super/` | Gestion globale de la plateforme |
| `company_admin` | `/api/v1/company/` | Sa compagnie uniquement |
| `agent_guichet` | `/api/v1/agent/` | Enregistrement passagers & colis |
| `controleur` | `/api/v1/agent/` | Scan QR, embarquement |
| `voyageur` | `/api/v1/` | Réservations, colis, réclamations |

---

## Fonctionnalités clés

### Mode hors ligne (agents)
Les agents peuvent travailler sans connexion internet. Les données sont stockées localement et synchronisées automatiquement au retour de la connexion via `POST /api/v1/agent/sync/`. Les conflits de sièges sont résolus automatiquement.

### QR Code billets
Chaque réservation génère un numéro unique (`BF2026XXXXXX`) et un QR code. Le contrôleur scanne ce QR à l'embarquement pour valider en moins d'une seconde.

### Suivi de colis
Chaque colis reçoit un numéro de suivi (`COL2026XXXXXX`). Le destinataire est notifié par SMS à l'arrivée. Le suivi est public : pas de compte requis.

### Tableaux de bord
L'admin compagnie accède à : chiffre d'affaires, taux de remplissage par trajet, répartition des paiements, top 5 des lignes, activité des agents — filtrables par période.

---

## API — Aperçu des endpoints

La documentation complète est disponible dans [`docs/api_endpoints.md`](docs/api_endpoints.md).

```
/api/v1/auth/          # Authentification (login, register, refresh)
/api/v1/users/         # Profil utilisateur
/api/v1/trips/         # Recherche de voyages (public)
/api/v1/bookings/      # Réservations voyageur
/api/v1/parcels/track/ # Suivi colis (public)
/api/v1/agent/         # Interface agents (guichet + contrôleur)
/api/v1/company/       # Interface admin compagnie
/api/v1/super/         # Interface super administrateur
```

> L'API intègre Swagger UI — accessible en dev sur `/api/v1/docs/`

---

## Tests

```bash
# Lancer tous les tests
pytest

# Avec couverture
pytest --cov=apps --cov-report=html

# Une app spécifique
pytest apps/bookings/
```

Couverture cible : **≥ 70%**

---

## Données métier importantes

- `Trip.available_seats` est décrémenté avec `select_for_update()` pour éviter les surréservations.
- Le tarif colis = `poids_kg × prix_par_kg + frais_fixes` selon la tranche de distance.
- La commission TransBooking = `montant × taux_commission / 100` prélevée par réservation.
- Un avis ne peut être déposé qu'après un voyage au statut `completed`.
- Les réclamations sans réponse après 48h sont signalées automatiquement au super admin.

---

## Équipe & contact

Développé par **Agence Internationale de Statistique et de l'Informatique** — Juin 2026