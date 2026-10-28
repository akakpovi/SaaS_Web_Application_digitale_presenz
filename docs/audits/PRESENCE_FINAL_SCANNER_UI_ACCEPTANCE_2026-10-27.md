# Presence — Acceptation finale scanners et interface

**Date :** 27 octobre 2026
**Périmètre :** pile locale Presence reconstruite. Aucun déploiement, aucune cible externe non autorisée.
**Complète :** `PRESENCE_ADVANCED_SCANNERS_INSTALLATION_2026-10-27.md` (installation des six scanners), `PRESENCE_UI_SCANNER_VALIDATION_2026-10-27.md` (parcours UI des statuts), `PRESENCE_SCAN_STATUS_INTEGRITY_2026-10-26.md` (agrégation des statuts).

---

## 1. Images et services réellement actifs (après reconstruction contrôlée)

| Service | Image | État |
|---|---|---|
| `web` | `saas_web_application_digitale_presenz-web:latest` (`45e6cc6dcc76`, reconstruite depuis l'arbre de travail) | healthy |
| `celery-worker` | `…-celery-worker:latest` (`ae477d4a538d`) | running |
| `celery-beat` | `…-celery-beat:latest` (`ebc2b4d5a353`) | running |
| `frontend` | `…-frontend:latest` (`38331c457fb9`) | healthy |
| `scanner-tools` (jetable) | `presence-scanner-tools:2026-10-27` | utilisée par le worker pour sandboxer les scanners |
| `db`, `redis`, `wordpress`, `mailpit`, `scanner-egress-guard`, `scanner-sandbox-anchor` | inchangés | running/healthy |

Aucun volume supprimé. Le worker recréé monte toujours `scanner_archive_data` sur `/app/scanner-archives` (propriétaire `app`, mode `0700`, archives existantes `dnsrecon` conservées).

**Rappel de méthode :** le conteneur `web` n'a aucun montage du code source. Avant reconstruction, la pile exécutait une image antérieure aux correctifs ; les validations ci-dessous ont été produites **après** reconstruction.

---

## 2. Outils scanner disponibles (preuve d'exécution)

`docker compose run --rm --entrypoint /usr/local/bin/scanner-tools-check scanner-tools` :

```
nmap         Nmap version 7.93 ( https://nmap.org )
nikto        Nikto 2.6.1 (LW 2.5)
whatweb      WhatWeb version 0.5.5
testssl.sh   <no version output>
dnsrecon     DNSRecon version 1.1.3
gobuster     3.6
wordlist     /usr/share/dirb/wordlists/common.txt (4614 entries)
```

- Nuclei : `projectdiscovery/nuclei:latest` (3.11.1 au digest restauré lors du nettoyage du 27/10) — config `SCANNER_DOCKER_IMAGE_NUCLEI`.
- OWASP ZAP : `zaproxy/zap-stable:latest` — config `SCANNER_DOCKER_IMAGE_ZAP`.
- Les six scanners avancés utilisent l'image partagée `presence-scanner-tools:2026-10-27` (`SCANNER_TOOLS_IMAGE`, surchargeable par scanner via `SCANNER_DOCKER_IMAGE_<OUTIL>`).
- `testssl.sh` est présent (détecté par le script de contrôle) mais ne renvoie pas de chaîne de version sur `--version` en shell non interactif ; sa version exacte n'est donc **pas** attestée ici.

---

## 3. Chaîne d'exécution et d'archivage réellement validée

`scripts/integrated_acceptance_recipe.py` (exécuté dans le conteneur `web`, API réelle, pile finale) :

| Étape | Preuve observée |
|---|---|
| Site créé via API | 201 |
| Scan `health` lancé | 202, exécuté par Celery |
| État terminal | `completed`, score 69 |
| Artefacts persistés | 7 `CheckResult`, 8 `ScannerRun`, 7 `Finding` |
| API vs base | `api=completed` / `db=completed` (aucun écart) |
| Filtre de liste | `?status=completed` fonctionnel |
| Surveillance | activation → planification, pause → planification vide |
| Isolation | site et scan d'un autre compte → 404 |
| AKA IA | extérieur 404 sans appel modèle, propriétaire 200 (modèle réel) |

Résultat global : **17/17**. Idempotence des reprises, non-résolution sur scan incomplet et agrégation `completed`/`partial`/`failed` restent couvertes par les suites backend (`scans`, `alerts`, `advisory`, `monitoring`).

---

## 4. Interface validée dans le navigateur

Session authentifiée sur le serveur de développement Vite (`http://localhost:5173`), données réelles de la recette :

| Écran | Observation |
|---|---|
| Détail du site | Statut « Critical », score 69/100, six contrôles détaillés (DNS, e-mail, performance, en-têtes, SSL, disponibilité) avec libellés Action, résumés et scores par catégorie |
| Bandeau de surveillance | « Monitoring paused » + carte d'activation expliquant ce qui est surveillé, la fréquence (24 h), le quota mensuel et la réversibilité |
| Page Monitoring | Résumé (0/1 activé, « No schedule »), graphique d'uptime réel (2 checks, 0 échec), timeline d'événements (« Scan completed — 69/100 », alertes en-têtes et e-mail) |
| Bouton de pause/activation | Clic « Activate monitoring » → bandeau « active » et carte retirée ; clic « Pause monitoring » → badge « Monitoring off », bouton « Activate monitoring », résumé « 0 of 1 websites enabled » |
| Page Alerts | Filtres Tous/Critical/Warning/Resolved, alertes réelles issues du scan (en-têtes de sécurité, authentification e-mail) |
| Console et réseau | Aucune erreur console ; toutes les requêtes API en 200 |

Captures :

- `docs/audits/screenshots/presence-website-monitoring-activation-2026-10-27.png`
- `docs/audits/screenshots/presence-monitoring-toggle-2026-10-27.png`

---

## 5. État des statuts après la mission

- Un scan `full`/`security` n'est `completed` que si tous les scanners requis ont terminé ; un scanner optionnel indisponible ne dégrade pas un scan santé (correctif et test dédiés, cf. rapport d'intégrité).
- Un scan incomplet devient `partial` (résultats exploitables) ou `failed`, **jamais** `completed` ; aucun constat n'est résolu sur cette base.
- `partial` et `failed` déclenchent une alerte de couverture, maintenue dans une seule alerte `firing` reliée au dernier scan, escaladée en `critical` après une deuxième exécution incomplète consécutive.
- L'interface distingue les états (`StatusBadge`, ton neutre pour « Monitoring off ») et n'affiche jamais un scan partiel comme une évaluation complète.

---

## 6. Limites

- **Scans `security`/`full` de bout en bout non rejoués dans cette session** : les six scanners ont été installés et validés lors de la mission précédente ; ici, seule la présence des binaires et la chaîne health/ingestion/UI ont été réexécutées. Un scan de sécurité réel complet reste à refaire lors de la recette finale sur une cible autorisée (le dernier a été agrégé `partial` à cause de Gobuster sur une SPA, comportement honnête et attendu).
- `testssl.sh` : version exacte non attestée (pas de sortie de version exploitable).
- Le test de performance de la page (Lighthouse) n'a pas été réexécuté.
- Les scans de la recette sur `appchat.elomaiapp.com` sont conservés comme données de test locales ; aucun scan historique n'a été modifié ou supprimé.
