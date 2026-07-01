# API — App `users`

Préfixe global : `/api/v1/`. Authentification via JWT (`Authorization: Bearer <access>`).

Toutes les routes `auth/*` sont protégées par un rate limit de **10 requêtes POST / minute
par IP** (`django-ratelimit`) ; au-delà → `429 Too Many Requests`.

---

## POST `/api/v1/auth/register/`

Inscription d'un voyageur (public, rôle `voyageur` attribué automatiquement).

| Champ      | Type   | Obligatoire | Notes                                            |
|------------|--------|-------------|--------------------------------------------------|
| `prenom`   | string | oui         | max 100                                          |
| `nom`      | string | oui         | max 100                                          |
| `phone`    | string | oui         | unique, format BF `+226XXXXXXXX` ou `0XXXXXXXX`  |
| `password` | string | oui         | min 8 caractères (write-only)                    |
| `email`    | string | non         | optionnel                                        |

```bash
curl -X POST https://api.transbooking.bf/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"prenom":"Awa","nom":"Ouedraogo","phone":"+22670000001","password":"password123","email":"awa@example.com"}'
```

**201 Created**
```json
{"prenom": "Awa", "nom": "Ouedraogo", "phone": "+22670000001", "email": "awa@example.com", "role": "voyageur"}
```

Erreurs : `400` (téléphone déjà utilisé, format invalide, mot de passe trop court),
`429` (trop de tentatives).

---

## POST `/api/v1/auth/login/`

Connexion. Retourne les tokens JWT enrichis du rôle et du prénom.

| Champ      | Type   | Obligatoire |
|------------|--------|-------------|
| `phone`    | string | oui         |
| `password` | string | oui         |

```bash
curl -X POST https://api.transbooking.bf/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"phone":"+22670000001","password":"password123"}'
```

**200 OK**
```json
{"refresh": "<refresh_token>", "access": "<access_token>", "role": "voyageur", "prenom": "Awa"}
```

Erreurs : `400` (champs manquants), `401` (identifiants invalides), `429`.

---

## POST `/api/v1/auth/token/refresh/`

Rafraîchit un token d'accès à partir d'un refresh token valide.

| Champ     | Type   | Obligatoire |
|-----------|--------|-------------|
| `refresh` | string | oui         |

```bash
curl -X POST https://api.transbooking.bf/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<refresh_token>"}'
```

**200 OK**
```json
{"access": "<new_access_token>"}
```

Erreurs : `400` (champ manquant), `401` (refresh invalide/expiré), `429`.

---

## POST `/api/v1/auth/logout/`

Révoque (blacklist) le refresh token. Authentification requise.

| Champ     | Type   | Obligatoire |
|-----------|--------|-------------|
| `refresh` | string | oui         |

```bash
curl -X POST https://api.transbooking.bf/api/v1/auth/logout/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<refresh_token>"}'
```

**204 No Content** (corps vide)

Erreurs : `400` (champ manquant, token invalide/expiré), `401` (non authentifié), `429`.

---

## GET `/api/v1/users/me/`

Profil de l'utilisateur connecté. Authentification requise.

```bash
curl https://api.transbooking.bf/api/v1/users/me/ \
  -H "Authorization: Bearer <access_token>"
```

**200 OK**
```json
{"prenom": "Awa", "nom": "Ouedraogo", "phone": "+22670000001", "email": "awa@example.com", "role": "voyageur"}
```

Erreurs : `401` (non authentifié).

---

## PATCH `/api/v1/users/me/`

Mise à jour partielle du profil. Seuls `phone` et `email` sont modifiables ;
les autres champs envoyés sont ignorés. Authentification requise.

| Champ   | Type   | Obligatoire | Notes                                           |
|---------|--------|-------------|-------------------------------------------------|
| `phone` | string | non         | unique, format BF `+226XXXXXXXX` ou `0XXXXXXXX` |
| `email` | string | non         |                                                 |

```bash
curl -X PATCH https://api.transbooking.bf/api/v1/users/me/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"phone":"+22670000005","email":"new@example.com"}'
```

**200 OK**
```json
{"prenom": "Awa", "nom": "Ouedraogo", "phone": "+22670000005", "email": "new@example.com", "role": "voyageur"}
```

Erreurs : `400` (téléphone déjà utilisé, format invalide), `401` (non authentifié).
