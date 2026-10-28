# Umami — dossier de préparation (non appliqué)

**Date :** 2026-10-28
**Statut :** **BROUILLON**. Aucune commande de ce document n'a été exécutée.
`VITE_ANALYTICS_ENABLED` reste `false`, aucun conteneur Umami n'existe, aucune base n'a été créée.

Ce document contient exactement ce qui sera appliqué **après confirmation explicite**. Les mesures de la section 4 proviennent de l'instance en service, en lecture seule.

---

## 1. Définition du service (à ajouter dans `docker-compose.yml`)

```yaml
  # ── Umami (mesure d'audience, désactivé tant que le juridique n'est pas prêt)
  # Aucun `ports:` : l'instance n'est joignable que par nginx sur le réseau du
  # projet. L'administration passe par un tunnel SSH vers le port 3000 du
  # conteneur, jamais par une publication d'hôte.
  umami:
    # Tag `postgresql-latest` résolu le 2026-10-28 en digest d'index multi-arch
    # (linux/amd64 + linux/arm64). Pour mettre à jour, relancer
    #   docker buildx imagetools inspect ghcr.io/umami-software/umami:postgresql-latest
    # et remplacer le digest ci-dessous — jamais le tag mouvant.
    image: ghcr.io/umami-software/umami@sha256:e69d1a7932e9dab0fc523edc7be1f3a53f3c261f57856fc2167ae74a8fc022e8
    env_file:
      - ./secrets/umami.env        # non versionné, 600, voir §3
    environment:
      DATABASE_TYPE: postgresql
      DISABLE_TELEMETRY: "1"
      TRACKER_SCRIPT_NAME: script.js
    expose:
      - "3000"
    depends_on:
      db:
        condition: service_healthy
    mem_limit: 512m
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:3000/api/heartbeat >/dev/null || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

Points de vigilance à vérifier au moment de l'activation (pas avant) :

- Image épinglée au digest d'index `sha256:e69d1a79…022e8` (tag `postgresql-latest` résolu le 2026-10-28). Une mise à jour devient un changement explicite de digest, jamais une dérive silencieuse ; `docker buildx imagetools inspect` redonne le digest courant avant toute montée de version.
- `/api/heartbeat` est le chemin exposé par les versions récentes ; à confirmer sur l'image épinglée.
- `secrets/` doit être ajouté au `.gitignore` racine **avant** la première génération du fichier.

Aucun autre service du compose n'est modifié.

---

## 2. SQL exact de création (à exécuter en superutilisateur)

```sql
-- Connexion : base `postgres`, rôle propriétaire du cluster.
-- Le mot de passe arrive par variable psql (:'umami_password'), jamais écrit ici.

CREATE ROLE umami_app LOGIN PASSWORD :'umami_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
  CONNECTION LIMIT 10;

CREATE DATABASE umami
  OWNER umami_app
  ENCODING 'UTF8'
  LC_COLLATE 'C'
  LC_CTYPE 'C'
  TEMPLATE template0;

REVOKE ALL ON DATABASE umami FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE umami TO umami_app;

\connect umami

-- Depuis PostgreSQL 15, le schéma public n'est plus inscriptible par PUBLIC.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO umami_app;

ALTER ROLE umami_app SET statement_timeout = '30s';
ALTER ROLE umami_app SET idle_in_transaction_session_timeout = '60s';
```

Pourquoi ces choix :

- `CONNECTION LIMIT 10` plafonne Umami même si son pool Prisma s'emballe : il ne peut pas affamer Django.
- Rôle `NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT` : moindre privilège, aucun accès aux autres bases.
- Base dédiée `umami`, propriétaire `umami_app` : aucune migration d'Umami ne touche `presence`.
- Aucune modification de `postgresql.conf` → **aucun redémarrage de PostgreSQL nécessaire**.

### Vérifications post-création (lecture seule)

```sql
SELECT datname FROM pg_database WHERE datname = 'umami';
SELECT rolname, rolcanlogin, rolconnlimit FROM pg_roles WHERE rolname = 'umami_app';
SELECT count(*) FROM pg_stat_activity WHERE datname = 'umami';   -- doit être 0 avant démarrage
```

---

## 3. Gestion du mot de passe

Le mot de passe n'est **jamais** écrit dans un fichier suivi par Git, ni dans `docker-compose.yml`.

```bash
# 1) Génération + fichier hors versionnement
install -d -m 700 secrets
umask 077
PW=$(openssl rand -base64 32 | tr -d '\n')
{
  printf 'DATABASE_URL=postgresql://umami_app:%s@db:5432/umami\n' "$PW"
  printf 'APP_SECRET=%s\n' "$(openssl rand -hex 32)"
} > secrets/umami.env
chmod 600 secrets/umami.env

# 2) Création du rôle sans exposer le mot de passe dans argv
printf "\\set umami_password '%s'\n" "$PW" \
  | cat - docs/analytics/umami-create.sql \
  | docker exec -i saas_web_application_digitale_presenz-db-1 \
      sh -c 'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1'

unset PW
```

- `secrets/` figure dans `.gitignore` avant la génération.
- Le mot de passe transite par stdin, pas par la ligne de commande.
- `APP_SECRET` est requis par Umami pour signer les sessions ; généré séparément.
- Sauvegarde du fichier : hors dépôt, avec les autres secrets locaux.

---

## 4. Impact mesuré sur le PostgreSQL partagé

Mesures du 2026-10-28, en lecture seule :

| Métrique | Valeur mesurée | Effet de l'ajout |
|---|---|---|
| `max_connections` | **100** | inchangé |
| `superuser_reserved_connections` | 3 | inchangé |
| Connexions actives | **11** (dont 6 sur `presence`) | +2 à +10 (plafonné par `CONNECTION LIMIT`) |
| Marge restante | **89 connexions** | ≥ 79 après Umami |
| `shared_buffers` | 128 MB | inchangé |
| Taille base `presence` | 20 MB | inchangée |
| Mémoire conteneur `db` | 57 MiB utilisés, **aucune limite** | + quelques Mo de cache |
| Mémoire hôte | 15,44 GiB, 23 GB disque libres | Umami plafonné à 512 MB |
| Volume attendu | ~1–2 Ko par page vue | ~20 Mo/an à 10 000 vues/mois |

**Aucun redémarrage de `db` n'est nécessaire** : la création d'un rôle et d'une base ne touche pas la configuration du serveur. Le risque sur le backend Django et les workers Celery se limite à la consommation de connexions, déjà plafonnée par le rôle.

### 4.1 Sauvegarde — patch à appliquer avant l'activation

**Constat.** `scripts/backup.sh` ne dumpe que `$POSTGRES_DB` (`presence`) :

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner'
```

Une base `umami` ne serait donc jamais sauvegardée, et `restore.sh` ne saurait pas la restaurer. Le patch ci-dessous rend le dump **conditionnel** : il ne s'active que si la base existe, donc il est sans effet tant qu'Umami n'est pas créé.

#### `scripts/backup.sh`

1. En-tête, après la ligne `postgres-<UTC>.dump` :

```bash
#   umami-<UTC>.dump       pg_dump de la base analytique (si elle existe)
```

2. Après `PG_FILE=` :

```bash
UMAMI_FILE="$BACKUP_DIR/umami-$STAMP.dump"
```

3. Juste après le dump de `presence` :

```bash
# La base analytique n'existe qu'après l'activation d'Umami : le dump reste
# conditionnel pour que le script fonctionne avant comme après.
if docker compose exec -T db sh -c \
    "psql -U \"\$POSTGRES_USER\" -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname = 'umami'\"" \
    | grep -qx 1; then
  echo "==> Umami → $UMAMI_FILE"
  docker compose exec -T db sh -c \
    'pg_dump -U "$POSTGRES_USER" -d umami --format=custom --no-owner' > "$UMAMI_FILE"
  [ -s "$UMAMI_FILE" ] || fail "pg_dump umami a produit un fichier vide"
fi
```

4. Empreintes — remplacer l'appel `sha256sum` fixe :

```bash
CHECKSUMMED=("postgres-$STAMP.dump" "redis-$STAMP.rdb.gz")
[ -f "$UMAMI_FILE" ] && CHECKSUMMED+=("umami-$STAMP.dump")
(cd "$BACKUP_DIR" && sha256sum "${CHECKSUMMED[@]}" > "SHA256SUMS-$STAMP")
```

5. Export S3, dans le bloc `if [ -n "${BACKUP_S3_URI:-}" ]` :

```bash
[ -f "$UMAMI_FILE" ] && aws s3 cp "$UMAMI_FILE" "$BACKUP_S3_URI/" --only-show-errors
```

6. Rétention — ajouter le motif :

```bash
\( -name 'postgres-*.dump' -o -name 'umami-*.dump' -o -name 'redis-*.rdb.gz' -o -name 'SHA256SUMS-*' \)
```

7. Récapitulatif final :

```bash
[ -f "$UMAMI_FILE" ] && ls -lh "$UMAMI_FILE"
```

#### `scripts/restore.sh`

Le cas `*.dump` devient un aiguillage sur le nom du fichier, pour ne jamais restaurer un dump analytique dans la base applicative (et inversement) :

```bash
  *.dump)
    case "$(basename "$FILE")" in
      umami-*.dump)
        echo "==> Arrêt d'Umami"
        docker compose stop umami >/dev/null 2>&1 || true
        echo "==> Restauration PostgreSQL → base analytique"
        docker compose exec -T db sh -c \
          "pg_restore -U \"\$POSTGRES_USER\" -d umami --clean --if-exists --no-owner" < "$FILE"
        docker compose start umami >/dev/null 2>&1 || true
        ;;
      *)
        echo "==> Arrêt des services applicatifs"
        docker compose stop web celery-worker celery-beat >/dev/null
        echo "==> Restauration PostgreSQL → base applicative"
        docker compose exec -T db sh -c \
          'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < "$FILE"
        docker compose start web celery-worker celery-beat >/dev/null
        ;;
    esac
    ;;
```

#### `scripts/verify_backup_restore.sh`

Le script actuel restaure dans `presence_restore_check_*` puis vérifie `accounts_user`, `websites_website`, `scans_scan` : il est spécifique à la base applicative et **ne peut pas vérifier un dump Umami tel quel**. Deux options, à trancher le jour de l'activation : un second script dédié qui compte les tables d'`umami`, ou un mode `--generic` qui se contente de `pg_restore --exit-on-error` plus un compte de tables. Le patch ci-dessus ne prétend pas couvrir ce point.

#### Contrôle après application

```bash
bash scripts/backup.sh          # doit afficher « ==> Umami → … » et lister le fichier
(cd backups && sha256sum -c SHA256SUMS-*.latest)   # le dump umami doit y figurer
```

---

## 5. Isolation : aucune autre application ne partage cette instance

| Vérification | Résultat |
|---|---|
| Ports publiés par `...-db-1` | **aucun** (`docker port` vide ; `5432/tcp` est un simple `EXPOSE`) |
| Réseau de `...-db-1` | `saas_web_application_digitale_presenz_default` uniquement |
| Conteneurs non-projet sur ce réseau | **aucun** |
| `POSTGRES_HOST` du backend | `db` (le conteneur), pas l'hôte |
| AI Platform | conteneurs `Exited` depuis 5 h ; son PostgreSQL (`ai-platform-postgres-1`) est sur `ai-platform_ai_internal`, réseau distinct |
| OmniRoute / FingptFinrobot | **aucun conteneur** de ce nom (`docker ps -a`) |
| PostgreSQL hôte | un service système écoute sur `127.0.0.1:5432` ; il n'est **pas** utilisé par Presence et ne sera pas touché |

Conclusion : Umami utilisera l'instance du conteneur `...-db-1`, isolée du PostgreSQL hôte et des autres projets. Aucun autre service actif ne partage cette instance.

---

## 6. Bloc nginx `/stats/` (même origine, aucun impact sur `/cms/` ni `?lang=`)

```nginx
    # --- Mesure d'audience (Umami), servie depuis notre propre origine ------
    # Pas de domaine tiers : pas de CSP à ouvrir, pas de blocage par les listes
    # anti-traceurs, pas de CORS. Le format de log existant ne journalise déjà
    # pas la query string.
    location = /stats/script.js {
        proxy_pass http://umami:3000/script.js;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        expires 1h;
        add_header Cache-Control "public, max-age=3600" always;
    }

    location /stats/api/ {
        proxy_pass http://umami:3000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 10s;
    }

    location /stats/ {
        return 404;
    }
```

- **Implémentation finale (2026-10-28)** : les deux `proxy_pass` passent par une upstream en variable (`set $umami_upstream`) + `rewrite`, et non par un hôte littéral — voir §9, écart 2. Aucun `expires`/`Cache-Control` n'est ajouté : Umami envoie déjà `public, max-age=86400, must-revalidate`, et deux valeurs concurrentes rendraient le cache indéterminé.
- Le préfixe exact `/stats/api/` correspond à l'endpoint déduit par le script Umami depuis son propre `src` (`/stats/script.js` → base `/stats`) ; confirmé le 2026-10-28 (`/stats/api/heartbeat` → 200 JSON).
- Le `location /stats/` final reproduit le comportement actuel de `/cms/` : tout le reste reste fermé.
- Aucune des règles `?lang=` ni des blocs `/cms/wp-json/` et `/cms/wp-content/` n'est touchée.

---

## 7. Ce qui sera exécuté, dans l'ordre, après ton feu vert

1. `secrets/` ajouté au `.gitignore` racine.
2. Génération du mot de passe + `secrets/umami.env` (600, hors Git).
3. Exécution du SQL de la section 2 (aucun redémarrage).
4. Vérifications de la section 2 (rôle, base, 0 connexion).
5. Ajout du service `umami` au compose, `docker compose up -d --no-deps umami` (le seul conteneur créé).
6. Création du site dans l'admin Umami (via tunnel SSH), récupération du `data-website-id`.
7. Bloc nginx `/stats/` + `verify-nginx.sh`.
8. Application du patch §4.1 (`backup.sh` + `restore.sh`), puis `bash scripts/backup.sh` de contrôle : le dump `umami-*.dump` doit apparaître et figurer dans `SHA256SUMS-*`.
9. **Toujours pas d'activation** : `VITE_ANALYTICS_ENABLED=false`, aucune balise dans le HTML.

L'activation du script reste une étape distincte, conditionnée à la levée des six points juridiques du plan.

---

## 8. État au moment de la rédaction (historique, avant exécution)

Au 2026-10-28, avant le feu vert : aucune base ni rôle créé, aucun conteneur
Umami, aucune ligne dans `docker-compose.yml`, aucun bloc nginx, aucun mot de
passe généré. **Ces six points ne sont plus vrais après l'exécution : voir §9.**

---

## 9. Journal d'exécution — 2026-10-28

Exécution des étapes 1 à 8 du §7, dans l'ordre, sans activation du tracking.

| Étape | Résultat |
|---|---|
| 1. `.gitignore` | `secrets/` ajouté ; `git check-ignore -v secrets/umami.env` → `.gitignore:44:secrets/` |
| 2. Secrets | `secrets/umami.env` créé en 600 (279 octets, 4 clés). Valeurs jamais affichées ni versionnées. |
| 3. SQL | Rôle `umami_app` (LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, `CONNECTION LIMIT 10`) + base `umami` ; exit 0. Aucun redémarrage de `db`. |
| 4. Contrôles | Base `umami` présente, rôle conforme, **0** connexion sur `umami` avant démarrage. |
| 5. Service | Conteneur `umami` démarré, `healthy`, port 3000 **non publié** (`3000/tcp` seul). Seul conteneur créé. |
| 6. Site admin | `data-website-id` = `cc640a0b-5955-4d5e-83b9-1b09db4a934f`. Mot de passe par défaut révoqué : `umami` → 401, mot de passe généré → 200. |
| 7. Nginx `/stats/` | `/stats/` et `/stats/<page>` → 404 ; `/stats/script.js` → 200 `application/javascript` (4 773 octets) ; `/stats/api/heartbeat` → 200 JSON. `verify-nginx.sh` exit 0. |
| 8. Sauvegarde | `backup.sh` exit 0 : `umami-20261028T125920Z.dump` (65 K) présent dans `SHA256SUMS-20261028T125920Z`, `sha256sum -c` → OK. `restore.sh` refuse une cible erronée (exit 1). |
| 9. Activation | **Non faite.** `VITE_ANALYTICS_ENABLED` absent de `.env` ; 0 occurrence de `stats/script.js` dans `/`, `/pricing`, `/en/pricing`, `/faq`, `/en/faq`. |

### Écarts par rapport au texte du brouillon

1. **Mot de passe admin.** L'endpoint supposé `POST /api/users/{id}/password` répond 404 (page HTML) sur cette version : le changement passe par `POST /api/me/password` avec `{currentPassword, newPassword}` et le jeton de session. L'ancien mot de passe est ensuite refusé (401).
2. **Bloc nginx.** Les deux `proxy_pass` utilisent une upstream en variable (`set $umami_upstream`) + `rewrite`, comme les blocs `/cms/`, au lieu d'un hôte littéral. Motif : un `proxy_pass http://umami:3000` littéral empêche nginx de démarrer si Umami est arrêté, et la résolution Docker ne serait pas rafraîchie. Les en-têtes de sécurité sont répétés dans le bloc `script.js` (un `add_header` local coupe l'héritage du bloc `server`). Aucun `Cache-Control` local n'est ajouté : celui d'Umami (`public, max-age=86400, must-revalidate`) reste seul, vérifié par `curl -I`.
3. **`restore.sh`.** La confirmation interactive affiche désormais la base cible déduite du nom de fichier et exige `RESTORE umami` / `RESTORE presence` / `RESTORE redis` : une faute de frappe sur le chemin ne peut plus écraser la mauvaise base. `--yes` reste disponible pour l'automatisation et affiche la cible.
4. **`backup.sh`.** Le récapitulatif final utilise un `if` plutôt qu'un `[ -f ] &&` : en dernière commande, un test faux faisait sortir le script en statut 1 alors que la sauvegarde avait réussi.

### Ce qui reste explicitement hors périmètre

- `VITE_ANALYTICS_ENABLED`, `src/lib/analytics.ts`, les pages juridiques et l'injection du script dans `prerender.mjs` : **inchangés**.
- `verify_backup_restore.sh` ne sait toujours pas vérifier un dump Umami (voir §4.1) : la restauration réelle d'un `umami-*.dump` n'a pas été exercée, seulement sa porte de confirmation.
- Aucun commit, aucun déploiement.

---

## 10. Activation locale de vérification — 2026-10-28 13:45–14:00 UTC

**Portée : local/développement uniquement.** Aucune configuration de production
n'a été modifiée. Les pages Datenschutz/Cookies restent des brouillons : le
blocage juridique est entier et doit être levé par un juriste avant toute mise
en ligne publique collectant des données.

### Ce qui a changé

| Fichier | Changement |
|---|---|
| `scripts/prerender.mjs` | Remplace `<!-- presence:analytics -->` par la balise Umami quand `VITE_ANALYTICS_ENABLED=true` ; refuse un id non-UUID ou une URL non same-origin ; n'injecte jamais sur les 5 écrans noindex ni sur `404.html`. |
| `scripts/check-seo-build.mjs` | Exige exactement 1 balise par page indexable (articles compris), 0 sur les pages noindex, et l'absence du marqueur brut dans tout le `dist/`. |
| `src/components/AnalyticsPageviews.tsx` | Hook `trackPageview(pathname + search)` sur les changements de route SPA ; le premier rendu est ignoré (le script compte déjà le chargement initial). |
| `src/App.tsx` | Monte le hook dans le `BrowserRouter` (jamais dans le rendu statique). |
| `docker-compose.yml` | Publie Umami sur `127.0.0.1:3000` seulement, pour le tableau de bord local. |
| `scripts/verify-nginx.sh` | Remplace l'assertion « aucun tracker » par « exactement une balise bien formée, jamais dupliquée, jamais le marqueur brut ». |

`VITE_ANALYTICS_ENABLED=true`, `VITE_ANALYTICS_WEBSITE_ID` et
`VITE_ANALYTICS_SCRIPT_URL` sont définis dans
`SaaS_Web_Application_UI_UX_frontendV2/.env.local` (non versionné,
`.gitignore:8`). Le gabarit `.env.example` reste à `false`.

### Preuves brutes

```text
dist/index.html                            1
dist/pricing/index.html                    1
dist/en/pricing/index.html                 1
dist/faq/index.html                        1
dist/login/index.html                      0
dist/_i18n/login/index.html                0
dist/404.html                              0
dist/blog/<slug>/index.html                1
marqueur brut restant dans dist/           0
sitemap <loc>                              66
```

```html
<script defer src="/stats/script.js" data-website-id="cc640a0b-…"></script>
```

```text
GET /stats/script.js → 200 application/javascript 4773 octets (via nginx)
TLS au build → [prerender] analytics enabled for this build: /stats/script.js
pnpm exec tsc --noEmit          → 0
pnpm run build                  → 0 (58 pages + 8 articles, sitemap 66)
pnpm check:seo                  → 0
pnpm exec playwright test       → 0 (50 passed, 6.6 min)
bash scripts/verify-nginx.sh    → 0 (exactly one well-formed tracker tag)
scripts/build-frontend.sh       → 0 (image reconstruite, frontend seul recréé)
```

Visite réelle (Chromium, UA desktop, certificat local ignoré) :

```text
/pricing?utm_source=local_check&utm_medium=verification → pageview enregistré
clic interne /pricing?utm_source=spa_hook_check → /   → pageview enregistré
documentLoads = 1 (aucun rechargement complet : c'est le hook SPA)
website_event : 4 lignes (dont les deux du parcours E2E)
```

Sauvegarde après activation : `backup.sh` exit 0, `umami-20261028T135634Z.dump`
(65 K) présent dans `SHA256SUMS-20261028T135634Z` à côté des dumps PostgreSQL et
Redis.

### Avertissement

`VITE_ANALYTICS_ENABLED=true` ne doit **jamais** être présent dans une
configuration de production tant que Datenschutz/Cookies ne sont pas finalisées
et validées par un juriste. Ce réglage vit uniquement dans un `.env.local`
ignoré par Git, sur ce poste.
