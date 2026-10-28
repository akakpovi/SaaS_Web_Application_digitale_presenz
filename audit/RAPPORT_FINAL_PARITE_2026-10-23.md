# Rapport final — parité API ↔ UI

**Date :** 2026-10-23
**Périmètre :** les quatre écarts utilisateur encore ouverts après
`RAPPORT_PARITE_API_UI_2026-10-23.md`
**Conclusion :** les quatre écarts sont fermés et vérifiés de bout en bout sur
la pile réelle. La parité **orientée utilisateur** est à 100 % sur le périmètre
défini ci-dessous. Les routes internes restantes sont listées en §6.

## 1. Synthèse

| Écart précédent | État | Preuve |
| --- | --- | --- |
| `/auth/email/verify/` sans page | **Fermé** | e-mail réel → lien → `is_email_verified: true` |
| `/public/scan/*` sans UI | **Fermé** | scan réel `3243`, score 85, 7 catégories |
| `/reviews/:id/approve/` sans action | **Fermé** | bouton UI, `?approved=true` renvoie 1 ligne |
| `/scans/:id/results/` non appelé | **Fermé** | 7 résultats agrégés, 85/100 consolidé |

## 2. Mission 1 — vérification d'e-mail

### Implémentation

- Nouvelle page [`VerifyEmail.tsx`](../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/VerifyEmail.tsx),
  route publique `/verify-email` dans `App.tsx`.
- Lit `uid` et `token` dans la query string et appelle
  `POST /api/v1/auth/email/verify/` (`{uidb64, token}`).
- Quatre états : vérification (spinner), succès, lien incomplet, échec.
  - succès → « Email verified » + « Sign in » (ou « Go to dashboard » si déjà
    connecté) ;
  - échec → message serveur réel (« Invalid or expired verification token. »)
    + renvoi d'un lien si l'utilisateur est connecté
    (`POST /auth/email/verify/resend/`) ;
  - le token est à usage unique : un `useRef` empêche le double appel de
    React StrictMode en développement.
- `refreshUser()` après succès : le badge « Verified » de la sidebar se met à
  jour sans reconnexion.

### Correctif de déploiement indispensable

Le lien e-mail pointe vers `/verify-email`, mais nginx ne servait la coquille
SPA que pour `/app/`, `/report/`, `/blog/` et `/admin`. En production, les deux
nouvelles routes renvoyaient un **vrai 404** (vérifié : `HTTP 404`, page
`Page not found | Presence`), alors que le serveur de développement
fonctionnait. `nginx.conf` a été corrigé :

```nginx
location /scan/ {
    try_files $uri /index.html;
}
location = /verify-email {
    try_files /index.html =404;
}
```

Après reconstruction du conteneur : `/verify-email` et `/scan/:id` renvoient
`HTTP 200`.

### Vérification de bout en bout

1. Inscription de `paritytest@example.com` → e-mail reçu dans Mailpit
   (`Verify your Presence email address`).
2. Extraction du lien réel :
   `/verify-email?uid=MTk&token=dgwln4-…`.
3. Ouverture du lien dans le navigateur, sur le **bundle de production** :
   la page affiche « Email verified ».
4. `POST /auth/email/verify/` → `200`, puis connexion → `is_email_verified:
   true`.
5. Lien falsifié (`token=invalid-token-123`) → « Verification failed » +
   « Invalid or expired verification token. »

## 3. Mission 2 — scanner public (génération de leads)

### Implémentation

- [`ToolPage.tsx`](../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/ToolPage.tsx)
  ne simule plus rien : le `setTimeout` et les résultats d'exemple ont été
  supprimés. Le formulaire appelle `POST /public/scan/` puis redirige vers
  `/scan/:id`.
- [`PublicScanResult.tsx`](../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/PublicScanResult.tsx)
  (nouvelle route publique) :
  - polling de `GET /public/scan/:id/status/` toutes les 2 s tant que le scan
    est `queued`/`running` ;
  - progression pondérée + les 7 étapes réelles ;
  - score réel, résumé (critique / avertissements / réussis), une carte par
    catégorie avec le message du scanner et le correctif (`nginx`, `apache`,
    `code`) repliable ;
  - capture d'e-mail : `POST /public/scan/:id/email/` avec confirmation réelle ;
  - CTA « Create free account » vers
    `/register?scan_id=…&url=…` (fourni par le backend), plus la liste des
    limites du rapport public.
- [`Landing.tsx`](../SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2/src/pages/Landing.tsx) :
  le champ du hero ne mène plus vers `/onboarding`. Il transmet le domaine à
  `/tools/website-checker?domain=…`, qui démarre le scan réel immédiatement.
- Les quatre outils (`website`, `ssl`, `dns`, `email-security`) utilisent le
  même flux réel ; les jeux de résultats codés en dur ont été retirés.

### Vérification

- `POST /public/scan/ {"domain":"example.com"}` → `202`, id `3243`.
- Polling → `completed`, `score: 85`, 7 catégories (`website`, `ssl`, `dns`,
  `email_security`, `security_headers`, `performance`, `uptime`).
- Page `/scan/3243` : « 85 / 100 », « Report ready », 7 cartes, correctif nginx
  affiché, CTA présent.
- « Email me this report » → « Report sent to ui-lead@example.com » (e-mail
  réellement remis par Mailpit).
- Limite de débit : la 6ᵉ requête publique/heure renvoie un message explicite
  (« Request was throttled. Expected available in 3600 seconds. ») au lieu
  d'un échec silencieux.
- Depuis la landing : saisie de `example.com`, clic « Check my website » →
  navigation vers le checker puis `/scan/3244`, scan créé et complété.
- Sécurité : un autre navigateur obtient `404` sur
  `POST /public/scan/3243/email/` (le scan n'appartient pas à sa session).

## 4. Mission 3 — derniers écarts métiers

### 4.1 Approbation manuelle d'un avis

- Endpoint ajouté au client : `POST /reviews/:id/approve/`.
- Bouton « Approve » sur chaque avis non approuvé, avec état de chargement ;
  badge « Approved » après succès, rafraîchissement de la liste et des KPI.
- Vérification : avis « Test Reviewer » créé via l'API, approuvé depuis
  `/app/reviews` ; le DOM passe de `Approve` à `Approved`, et
  `GET /reviews/?approved=true` renvoie bien 1 ligne avec
  `is_approved: true`.

### 4.2 Diagnostic consolidé d'un scan

- `ScanDetails` appelle désormais `GET /scans/:id/results/` et calcule :
  score global pondéré, nombre de contrôles sains / avertissements /
  critiques, et les trois premières corrections recommandées.
- Repli automatique sur `check_results` du détail si l'agrégat échoue, avec
  un message explicite.
- Vérification sur le scan `3245` : 7 résultats, **85/100**, 6 sains,
  0 avertissement, 1 critique, « What to fix first » →
  en-têtes de sécurité.

## 5. Correctif annexe — refresh d'un compte supprimé

Découvert pendant la vérification : un refresh token encore valide dont le
compte a été supprimé (effacement RGPD, suppression admin) provoquait un
**HTTP 500** dans `POST /auth/refresh/`. SimpleJWT lève `User.DoesNotExist`
dans `validate()`, que la vue ne rattrapait pas. Le client restait bloqué avec
une session morte et une erreur serveur.

Correctif : rattraper `User.DoesNotExist` aux côtés de `TokenError` et
répondre `401` avec `{"detail": "This refresh token is invalid or expired."}`,
si bien que le client purge sa session. Test de régression :
`test_refresh_token_of_deleted_account_is_rejected`.

Vérifié sur la pile : compte créé → connexion → suppression → refresh →
**401** (au lieu de 500).

## 6. Vérifications exécutées

| Commande / contrôle | Résultat |
| --- | --- |
| `pnpm exec tsc --noEmit` | **0 erreur** |
| `pnpm run build` | **OK** (vite + prerender, 31 routes) |
| Tests backend `accounts public_checker reviews scans` | **218 tests, OK** |
| Refresh d'un compte supprimé | **401** (au lieu de 500) |
| `docker compose up -d --build frontend` | **OK**, conteneur healthy |
| `GET https://localhost/verify-email` | **200** |
| `GET https://localhost/scan/3243` | **200** |
| Parcours e-mail complet (Mailpit → lien → API → base) | **OK** (`is_email_verified: true`) |
| Scan public complet (création → Celery → rapport) | **OK** (score 85) |
| Approbation d'avis (UI → API → base) | **OK** |
| Agrégat `/scans/3245/results/` (API + DOM) | **OK** (7 lignes) |

Le bundle de production a aussi été servi sur un harnais HTTP local
(`127.0.0.1:8082`, proxy `/api` vers la pile TLS) pour l'inspecter dans un
navigateur : le certificat auto-signé de `https://localhost` n'est pas approuvé
par le navigateur de prévisualisation. Le rendu, le polling et la vérification
d'e-mail y ont été exercés avec le **même `dist/`** que celui servi par nginx.

## 7. Périmètre « 100 % » — ce qui reste, et pourquoi

Sont couverts **tous les endpoints qui portent une fonction utilisateur**,
y compris les quatre écarts de ce rapport. Restent sans écran, par conception :

| Route | Raison |
| --- | --- |
| `POST /analytics/events/track/` | télémétrie ; le trafic est déjà journalisé côté serveur |
| `GET /monitoring/` | remplacé par `/monitoring/overview/`, qui renvoie un sur-ensemble |
| `POST /subscriptions/upgrade/` | legacy volontairement fermé |
| `admin/`, `webhooks/paddle/`, `api/docs|schema|redoc`, `health/` | interne / machine |

Deux réglages restent statiques faute d'API de profil : la section
« Business » et le sélecteur de langue. Ce n'est pas un écart de parité
API ↔ UI (aucun endpoint correspondant n'existe), mais une fonctionnalité
produit à spécifier.

De même, `/report/:publicId` reste une page de démonstration explicitement
étiquetée « Preview report » : aucun endpoint ne sert de rapport partageable
par identifiant public. Le vrai rapport public est désormais `/scan/:id`,
alimenté par l'API.

## 8. Fichiers modifiés

- `src/pages/VerifyEmail.tsx` (**nouveau**)
- `src/pages/PublicScanResult.tsx` (**nouveau**)
- `src/App.tsx` — routes `/verify-email` et `/scan/:scanId`
- `src/pages/ToolPage.tsx` — scan public réel, suppression des faux résultats
- `src/pages/Landing.tsx` — le hero démarre le vrai scan
- `src/pages/Reviews.tsx` — action d'approbation
- `src/pages/Scans.tsx` — diagnostic consolidé via `/results/`
- `src/api/endpoints.ts` — `reviews.approve`
- `src/api/types.ts` — types du rapport public
- `src/pages/Settings.tsx` — type `Uint8Array<ArrayBuffer>` (tsc)
- `nginx.conf` — fallback SPA pour `/verify-email` et `/scan/`
- `backend/accounts/views.py` — refresh d'un compte supprimé → 401
- `backend/accounts/tests/test_auth_api.py` — test de régression

## 9. Notes d'exploitation

- `FRONTEND_URL` doit pointer vers l'origine publique réelle : le lien de
  vérification est construit avec cette variable. En local, il vaut
  `https://localhost`.
- Le conteneur `frontend` a été reconstruit avec ce code ; un déploiement doit
  refaire `docker compose up -d --build frontend` (nginx fait partie de
  l'image).
- Sans `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`, le push reste désactivé et
  l'UI le dit explicitement (inchangé).
