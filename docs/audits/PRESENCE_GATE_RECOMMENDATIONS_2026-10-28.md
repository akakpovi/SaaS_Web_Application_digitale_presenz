# Presence — Lot §9 « Recommandations avant gel » — 2026-10-28

Périmètre : les quatre recommandations du §9 de
`PRESENCE_SCAN_PIPELINE_FIXES_2026-10-28.md`, traitées séparément, avec
preuves d'exécution réelles. Aucun commit, push ou déploiement distant n'a été
fait avant la clôture de ce rapport.

Compte utilisé pour les scans réels : `qa-admin@presence.local` (plan QA
Interne, 100 000 scans/mois, 1 000 sites). Les comptes de plan Free/Pro/
Business/Agency n'ont pas été consommés.

---

## Verdict de gel

**Le pipeline n'est pas encore qualifiable « prêt pour gel ».** Les deux
correctifs de robustesse (alerte IA et métriques) sont validés, et la détection
soft-404 est validée en laboratoire. En revanche, le scan `full` réel reste
`partial` : testssl.sh est encore tué à 120 s, nikto atteint sa `maxtime`, et
gobuster son budget de 45 s. Le scan a consommé 537 s sur un budget total de
540 s : augmenter un timeout sans réduire un autre budget ne ferait que déplacer
la coupe. C'est une décision de produit/architecture, pas un correctif mécanique.

| Sous-point | Statut |
|---|---|
| 1.1 Budgets testssl / nikto | **ÉCHEC** sur le critère « scan full completed » (mesures et ajustement appliqués, mais testssl reste en timeout) |
| 1.2 Détection soft-404 gobuster | **VALIDÉ TECHNIQUEMENT** en laboratoire (2 cibles réelles) ; réserve : gobuster reste en timeout sur la cible appchat |
| 1.3 Alerte opérateur sur run IA reapé | **VALIDÉ TECHNIQUEMENT** |
| 1.4 Métriques de reap | **VALIDÉ TECHNIQUEMENT** |

---

## 1.1 — Budgets testssl / nikto

### Mesures réelles avant ajustement

Commande testssl.sh bornée (`--std`, celle de l'adaptateur) dans l'image
`presence-scanner-tools:2026-10-27`, sur `appchat.elomaiapp.com:443` :

- hôte au repos : **36 s** ;
- avec quatre burners CPU saturant la machine : **94 s**.

Nikto, avec `-maxtime 85s` : **88 s**, termine sur
`Host maximum execution time ... reached`. Avec `-maxtime 150s` : **154 s**,
même message de troncature. La catalogue complet ne rentre donc pas dans le
budget global de 540 s.

### Changement appliqué

`backend/config/settings/base.py` :

- `SCANNER_TIMEOUT_TESTSSL` : `90` → `120` s ;
- `SCANNER_TESTSSL_CPU_SECONDS` : `120` → `150` s (marge du sandbox au-dessus
  du timeout mur) ;
- nikto conservé à `100` s (`maxtime 85 s`) : l'allonger ne produit qu'une
  troncature plus tardive, déjà mesurée.

Le commentaire du code indique explicitement que 120 s ne garantit pas la
complétude sur cette cible, et qu'un passage à 180 s dépasserait le budget
global.

### Scan full réel après ajustement

Scan **59**, site QA 38 (`appchat.elomaiapp.com`), type `full` :

```text
SCAN 59 status=partial type=full duration=537
started=2026-10-28 18:59:56.786502+00:00
completed=2026-10-28 19:08:54.772068+00:00
failure=Partial scan: at least one required scanner did not complete a full
run (nikto partial, testssl timeout, gobuster timeout). Results are limited to
the scanners that finished; the absent checks are not proof that a finding is
resolved.
```

| Scanner | Statut | Durée (ms) | Budget |
|---|---:|---:|---:|
| website | completed | 829 | 15 s |
| ssl | completed | 348 | 15 s |
| dns | completed | 482 | 10 s |
| email_security | completed | 169 | 15 s |
| security_headers | completed | 730 | 15 s |
| performance | completed | 410 | 15 s |
| lighthouse | unavailable | 27 | — |
| uptime | completed | 228 | 10 s |
| nmap | completed | 16 228 | 75 s |
| nikto | **partial** | 92 369 | 100 s |
| nuclei | completed | 105 543 | 150 s |
| whatweb | completed | 10 659 | 25 s |
| testssl | **timeout** | 120 722 | 120 s |
| dnsrecon | completed | 3 992 | 30 s |
| gobuster | **timeout** | 46 341 | 45 s |
| zap | completed | 138 366 | 140 s |

Non-régression santé : scan **62**, même site, `health`, `completed`, score 69,
durée 5 s, aucun échec.

### Conclusion 1.1

Le passage à 120 s corrige le cas « 94 s sous charge modérée » mais **échoue**
sur le scan full réel : testssl est encore coupé à 120,7 s. Le scan reste
`partial` et le budget global est déjà saturé (537/540 s). Aller à 180 s
supprimerait gobuster/ZAP de la couverture. **À décider** : soit augmenter le
budget global et le time limit Celery (impact worker), soit réduire la portée
d'un autre scanner, soit accepter explicitement le statut `partial` sur cette
cible. Aucune de ces options n'a été appliquée sans validation.

---

## 1.2 — Détection soft-404 gobuster

### Implémentation

`backend/scanners/implementations/gobuster.py` :

- sonde d'un chemin aléatoire `/.presence-soft404-<hex>` avant le scan ;
- si la cible répond `200` avec un corps non vide, la longueur est passée à
  `gobuster --exclude-length <n>` ;
- si la sonde échoue ou renvoie autre chose, aucun `--exclude-length` n'est
  ajouté (comportement conservateur) ;
- la sonde et la longueur exclue sont enregistrées dans le résultat ;
- les séquences ANSI de progression (`ESC[2K`) sont retirées avant le parseur.
  Ce point a été découvert par le test réel : sans lui, la ligne
  `/admin (Status: 200)` était rejetée comme une bannière.

Tests unitaires ajoutés : détection 200 → `--exclude-length`, vrai 404 → pas
d'exclusion, sonde enregistrée, préfixe ANSI non destructif.

### Test réel sur deux cibles

Deux serveurs locaux réels, binaire Gobuster 3.6 de l'image :

```text
true404 random path: HTTP 404 bytes=335
spa random path:     HTTP 200 bytes=1193
spa catch-all body length: 1193

--- gobuster on true 404 target (no exclusion) ---
GOBUSTER_TRUE404_EXIT=0

--- gobuster on SPA target without exclusion ---
Error: the server returns a status code that matches the provided options for
non existing urls. http://127.0.0.1:18082/2e37f789-... => 200 (Length: 1193).
To continue please exclude the status code or the length
GOBUSTER_SPA_NOEXCLUDE_EXIT=1

--- gobuster on SPA target with --exclude-length 1193 ---
/admin                (Status: 200) [Size: 27]
GOBUSTER_SPA_EXCLUDE_EXIT=0
```

Interprétation : sur une cible à vrai 404, aucune régression (exit 0, aucun
résultat). Sur la SPA, le comportement antérieur était un exit 1 sans résultat ;
avec la sonde, Gobuster termine en exit 0 et trouve réellement `/admin`. Le
`partial` n'est pas transformé artificiellement en `completed` : si la sonde
échoue, l'exclusion n'est pas ajoutée et un exit 1 reste `partial`.

### Réserve sur la cible appchat

Dans le scan full 59, gobuster reste `timeout` à 46,3 s (budget 45 s) et le scan
reste partiel pour ce scanner. La détection soft-404 est donc validée en
laboratoire, mais la couverture de cette cible publique reste limitée par le
budget de 45 s. Ce n'est pas une régression : le comportement antérieur était
déjà incomplet.

---

## 1.3 — Alerte opérateur sur les runs IA reapés

### Implémentation

- `Alert.AlertType.AI_RUN_REAPED` (`ai_run_reaped`), migration
  `alerts/migrations/0002_alter_alert_alert_type.py` ;
- tâche `alerts.tasks.report_ai_run_reaped`, qui réutilise la table `Alert`, le
  dispatcher, les préférences (`scan_failed_enabled`, même famille d'incident)
  et les fenêtres de mute existantes ;
- déduplication par `metadata.run_id` ;
- `advisory.tasks.reap_stale_ai_runs` met l'alerte en file via `.delay` après
  chaque run clôturé, sans faire échouer le balayage si le broker est
  indisponible (`alerts_queued` dans le résultat).

### Preuve réelle (pas un mock)

Site QA 39, scan complété 60, run IA `c47d17db-d1f1-497a-8c62-f88457e75c92`
backdaté de 11 minutes. Après redémarrage de beat (nécessaire pour recharger
le planning), tick réel :

```text
[2026-10-28 19:03:13,725: ERROR/ForkPoolWorker-1] ai_advisor_run_reaped
run_id=c47d17db-d1f1-497a-8c62-f88457e75c92 scan_id=60 attempts=1 idle_s=833
error_code=stale_run_reaped
[2026-10-28 19:03:13,729: INFO/ForkPoolWorker-1] ai_advisor_reaper
cutoff=2026-10-28T18:53:13.699890+00:00 reaped=1 alerts_queued=1
[2026-10-28 19:03:14,185: INFO/ForkPoolWorker-1] report_ai_run_reaped:
alert c3defdb7-026b-4137-a0c0-6bb422cb77b1 created for run
c47d17db-d1f1-497a-8c62-f88457e75c92 (scan 60)
```

État en base, lu après coup :

```text
ALERT c3defdb7-026b-4137-a0c0-6bb422cb77b1 ai_run_reaped warning firing
created=2026-10-28 19:03:14.129925+00:00
meta={'run_id': 'c47d17db-d1f1-497a-8c62-f88457e75c92', 'scan_id': 60,
'error_code': 'stale_run_reaped'}
```

L'alerte est donc visible dans la même table que les alertes opérateur, pas
seulement dans les logs.

---

## 1.4 — Métriques de reap

### Implémentation

- `backend/core/reaper_metrics.py` : compteurs cumulés `ai_runs_total` et
  `scans_total`, horodatages `ai_last_tick`, `scans_last_tick`, `last_tick`,
  stockés dans le cache partagé sans expiration (Redis en déploiement) ;
- `record_reaper_tick()` appelé à chaque tick des deux reapers, y compris quand
  rien n'est reapé ;
- commande `python manage.py reaper_status` pour lecture sans logs ;
- une panne de cache est journalisée et ne casse jamais le balayage.

### Preuve réelle

Avant le tick : compteurs à 0, horodatages `null`.

Après le tick de 19:03:13 :

```text
{
  "ai_last_tick": "2026-10-28T19:03:13.730229+00:00",
  "ai_runs_total": 1,
  "last_tick": "2026-10-28T19:03:13.730229+00:00",
  "scans_last_tick": "2026-10-28T19:03:13.682397+00:00",
  "scans_total": 1
}
```

Après les ticks suivants (19:53:13), les horodatages avancent et les compteurs
restent à 1, ce qui prouve que beat tourne et qu'aucun nouvel élément n'a été
reapé :

```text
{
  "ai_last_tick": "2026-10-28T19:53:13.589953+00:00",
  "ai_runs_total": 1,
  "last_tick": "2026-10-28T19:53:13.589953+00:00",
  "scans_last_tick": "2026-10-28T19:53:13.524701+00:00",
  "scans_total": 1
}
```

Limite assumée : les compteurs sont dans le cache, pas dans une table ; un
flush Redis les remet à zéro. Cela répond au besoin « vérifier d'un coup d'œil
que le reaper tourne », sans prétendre à une métrique historisée.

---

## Tests et migrations

Commande exécutée :

```text
bash scripts/run_backend_tests.sh advisory scans.tests.test_stale_scans \
  scanners.tests.test_advanced_tool_adapters
```

Résultat brut :

```text
Ran 242 tests in 1135.063s

OK

Destroying test database for alias 'default'...
```

Code de sortie : **0**. Aucune assertion existante retirée ou affaiblie ; les
tests ajoutés portent sur l'alerte, les métriques, la sonde soft-404 et le
parseur ANSI.

Tests ciblés antérieurs :

- `advisory.tests.test_reaper scans.tests.test_stale_scans` : **16 tests OK** ;
- `scanners.tests.test_advanced_tool_adapters` : **33 tests OK**.

Migration :

```text
$ python manage.py migrate alerts
Applying alerts.0002_alter_alert_alert_type... OK
$ python manage.py makemigrations --check --dry-run
No changes detected
```

La migration ne modifie que les `choices` du champ `alert_type` (aucun changement
de colonne PostgreSQL).

---

## Isolation et données de test

- Seuls `celery-worker` (reconstruction de l'image, redémarrage à 18:58:31) et
  `celery-beat` (redémarrage à 19:02:58 pour recharger le planning) ont été
  recréés/redémarrés. Les autres conteneurs n'ont pas changé de `StartedAt`.
- Aucun service AI Platform, OmniRoute, FingptFinrobot, VPS ou WordPress n'a été
  touché.
- Données de test créées, non supprimées : sites QA 38 et 39, scans 59, 60, 61,
  62, run IA `c47d17db-...`, alertes `c3defdb7-...` et
  `38f7e106-...`. Elles restent à nettoyer sur décision explicite.

---

## Réserves restantes

1. Testssl.sh reste non complet sur la cible appchat dans le budget de 540 s ;
   décision de budget à prendre.
2. Nikto reste `partial` par construction (`maxtime`), indépendamment de ce lot.
3. Gobuster reste `timeout` sur appchat avec 45 s, même si la détection soft-404
   fonctionne en laboratoire.
4. Lighthouse est `unavailable` dans le worker (binaire absent) ; limitation
   antérieure, non traitée ici.
5. Les compteurs de reap sont volatils (cache Redis) ; suffisant pour
   l'exploitation immédiate, pas pour un historique.
