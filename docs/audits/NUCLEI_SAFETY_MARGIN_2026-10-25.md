# Marge de sécurité Nuclei — rapport de mission

Date : 2026-10-25
Périmètre : `SaaS_Web_Application_digitale_presenz_v2/backend`
Cible de validation autorisée : `appchat.elomaiapp.com` (site `24`, organisation `a694ddef-a833-4d17-bc0c-44804a74180b`).
Aucun déploiement production, aucune suppression de données, aucune modification de l'intégration AKA IA.

## Statut

**Fiabilisé et vérifié en conditions réelles, avec une réduction de couverture explicite.**

Trois scans Presence successifs (`3573`, `3574`, `3575`) ont exécuté le profil `standard` complet en **84,2 s, 65,3 s et 70,6 s** (objectif ≤ 150 s, limite absolue < 180 s), avec `percent=100`, `exit=0`, 646 templates chargés, 1 300 requêtes et **0 erreur réseau**. La marge est de 66 à 85 secondes.

La contrepartie est assumée : le profil `standard` ne couvre plus les sévérités `medium` (421 templates). Cette couverture reste disponible dans le profil `thorough`, désactivé par défaut. Aucun scan ne peut résoudre un constat hors de sa couverture : `resolve_missing=False` pour `standard` et `thorough`.

## 1. Audit initial et budgets réellement appliqués

### Configuration avant correction

| Élément | Valeur constatée |
|---|---|
| Profil Nuclei | `standard` |
| Templates sélectionnés | `exposure`, `misconfig`, sévérités `critical,high,medium` |
| Budget du profil | 170 s |
| Budget legacy `SCANNER_CONFIG["nuclei"]["timeout"]` | 170 s |
| Budget effectivement transmis au sandbox | **170 s** (le budget legacy, pas le profil) |
| Plafond sandbox | 300 s |
| Budget global du scan | 540 s |
| Celery | `time_limit=600`, `soft_time_limit=570` |
| Alerte de durée | inexistante |

Le défaut structurel était dans `ScanOrchestrator._effective_timeout()` : il lisait `SCANNER_CONFIG[nom]["timeout"]` et ignorait le budget du profil Nuclei. Modifier seulement `profiles.standard.timeout` n'aurait donc eu aucun effet sur le processus : le sandbox aurait continué à recevoir 170 s.

### Budgets après correction

| Profil | Budget profil | Budget orchestrateur | Budget sandbox effectif | Alerte | Plafond absolu |
|---|---:|---:|---:|---:|---:|
| `standard` | **150 s** | **150 s** | **150 s** | 150 s | < 180 s |
| `thorough` | **178 s** | **178 s** | **178 s** | 150 s | < 180 s |
| `deep` | 540 s (déclaré) | 300 s (plafonné) | 300 s | 540 s | dépend du worker |

Hiérarchie du profil standard : `150 s (Nuclei/sandbox/orchestrateur) < 540 s (scan total) < 570 s (soft Celery) < 600 s (hard Celery)`.

`deep` reste volontairement hors du chemin automatique : son budget de 540 s est plafonné par `SCANNER_SANDBOX_MAX_TIMEOUT=300`. Il faudrait élever ce plafond et le budget total, sur un worker dédié, avant de le considérer opérationnel.

## 2. Changements

### Profils

- **`standard`** : `critical,high` uniquement, tags `exposure,misconfig`, 20 workers, 60 req/s, timeout par requête 5 s, retries 1, `max-host-error=40`, budget 150 s, `resolve_missing=False`.
- **`thorough`** : même périmètre que l'ancien standard (`critical,high,medium`, 1 066 templates), 15 workers, 45 req/s, budget 178 s, `resolve_missing=False`. Il n'est jamais planifié par défaut.
- **`deep`** : ajoute la sélection complète du tag `cve` (y compris les CVE qui ne portent pas `exposure`/`misconfig`), budget déclaré 540 s, plafonné à 300 s par le sandbox actuel.

Le profil standard contient malgré tout **132 templates CVE** qui portent aussi les tags `exposure`/`misconfig` et sont de sévérité haute ou critique. La documentation ne doit pas dire « standard sans CVE » : elle doit dire « standard sans la sélection CVE complète ».

### Application effective du budget

`NucleiScanner` expose maintenant `profile_timeout` et `duration_alert_s`. `_effective_timeout()` utilise `profile_timeout` lorsqu'il s'agit d'un entier réel, puis applique le plafond sandbox et le budget restant. Un avertissement est journalisé si le budget du profil dépasse le plafond sandbox.

`ScannerRun.metadata` conserve désormais :

- `profile_timeout_s` ;
- `duration_alert_s` ;
- `duration_over_alert` ;
- `profile`, `templates_loaded`, `percent`, `requests`, `errors`, `host_skipped`, `scan_complete`, `partial_reason`, `exit_code`.

### Intégrité du statut

Un timeout ou un scan partiel n'est plus présenté comme une étape `completed` :

- `ScannerRun.status = timeout|partial` ;
- `Scan.steps[nuclei].status = timeout|partial` ;
- `step.error` porte la raison (`timeout`, `host_unresponsive`, `exit_code`, etc.) ;
- `compute_overall_progress()` traite `partial` comme un état terminal ;
- un scan incomplet force `resolve_missing=False` et ne ferme aucun constat.

## 3. Mesures réelles

Toutes les mesures ci-dessous utilisent la cible autorisée, le worker Celery réel et le sandbox Docker `presence_scanner_sandbox`.

| Scan | Durée Nuclei | Templates chargés | Requêtes / erreurs | Exit | Complétude | Constats | Scan Presence total |
|---|---:|---:|---:|---:|---|---:|---:|
| `3573` | **84,166 s** | 646 | 1 300 / 0 | 0 | `percent=100`, complet | 0 | 181,4 s (ZAP inclus) |
| `3574` | **65,326 s** | 646 | 1 300 / 0 | 0 | `percent=100`, complet | 0 | 151,2 s (ZAP inclus) |
| `3575` | **70,632 s** | 646 | 1 300 / 0 | 0 | `percent=100`, complet | 0 | 164,9 s (ZAP inclus) |

Les trois `ScannerRun` sont `completed`, avec `timeout_s=150`, `profile_timeout_s=150`, `duration_alert_s=150`, `duration_over_alert=False`, `host_skipped=False`, `scan_complete=True`.

La durée totale du scan Presence inclut ZAP (environ 70–97 s) et les scanners internes ; l'objectif de 150 s porte sur le processus Nuclei, pas sur l'orchestration complète.

### Comparaison avec l'ancien profil

| Configuration | Templates | Requêtes | Erreurs | Durée observée |
|---|---:|---:|---:|---:|
| Ancien standard `medium+`, 20/60 | 1 066 | 3 334 | 1 958–2 371 | 129,6–169,0 s |
| Nouveau standard `high+critical`, 20/60 | 646 | 1 300 | 0 | **65,3–84,2 s** |
| `thorough` `medium+`, 15/45 (mesure directe) | 1 066 | 3 334 | 1 794 | 127 s |

Le passage de 20/60 à 30/90 sur l'ancien profil a provoqué un `Skipped host: port closed or filtered` après 48 requêtes : l'augmentation du débit n'est pas une voie sûre sur cette cible. La réduction du débit à 15/45 améliore l'ancien profil (127 s au lieu de 129–169 s) mais conserve une marge trop faible pour le standard automatique.

### Ressources observées

Échantillon pendant le scan `3574` :

- conteneur Nuclei : **803,9 MiB / 1,5 GiB (52,3 %)**, CPU **23,6 %** ;
- conteneur ZAP : **256,7 MiB**, CPU **102,3 %** (limite 1 CPU).

Ces valeurs sont des mesures ponctuelles, pas un pic continu. Les limites appliquées restent 1 CPU et 1 536 Mo pour Nuclei.

## 4. Couverture : perdue et préservée

L'ancien profil chargeait 1 066 templates. Le nouveau standard en charge 646.

| Catégorie de répertoire | Standard high/critical | Medium retiré du standard |
|---|---:|---:|
| `http/misconfiguration` | 367 | 166 |
| `http/cves` | 132 | 92 |
| `http/exposures` | 99 | 134 |
| `http/vulnerabilities` | 40 | 18 |
| `http/exposed-panels` | 3 | 9 |
| `http/iot` | 4 | 2 |
| `http/cnvd` | 1 | 0 |
| **Total** | **646** | **421** |

Les 421 templates medium restent disponibles dans `thorough`. Aucune exclusion globale de `sqli`, `xss`, `injection`, `cve` ou `misconfig` n'a été ajoutée. Comme le profil est piloté par les tags positifs `exposure` et `misconfig`, les templates qui ne portent que `sqli`/`xss` ne sont pas sélectionnés ; cette limite existait déjà et interdit la résolution hors couverture.

Les templates DoS, fuzzing, intrusifs, brute-force, default-login, credential-stuffing et token-spray restent exclus des trois profils.

## 5. Timeout contrôlé et intégrité

Un timeout forcé de 20 s a été exécuté directement via l'adaptateur, avec la cible validée et le sandbox réel :

```text
status=warning duration_ms=20388
scan_complete=False
timed_out=True
partial_reason=timeout
exit_code=137
findings=['nuclei.timeout']
```

Aucun conteneur `presence-scan-*` ne subsiste après l'essai (`docker ps -aq --filter name=presence-scan` → 0). Le scan est classé `timeout`, jamais `completed`.

### Absence de résolution abusive en conditions réelles

Après les trois scans standard :

- les logs d'ingestion Nuclei indiquent `received=0 created=0 updated=0 resolved=0 resolve_missing=False` ;
- un constat Nuclei existant (`4c45ddaf-17f0-490a-991d-3355f79fe82e`, « HTTP Missing Security Headers ») est toujours `open` avec `resolved_at=None` ;
- ZAP a mis à jour ses 12 constats (`updated=12`) sans en résoudre (`resolved=0`).

Le profil standard complet ne peut donc pas fermer un constat medium/CVE hors de sa couverture, même quand il ne détecte rien.

## 6. Tests exécutés

| Commande | Résultat |
|---|---|
| `scanners.tests.test_advanced_security scans.tests.test_orchestrator_delegation` | **48 tests, OK**, 17,8 s |
| `scanners advisory.tests.test_scan_ingestion` | **126 tests, OK**, 26,6 s |
| `monitoring scans.tests.test_scans` | **87 tests, OK**, 94,9 s |
| `manage.py check` (code monté, settings de test) | Aucun problème |
| `manage.py makemigrations --check --dry-run` | Aucun changement détecté |
| `python -m compileall scans scanners config/settings/base.py` | OK |

Les tests ajoutés couvrent :

- budget standard 150 s et sévérité `critical,high` ;
- profil `thorough` 178 s et conservation de `medium` ;
- priorité du `profile_timeout` sur le timeout legacy ;
- plafonnement par le sandbox et par le budget restant ;
- seuil d'alerte 150 s ;
- statut d'étape `timeout`/`partial` et progression terminale ;
- absence de résolution sur scan partiel (tests d'ingestion existants).

## 7. Fichiers modifiés

| Fichier | Nature |
|---|---|
| `backend/config/settings/base.py` | Profils `standard` 150 s high/critical, `thorough` 178 s medium+, débit 15/45, budgets et alertes |
| `backend/scanners/implementations/nuclei.py` | `profile_timeout`, `duration_alert_s`, journal d'alerte, métadonnées de budget |
| `backend/scans/services/orchestrator.py` | Prise en compte du budget de profil, avertissement de plafonnement, statuts d'étape partiel/timeout |
| `backend/scans/services/steps_builder.py` | État terminal `partial` dans la progression |
| `backend/.env.example` | Documentation des profils et des budgets |
| `backend/scanners/tests/test_advanced_security.py` | Tests de profils, budgets, seuil et commande CLI |
| `backend/scans/tests/test_orchestrator_delegation.py` | Tests de budget effectif et de statuts partiel/timeout |
| `backend/scans/tests/test_scanner_engine.py` | Test de progression d'une étape `partial` |

Aucun modèle, aucune migration et aucune route API n'ont été modifiés.

## 8. Risques et limites restantes

1. **Couverture medium retirée du standard** : 421 templates, dont 166 misconfigurations, 134 exposures et 92 CVE medium. `thorough` les couvre mais doit être planifié explicitement.
2. **`deep` n'est pas opérationnel avec la configuration actuelle** : son budget de 540 s est plafonné à 300 s par `SCANNER_SANDBOX_MAX_TIMEOUT`. Il exige un worker dédié, un plafond et un budget total relevés.
3. **Cible sensible au débit** : 30/90 a provoqué un host skip après 48 requêtes. Le standard reste à 20/60 ; `thorough` à 15/45.
4. **Marge du `thorough` plus faible** : 127 s mesurés, budget 178 s, seuil d'alerte 150 s. Un run lent peut être partiel ; le statut est explicite et ne résout rien.
5. **Pas de rapport brut complet archivé** : seuls les constats normalisés et les compteurs sont conservés. Le diagnostic d'un timeout repose sur stderr tronqué et les métadonnées.
6. **ZAP reste instable sur cette cible** (`failed to access target`, exit 3 sur certains runs). Il est hors périmètre et n'empêche pas Nuclei de fonctionner ; l'ingestion ZAP est ignorée proprement.
7. **Mesures de ressources ponctuelles** : le pic CPU/RAM n'a pas été échantillonné en continu.

## 9. Recommandation finale

Pour Presence :

1. **Garder `standard` en `critical,high` avec 150 s** pour les scans automatiques : trois runs réels complets entre 65 et 85 s, sans erreur, avec une marge de 66 à 85 s.
2. **Planifier `thorough` séparément** (manuel ou fenêtre dédiée) pour conserver la couverture medium. Ne pas le remettre par défaut tant que sa marge n'est pas mesurée sur plusieurs runs.
3. **Ne pas activer `deep`** avant d'avoir un worker dédié, `SCANNER_SANDBOX_MAX_TIMEOUT > 540`, `SCAN_TOTAL_TIME_BUDGET_SECONDS > 540` et une validation réelle.
4. **Surveiller `duration_alert_s=150`** : tout run standard qui atteint 150 s est un timeout partiel, jamais un succès. Les métadonnées `ScannerRun` permettent de l'auditer.
5. **Conserver `resolve_missing=False`** pour standard et thorough : la couverture réduite interdit toute fermeture automatique de constats hors périmètre.

La mission est **fiabilisée et vérifiée en conditions réelles** pour le profil standard, avec la réduction de couverture medium explicitement documentée et compensée par le profil `thorough`.
