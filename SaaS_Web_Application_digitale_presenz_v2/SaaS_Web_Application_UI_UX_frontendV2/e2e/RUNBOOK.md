# Runbook E2E — diagnostic d'un échec Playwright en CI

Ce runbook couvre le job `E2E Tests (i18n)` du workflow
`.github/workflows/ci.yml`. Il ne contient volontairement aucun identifiant :
`E2E_EMAIL`, `E2E_PASSWORD` et `E2E_WEBSITE_ID` sont lus depuis les secrets
GitHub ou depuis l'environnement local. Ne jamais coller ces valeurs dans une
issue, un log, un fichier suivi ou une commande enregistrée dans l'historique.

## 1. Localiser l'échec

1. Ouvrir GitHub → Actions → le run concerné → job **E2E Tests (i18n)**.
2. Vérifier les étapes dans cet ordre :
   - `Create CI environment file`
   - `Create Umami env placeholder`
   - `Prepare local TLS for nginx`
   - `Start local stack`
   - `Wait for API through nginx`
   - `Seed E2E test data`
   - `Run French i18n E2E`
3. Chercher les lignes `✘`, `Error:` et `TimeoutError` de Playwright. Noter le
   nom exact du test et la ligne du fichier `e2e/i18n-french.spec.ts`.
4. Télécharger le log complet :

```bash
gh run list --repo akakpovi/SaaS_Web_Application_digitale_presenz \
  --workflow ci.yml --limit 5
gh run view --job <job-id> \
  --repo akakpovi/SaaS_Web_Application_digitale_presenz --log
```

Les tests privés sont les seuls à dépendre du seed :

| Test | Dépendance |
| --- | --- |
| `French public pages and login use the French catalogue` | Stack + compte QA pour la connexion |
| `French private screens › dashboard and navigation are translated` | Compte QA |
| `French private screens › website list and detail keep their French actions` | Compte QA + `E2E_WEBSITE_ID` |
| `French private screens › settings sections and privacy copy are French` | Compte QA + abonnement |

Si les secrets sont absents, les tests privés sont explicitement ignorés ;
le test public reste exécuté. Un job vert avec des `skipped` n'est donc pas
une validation des écrans privés.

## 2. Lire le seed

L'étape `Seed E2E test data` doit être `success` **avant** Playwright. Sa
sortie attendue est de la forme :

```text
seed-e2e: plan free created
seed-e2e: user created id=...
seed-e2e: website created id=...
seed-e2e: subscription reused tier=free
E2E_WEBSITE_ID=...
```

`created` et `reused` sont tous deux normaux : le seed est idempotent. Le
plan Free est créé avant le compte pour que le signal `post_save` puisse
attacher un abonnement. Le mot de passe n'est jamais affiché.

Sur un compte QA local qui possède déjà une offre interne, le tier affiché
peut être `qa` : le seed ne remplace jamais un abonnement existant. En CI, le
compte neuf reçoit `free`.

Si le log contient encore `Free plan not found — subscription not created`,
le seed n'a pas créé le plan : vérifier que l'étape de seed est bien celle du
commit courant et que la migration `subscriptions` a été appliquée. Ne pas
contourner le problème en créant un abonnement à la main dans un environnement
partagé.

## 3. Classifier la panne

| Symptôme | Cause probable | Action |
| --- | --- | --- |
| `TimeoutError: page.waitForURL` après le login | Identifiants QA absents ou différents du seed | Vérifier `Seed E2E test data`, puis les secrets `E2E_EMAIL` et `E2E_PASSWORD` |
| `net::ERR_CONNECTION_REFUSED` | Stack ou API non démarrée | Vérifier `Start local stack` et `Wait for API through nginx` |
| `net::ERR_CERT_AUTHORITY_INVALID` | Certificat local absent | Vérifier `Prepare local TLS for nginx` |
| `expect(text).not.toContain('English')` échoue | Régression de traduction | Identifier le fichier i18n modifié dans le PR et relancer le test seul |
| Un texte ou un score métier a changé | Changement fonctionnel non aligné avec le test | Vérifier le diff backend/frontend ; ne pas modifier le test pour masquer une régression |
| `env file ... not found` | Fichier d'environnement CI manquant | Vérifier `Create CI environment file` et `Create Umami env placeholder` |
| `No tests found` ou tous les tests `skipped` | Mauvais répertoire, filtre `-g` ou secrets absents | Relancer depuis le répertoire frontend et vérifier `gh secret list` |
| `IntegrityError` sur le site | `E2E_WEBSITE_ID` appartient à un autre compte | En CI, choisir un ID libre dans le secret ; en local, ne jamais réutiliser le site d'un autre utilisateur |
| `ModuleNotFoundError: No module named 'config'` | Script lancé hors du conteneur | Utiliser `docker compose exec -T web python scripts/seed_e2e.py` depuis la racine |
| `Executable doesn't exist` | Chromium non installé | `pnpm exec playwright install chromium` |
| `Docker Build` échoue | Image ou dépendance backend/frontend | Lire le premier build error, pas seulement la dernière ligne |

## 4. Reproduire localement

Depuis la racine du dépôt, charger les valeurs dans le shell sans les écrire
dans un fichier suivi :

```bash
read -r -p 'E2E_EMAIL: ' E2E_EMAIL
read -r -s -p 'E2E_PASSWORD: ' E2E_PASSWORD; echo
read -r -p 'E2E_WEBSITE_ID (optionnel): ' E2E_WEBSITE_ID
export E2E_EMAIL E2E_PASSWORD E2E_WEBSITE_ID
```

Démarrer la stack et seeder :

```bash
docker compose up -d
docker compose exec -T \
  -e E2E_EMAIL="$E2E_EMAIL" \
  -e E2E_PASSWORD="$E2E_PASSWORD" \
  -e E2E_WEBSITE_ID="$E2E_WEBSITE_ID" \
  web python scripts/seed_e2e.py
```

Relancer le test fautif, puis la suite i18n complète :

```bash
cd SaaS_Web_Application_digitale_presenz_v2/SaaS_Web_Application_UI_UX_frontendV2
E2E_EMAIL="$E2E_EMAIL" \
E2E_PASSWORD="$E2E_PASSWORD" \
E2E_WEBSITE_ID="$E2E_WEBSITE_ID" \
  pnpm exec playwright test e2e/i18n-french.spec.ts \
  -g "dashboard and navigation are translated" --headed

E2E_EMAIL="$E2E_EMAIL" \
E2E_PASSWORD="$E2E_PASSWORD" \
E2E_WEBSITE_ID="$E2E_WEBSITE_ID" \
  pnpm exec playwright test e2e/i18n-french.spec.ts --reporter=list
```

Les traces et captures locales sont écrites dans `test-results/` (ignoré par
Git). La CI ne publie pas d'artefact Playwright : le log du job est la source
principale pour un échec distant.

## 5. Vérifier les secrets CI

```bash
gh secret list --repo akakpovi/SaaS_Web_Application_digitale_presenz \
  | grep -E '^E2E_'
```

Si un secret manque, le définir avec l'invite interactive de `gh` (ne pas
passer la valeur en argument, elle resterait dans l'historique) :

```bash
gh secret set E2E_EMAIL --repo akakpovi/SaaS_Web_Application_digitale_presenz
gh secret set E2E_PASSWORD --repo akakpovi/SaaS_Web_Application_digitale_presenz
gh secret set E2E_WEBSITE_ID --repo akakpovi/SaaS_Web_Application_digitale_presenz
```

## 6. Corriger et vérifier

1. Corriger la cause dans le code ou les données de seed, pas le test.
2. Relancer le test local, puis la suite i18n complète.
3. Vérifier `ruff check` et les tests backend concernés.
4. Committer et pousser ; le job E2E est bloquant, donc un échec doit être
   corrigé avant de considérer le run comme vert.
5. Déclencher un `workflow_dispatch` si nécessaire et suivre le run :

```bash
gh workflow run ci.yml \
  --repo akakpovi/SaaS_Web_Application_digitale_presenz --ref main
gh run watch --repo akakpovi/SaaS_Web_Application_digitale_presenz
```

## Contacts et références

- Mainteneur CI : `@akakpovi`
- Documentation E2E : [`README.md`](./README.md)
- Script de seed : `SaaS_Web_Application_digitale_presenz_v2/backend/scripts/seed_e2e.py`
- Workflow : `.github/workflows/ci.yml`