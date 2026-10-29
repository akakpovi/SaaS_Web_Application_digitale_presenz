# Correctif de couverture `testssl --std` — 2026-10-29

## 1. Verdict

| Point | Statut |
|---|---|
| Bug de couverture identifié et corrigé | **VALIDÉ TECHNIQUEMENT** |
| Couverture réelle (protocoles, certificat, HSTS, vulnérabilités) | **VALIDÉ TECHNIQUEMENT** |
| Budget testssl (120 s) et budget scan full (540 s) | **VALIDÉ TECHNIQUEMENT** (inchangés) |
| Tests automatisés | **VALIDÉ TECHNIQUEMENT** (72 ciblés, 169 scanners) |
| Déploiement worker | **VALIDÉ TECHNIQUEMENT** (image reconstruite, seul le worker redémarré) |
| Couverture multi-adresses IP | **À DÉCIDER PAR L'UTILISATEUR** (voir §8) |
| Commit correctif | **1888372** (voir §12) |

Aucune intégration SSLyze, aucune modification de Nikto ou gobuster, aucun changement des budgets 120 s / 540 s.

## 2. Bug localisé

Fichier : `SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/testssl.py`, lignes 302-307 dans `HEAD` avant correctif :

```python
        # ``--std`` is the bounded standard set (protocols, standard cipher
        # categories, server defaults + certificate, HSTS/security headers).
        # A full run — and even ``--fast`` — does not finish inside any
        # per-step budget on a rate-limited public target, so the step always
        # runs a scope it can actually complete rather than a run that is
        # killed mid-flight and can never prove coverage.
        return [
            self._get_binary(),
            "--std",
```

Le commentaire est faux. L'aide de testssl 3.0.8 embarqué dans `presence-scanner-tools:2026-10-27` dit exactement :

```text
     -s, --std, --standard         tests standard cipher categories by strength
     -p, --protocols               checks TLS/SSL protocols (including SPDY/HTTP2)
     -S, --server-defaults         displays the server's default picks and certificate info
     -h, --header, --headers       tests HSTS, HPKP, server/app banner, security headers, cookie, reverse proxy, IPv4 address
     -U, --vulnerable              tests all (of the following) vulnerabilities (if applicable)
```

Le même faux commentaire était répété dans `config/settings/base.py`, lignes 706-719 de `HEAD`, qui affirmait que `--std` couvrait protocoles, certificat et en-têtes, et que les sondes de vulnérabilités étaient « out of scope ».

## 3. Commande avant / après

### Avant (production)

```text
testssl --std --jsonfile-pretty <json> --quiet --nodns min --color 0 --parallel -- appchat.elomaiapp.com:443
```

Code de sortie : `0`. Durée murale mesurée : **40,54 s** (deux adresses IPv4 testées).

### Après (code livré)

```text
testssl --std --protocols --server-defaults --headers --vulnerable --ip one \
  --jsonfile-pretty <json> --quiet --nodns min --color 0 --parallel -- \
  appchat.elomaiapp.com:443
```

`--ip one` limite l'exécution à la première adresse DNS retournée. Le timeout testssl reste **120 s** et le budget global du scan reste **540 s** ; aucune valeur de budget n'a été modifiée.

## 4. Preuves JSON avant / après

### Avant — `--std` seul

Résumé du fichier `before.json` (deux adresses, `scanTime=39`) :

```text
[AVANT --std seul] scanTime=39 addresses=2
  ip=188.114.97.3 protocols=0 serverDefaults=0 headerResponse=0 vulnerabilities=0 ciphers=7
  ip=188.114.96.3 protocols=0 serverDefaults=0 headerResponse=0 vulnerabilities=0 ciphers=7
  parsed_unique_checks=9
```

Extrait brut de `before.json` :

```json
"protocols": [],
"serverDefaults": [],
"vulnerabilities": [],
```

La clé `headerResponse` est absente du document. Seuls `pretest` et `ciphers` sont peuplés. Le scan était pourtant marqué `completed` : c'est exactement le faux sentiment de couverture.

### Après — commande complète, première adresse

Résumé du fichier `ipone_load.json` (une adresse, `scanTime=99`, mesure sous charge) :

```text
[APRES --std --protocols --server-defaults --headers --vulnerable --ip one] scanTime=99 addresses=1
  ip=188.114.97.3 protocols=9 serverDefaults=36 headerResponse=12 vulnerabilities=20 ciphers=7
  parsed_unique_checks=86
```

Identifiants réellement présents :

```text
protocols: SSLv2, SSLv3, TLS1, TLS1_1, TLS1_2, TLS1_3, NPN, ALPN_HTTP2, ALPN
serverDefaults: cert, cert_commonName, cert_subjectAltName, cert_trust,
                cert_chain_of_trust, cert_expirationStatus, cert_notAfter,
                cert_keySize, cert_signatureAlgorithm, ...
headerResponse: HTTP_status_code, HSTS_time, HSTS_subdomains, HSTS_preload,
                HPKP, banner_server, cookie_count, ...
vulnerabilities: heartbleed, CCS, ticketbleed, ROBOT, secure_renego, CRIME_TLS,
                 BREACH, POODLE_SSL, fallback_SCSV, SWEET32, FREAK, DROWN,
                 LOGJAM, BEAST, LUCKY13, RC4, ...
```

### Après — chemin de code réel dans le worker déployé

Exécution de `testssl_scanner.execute("appchat.elomaiapp.com")` dans le conteneur `celery-worker` reconstruit :

```text
Starting sandboxed scanner container ... scanner=testssl mode=docker timeout_s=120
RESULT_STATUS= neutral
SCAN_COMPLETE= True
PARTIAL_REASON=
TOTAL_CHECKS= 86
HIGH_SEVERITY= 0
FINDINGS= 86
CHECK_COUNT= 86
WALL=72.91s EXIT=0
```

Parmi les 86 codes : `testssl.TLS1`, `testssl.TLS1_1`, `testssl.TLS1_2`, `testssl.TLS1_3`, `testssl.cert_expirationStatus`, `testssl.cert_subjectAltName`, `testssl.HSTS_time`, `testssl.HSTS_preload`, `testssl.heartbleed`, `testssl.POODLE_SSL`, `testssl.ROBOT`, `testssl.SWEET32`, `testssl.BEAST`, `testssl.LUCKY13`.

## 5. Temps réels mesurés

Cible : `appchat.elomaiapp.com:443` (Cloudflare, deux adresses IPv4 : `188.114.97.3`, `188.114.96.3`). Hôte : 4 vCPU, charge moyenne 5,1-5,9 au repos relatif.

| Variante | Adresses | Durée murale | Code |
|---|---:|---:|---:|
| `--std` seul (avant) | 2 | 40,54 s | 0 |
| `--std --protocols --server-defaults --headers --vulnerable` | 2 | **140,18 s** | 0 |
| idem + `--fast` | 2 | 122,18 s | 0 |
| `--protocols --server-defaults --headers --vulnerable` (sans `--std`) | 2 | 107,56 s | 0 |
| idem avec `--std`, `--ip one`, au repos | 1 | **65,28 s** | 0 |
| idem avec `--std`, `--ip one`, 4 boucles CPU | 1 | **100,14 s** | 0 |
| chemin de code complet via worker | 1 | **72,91 s** | 0 |

Décision : la variante complète sur les deux adresses dépasse le timeout de 120 s et aurait été tuée. `--fast` reste à 122 s, donc au-dessus. La variante `--ip one` conserve toutes les catégories et reste sous 120 s même sous charge (marge mesurée : 19,86 s).

## 6. Tests

### Suites ciblées

```text
$ bash scripts/run_backend_tests.sh scanners.tests.test_advanced_security scanners.tests.test_advanced_tool_adapters
Found 72 test(s).
Ran 72 tests in 3.895s
OK
PIPESTATUS=0
```

### Suite complète de l'app `scanners`

```text
$ bash scripts/run_backend_tests.sh scanners
Ran 169 tests in 7.174s
OK
PIPESTATUS=0
```

### Assertions modifiées / ajoutées

| Fichier | Ancienne assertion | Nouvelle assertion | Nature |
|---|---|---|---|
| `test_advanced_security.py` | `assertIn("--std", command)` uniquement | `--std`, `--protocols`, `--server-defaults`, `--headers`, `--vulnerable` présents, puis `--ip one` | **Renforcement** : l'ancienne assertion validait le bug (couverture cipher-only acceptée). |
| `test_advanced_tool_adapters.py` | tuple attendu `("--std", "--jsonfile-pretty", "testssl")` | tuple avec les cinq drapeaux de couverture | **Renforcement**, pas d'affaiblissement. |
| `test_advanced_tool_adapters.py` | aucun test ne vérifiait les sections du JSON | `TESTSSL_FULL_COVERAGE_JSON` : `TLS1_0`, `cert_expirationStatus`, `HSTS_time`, `heartbleed` doivent tous survivre au parseur, avec `total_checks=4` | **Nouveau test** : empêche un rapport cipher-only de repasser. |

Aucune assertion existante n'a été retirée ou affaiblie. Le test renommé `test_testssl_runs_the_bounded_standard_set` → `test_testssl_requests_every_covered_category` conserve toutes ses vérifications d'origine et en ajoute.

## 7. Déploiement worker

Reconstruction :

```text
$ docker compose build celery-worker
#18 writing image sha256:1382ac24625b7b49802a1a5b244932662a8f4e24054e5225e6d2883c14133435 done
Image saas_web_application_digitale_presenz-celery-worker Built
WALL=6.13s EXIT=0
```

Redémarrage isolé :

```text
$ docker compose up -d --no-deps celery-worker
Container ...-celery-worker-1 Recreated
Container ...-celery-worker-1 Started
exit=0
```

Comparaison des `StartedAt` de tous les conteneurs : une seule ligne diffère, `saas_web_application_digitale_presenz-celery-worker-1` (`2026-10-28T18:58:31` → `2026-10-29T05:40:27`). Aucun autre service n'a été redémarré.

Vérification dans le worker reconstruit :

```text
TIMEOUT= 120
ARGV= ['testssl', '--std', '--protocols', '--server-defaults', '--headers',
       '--vulnerable', '--ip', 'one', '--jsonfile-pretty', '/tmp/testssl.json',
       '--quiet', '--nodns', 'min', '--color', '0', '--parallel', '--',
       'appchat.elomaiapp.com:443']
```

## 8. Point à décider : couverture multi-adresses

`--ip one` teste la première adresse DNS et ignore les suivantes. C'est le compromis qui permet de garder **toutes** les catégories sous 120 s :

- deux adresses + toutes catégories = 140,18 s → tué à 120 s ;
- une adresse + toutes catégories = 65,28 s au repos, 100,14 s sous charge ;
- deux adresses sans `--std` = 107,56 s, mais perte des catégories de chiffrement ;
- deux adresses + `--fast` = 122,18 s, encore au-dessus du timeout.

Pour une cible CDN comme `appchat.elomaiapp.com`, les deux adresses sont des edges Cloudflare et la configuration TLS est identique dans les deux rapports initiaux. Ce n'est pas une garantie générale : un hôte multi-adresses peut présenter des certificats ou des protocoles différents.

**Décision laissée à l'utilisateur** : accepter cette couverture « première adresse » (statu quo du correctif), ou exiger un scan exhaustif de chaque adresse. La seconde option nécessite soit un timeout testssl > 140 s, soit l'exécution d'un conteneur testssl par adresse avec agrégation, soit une réduction d'autres postes du budget 540 s. Aucune de ces options n'a été appliquée.

## 9. Budget global

Le timeout testssl reste 120 s et `SCAN_TOTAL_TIME_BUDGET_SECONDS` reste 540 s. Le step mesuré dans le worker est de 72,91 s, inférieur au timeout de 120 s qui était déjà atteint par le scan 59 (537 s au total). Le nouveau step ne peut donc pas augmenter le pire cas du scan full par rapport au scan 59. Aucun scan full complet n'a été relancé dans ce lot : la vérification porte sur le step testssl réel et sur le chemin de code complet, pas sur les six scanners simultanément.

## 10. Limites et réserves

- `--ip one` ne couvre que la première adresse DNS ; la divergence entre adresses n'est pas détectée.
- Les mesures under load utilisent quatre boucles CPU, pas une charge applicative réelle ; la marge de 19,86 s reste à confirmer sur une charge de production soutenue.
- La cible de mesure est `appchat.elomaiapp.com` derrière Cloudflare ; les résultats de latence ne sont pas transposables à un hôte sans CDN.
- `SCANNER_TIMEOUT_TESTSSL` n'était pas défini dans le `.env` local : le worker utilisait la valeur par défaut de l'image (120 s). Le `.env.example` documentait encore 90 s ; il a été aligné sur 120 s, sans modification du budget runtime.
- Aucun scan full de bout en bout n'a été exécuté après correctif ; le budget 540 s est préservé par construction (step testssl ≤ 120 s, comme avant) mais non remesuré sur les six scanners.
- Aucune intégration SSLyze, aucun changement Nikto/gobuster, aucune modification des pages ou des autres services.

## 11. Fichiers modifiés

| Fichier | Rôle |
|---|---|
| `SaaS_Web_Application_digitale_presenz_v2/backend/scanners/implementations/testssl.py` | Ajout des quatre catégories et de `--ip one` ; commentaire corrigé. |
| `SaaS_Web_Application_digitale_presenz_v2/backend/config/settings/base.py` | Commentaire de configuration corrigé ; timeout inchangé à 120 s. |
| `SaaS_Web_Application_digitale_presenz_v2/backend/.env.example` | Documentation de couverture et budget aligné sur le runtime (120 s). |
| `SaaS_Web_Application_digitale_presenz_v2/backend/scanners/tests/test_advanced_security.py` | Assertion de couverture renforcée. |
| `SaaS_Web_Application_digitale_presenz_v2/backend/scanners/tests/test_advanced_tool_adapters.py` | Assertions de commande renforcées + test de conservation des quatre sections. |
| `docs/audits/PRESENCE_TESTSSL_STD_FIX_2026-10-29.md` | Ce rapport. |

## 12. Commit

Commit du correctif (liste blanche explicite, cinq fichiers de code/tests/config) :

```text
18883728e24e2f8c6ca0f7135d4185645159bbdb
fix(scanner): restore full testssl category coverage
```

Le présent rapport est ajouté dans un commit documentaire séparé, afin que le commit de correctif ne contienne que le correctif et ses tests. Aucun push n'a été exécuté : il n'était pas demandé par ce lot.
