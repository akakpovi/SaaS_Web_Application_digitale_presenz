# Rapport d'exécution — Itération 2 (P0-06 Production/TLS + P0-07 SSRF)

Date : 2026-10-14
Périmètre : configuration de production + fermeture des derniers vecteurs SSRF.
Dépôt : `~/Schreibtisch/SaaS_Web_Application_digitale_presenz` (branche `main`).

---

## 1. Mission 1 — P0-06 : Production et TLS

### 1.1 `.env` (`SaaS_Web_Application_digitale_presenz_v2/backend/.env`)

Forcé en production (les valeurs secrètes n'ont pas été modifiées ni affichées) :

| Variable | Valeur |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,web` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://localhost,https://127.0.0.1` |
| `CORS_ALLOWED_ORIGINS` | `https://localhost,https://127.0.0.1` (ajouté) |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` |
| `DJANGO_SESSION_COOKIE_SECURE` | `true` |
| `DJANGO_CSRF_COOKIE_SECURE` | `true` |

> Note : le code lit les noms préfixés `DJANGO_*` (`env_bool("DJANGO_DEBUG")`, …). Les noms demandés
> (`DEBUG`, `SECURE_SSL_REDIRECT`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`) ont donc été écrits avec le
> préfixe attendu par le projet. `ALLOWED_HOSTS`/`CORS` sont, eux, sans préfixe.

### 1.2 `config/settings/production.py`

Aucune modification nécessaire : le fichier satisfaisait déjà **toutes** les exigences (vérifié
par introspection des réglages actifs). Valeurs effectives constatées dans le conteneur :

```
SETTINGS_MODULE=config.settings.production   DEBUG=False
SECURE_SSL_REDIRECT=True                     SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True                      SECURE_HSTS_SECONDS=31536000
X_FRAME_OPTIONS=DENY                         SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_HSTS_INCLUDE_SUBDOMAINS=True          SECURE_HSTS_PRELOAD=True
SECURE_REFERRER_POLICY=same-origin           SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
```

### 1.3 Nginx (terminaison TLS)

**Décision d'architecture** : la pile canonique (`docker-compose.yml` à la racine) n'a **pas** de
service `nginx` dédié — le point d'entrée est le service **`frontend`** (conteneur nginx qui sert la
SPA et proxifie `/api/`). Le fichier
`SaaS_..._v2/SaaS_Web_Application_UI_UX_frontendV2/nginx.conf` est copié dans l'image vers
`/etc/nginx/conf.d/default.conf`. C'est donc **ce fichier** qui a été modifié (plutôt que de
ressusciter la pile backend dépréciée) :

- **80** : `return 301 https://$host$request_uri` (redirection stricte) ;
- **443** : `listen 443 ssl; http2 on;` avec `ssl_certificate /etc/nginx/ssl/presence.crt` et
  `ssl_certificate_key /etc/nginx/ssl/presence.key` (TLS 1.2/1.3) ;
- en-têtes ajoutés sur le serveur **et** re-déclarés sur `location /assets/` (nginx n'hérite pas les
  `add_header` du `server` si le `location` en définit un) :
  `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`,
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` ;
- proxy `/api/` et SPA (`try_files`) conservés.

### 1.4 `docker-compose.yml` (racine)

- service `frontend` : expose désormais `80:80` **et** `443:443` ;
- volume `./nginx/ssl:/etc/nginx/ssl:ro` (lecture seule) ;
- healthcheck frontend passé en HTTPS (`wget --no-check-certificate -qO- https://127.0.0.1/`) ;
- healthcheck `web` : ajout de l'en-tête `X-Forwarded-Proto: https` (sans quoi
  `SECURE_SSL_REDIRECT=True` renvoie un 301 au healthcheck interne et rend `web` *unhealthy*).

### 1.5 Module de test dédié — `config/settings/test.py` (nouveau)

`SECURE_SSL_REDIRECT=True` couplé aux cookies *secure-only* transforme chaque requête du client de
test Django en 301 et casse la suite. `scripts/run_backend_tests.sh` force donc désormais
`DJANGO_SETTINGS_MODULE=config.settings.test`, module qui hérite de `production` et ne relâche que
`SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`. La
production elle-même est validée par `check --deploy`.

### 1.6 Script de configuration TLS — `scripts/setup_local_tls.sh` (nouveau)

Génère un certificat auto-signé `nginx/ssl/presence.{crt,key}` (CN=localhost,
SAN `DNS:localhost, IP:127.0.0.1`, RSA 2048, 825 j). `nginx/ssl/` est ajouté au `.gitignore`
(jamais versionné).

---

## 2. Mission 2 — P0-07 : vecteurs SSRF restants

### 2.1 `advanced_security/scanners/port_scanner.py`

`socket.gethostbyname(domain)` supprimé. Le scanner appelle désormais `resolve_public_ip(domain)`
depuis `core.security`, qui applique `validate_domain_for_scan` **puis** résout le nom et refuse
toute adresse non globalement routable (loopback, privée, link-local, metadata). Les exceptions
`DomainValidationError` / `SSRFBlockedError` (et `socket.gaierror`) sont capturées → le scan renvoie
`[]` au lieu de contacter une cible interne.

### 2.2 `notifications/providers.py`

`WebhookProvider.send` (donc `DiscordProvider` par héritage) et `SlackProvider.send` n'utilisent plus
`requests.post` : ils passent par `core.security.safe_webhook_request`, qui valide l'URL (schéma
HTTP/HTTPS, ports 80/443, pas d'identifiants ni de fragment), rejette les hôtes internes/metadata,
résout et épingle l'IP publique avant connexion. `DomainValidationError` → webhook bloqué et
journalisé, retour `False`.

**Écart assumé** : `safe_request` **ne pouvait pas** être utilisée telle quelle — elle est
volontairement limitée à `GET`/`HEAD` (`ALLOWED_METHODS`) et un test dédié
(`test_safe_request_rejects_post_method`) verrouille ce contrat. Une variante `safe_webhook_request`
(POST + corps JSON) a donc été ajoutée à `core.security.py`, réutilisant **le même** pipeline de
validation et de *DNS pinning*. `resolve_public_ip` (helper public) a également été ajouté.
`_do_request` accepte désormais un paramètre `body` (transmis aussi lors des redirections).

---

## 3. Mission 3 — Validation (script `scripts/run_iteration2_validation.sh`)

Script consolidé (certificat → rebuild/up → `check --deploy` → tests → smoke-test SSRF), exécuté de
bout en bout : **exit 0**.

| Étape | Commande | Résultat |
|---|---|---|
| 1 | `bash scripts/setup_local_tls.sh` | certificat présent, CN=localhost, SAN OK |
| 2 | `docker compose build && docker compose up -d` | pile saine (web, frontend, db, redis) |
| 3a | `manage.py check --deploy --tag security` | **System check identified no issues (0 silenced)** |
| 3b | `manage.py check --deploy` filtré sur `security.W` | **0 avertissement `security.W*`** |
| 4 | `bash scripts/run_backend_tests.sh` | **Ran 326 tests in 619.268s — OK** (0 échec) |
| 5 | smoke-test SSRF (8 assertions) | **8/8 PASS** |

Vérifications TLS/headers en direct :

```
HTTP  (80)  /api/v1/health/  →  301  https://localhost/api/v1/health/
HTTPS (443) /api/v1/health/  →  200
strict-transport-security: max-age=31536000; includeSubDomains; preload
x-frame-options: DENY
x-content-type-options: nosniff
referrer-policy: same-origin
```

Smoke-test SSRF (conteneur `web`, contexte Django réel) :

```
PASS  validate_domain_for_scan('127.0.0.1')
PASS  validate_domain_for_scan('foo.internal')
PASS  resolve_public_ip('127.0.0.1')
PASS  resolve_public_ip('169.254.169.254')
PASS  safe_webhook_request('http://127.0.0.1/hook')
PASS  safe_webhook_request('http://metadata.google.internal/')
PASS  scan_sensitive_ports('127.0.0.1') == []
PASS  scan_sensitive_ports('localhost') == []
```

---

## 4. Réserve à lever / limites

- `manage.py check --deploy` remonte **~48 avertissements `drf_spectacular.W001/W002`** (schéma
  OpenAPI : `serializer_class` non deviné sur des `APIView`, collisions d'`operationId`, enums
  dupliqués). Ils sont **hors sécurité** (`security.W*` = 0) et **préexistants**. À traiter dans une
  itération dédiée si un `check` parfaitement silencieux est souhaité.
- Le certificat est **auto-signé** : à usage local uniquement. En production réelle, remplacer par un
  certificat ACME/Let's Encrypt ou fourni par l'hébergeur (le montage `/etc/nginx/ssl:ro` est
  inchangé).
- `safe_webhook_request` restreint les webhooks aux ports **80/443** : les webhooks sur port non
  standard (ex. `:8080`) sont refusés par conception (choix sécurité).
- Le hello de `reviews/services/sync.py` (`safe_request("GET", url, timeout=10)`) appelle la fonction
  avec une signature erronée — bug préexistant, hors périmètre de cette itération.
- Aucun artefact de test ou secret laissé en suspens : backup `.env` intermédiaire supprimé, aucune
  base `test_*`/scratch résiduelle, `nginx/ssl/` ignoré par git.

---

## 5. Livrable — confirmation

1. **`manage.py check --deploy` : aucun avertissement de sécurité `security.W*`** → confirmé
   (`--tag security` : « no issues »).
2. **Suite de tests : 100 % au vert** → confirmé, **326 tests, OK**.
3. **Aucun code sensible ou artefact de test laissé en suspens** → confirmé.
