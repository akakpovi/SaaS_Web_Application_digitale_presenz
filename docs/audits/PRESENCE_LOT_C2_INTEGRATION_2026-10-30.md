# Presence — Lot C2 : intégration du scénario C au palier 2 des parcours progressifs

**Version du lot** : 2026-10-30  
**Validation d'exécution** : 2026-11-04  
**Périmètre** : pipeline de scan backend uniquement (Django REST, scanners, image `scanner-tools`)  
**Statut** : **À VÉRIFIER MANUELLEMENT** — le pipeline est intégré, la non-régression complète est verte et les outils ont été exécutés sur le laboratoire local. La seule vérification non réalisable dans ce lot est un scan Django complet `journey_stage=2` via Celery contre une cible publique autorisée : les cibles du laboratoire sont en RFC1918 et le validateur SSRF de Presence les refuse par conception.

---

## 1. Synthèse exécutive

Le Lot C2 branche le scénario C **exclusivement sur les scans dont `journey_stage == 2`** :

- **Nuclei optimisé** : 61 templates communautaires sélectionnés + 10 templates originaux Presence, dans le profil `scenario_c` ;
- **Gobuster** : wordlist principale `dirb/common.txt` inchangée + seconde passe bornée de 19 chemins Presence ;
- **budget** : 360 s pour le palier 2, avec 180 s pour Nuclei et 120 s pour Gobuster ;
- **déduplication** : les constats de contenu sont conservés par identité canonique, et une découverte Gobuster du même chemin devient une preuve complémentaire au lieu d'un doublon.

Les scans classiques (`journey_stage=NULL`) conservent exactement leur pipeline historique : `_SECURITY_STEPS`, profil Nuclei `standard`, budget 540 s, Nikto présent, wordlist principale inchangée. Nikto n'a été ni retiré de l'image, ni retiré des scans classiques.

### Résultats vérifiés

| Contrôle | Résultat |
|---|---|
| Suite backend complète | **1 037 tests OK**, exit 0, 936,755 s |
| Tests dédiés au Lot C2 | **21 tests OK**, exit 0, 8,355 s |
| Validation Nuclei des 71 templates | **All templates validated successfully**, exit 0 pour les deux répertoires |
| Image `scanner-tools` reconstruite | exit 0 ; 61 + 10 templates, 19 chemins, Nikto et Gobuster présents |
| Intégration Nuclei sur DVWA local | exit 0 ; 15 résultats, 6 templates distincts, 10 constats d'en-têtes distincts |
| Intégration Gobuster sur DVWA local | exit 0 pour les deux passes ; 14 + 3 résultats, 16 chemins uniques après fusion |
| Migrations du domaine `scans` | `No changes detected in app 'scans'` |
| Modifications de production | aucune : pas de déploiement, pas de redémarrage de service, pas de migration, pas de frontend, pas de Celery/quotas/alertes |

### Réserve unique

Le laboratoire DVWA est accessible sur `10.42.10.5` dans le réseau Docker isolé `pentest-lab-core`. Le pipeline Django complet refuse cette adresse car le validateur SSRF de Presence bloque les plages privées. Les deux outils ont donc été exécutés avec **les paramètres exacts du profil** et **les assets de l'image**, sur cette cible locale, mais le chemin Celery → orchestration → ingestion n'a pas été rejoué contre le laboratoire. Cette vérification end-to-end devra être faite sur une cible publique explicitement autorisée avant activation.

---

## 2. Fichiers modifiés et créés

### 2.1 Fichiers modifiés

| Fichier | Modification |
|---|---|
| `backend/config/settings/base.py` | Budgets du palier 2, profil `scenario_c`, chemin des templates scénario, `extra_wordlist` Gobuster |
| `backend/config/settings/test.py` | Désactive la seconde passe Gobuster dans la suite unitaire ; les tests dédiés la réactivent explicitement |
| `backend/.env.example` | Variables `SCAN_JOURNEY_STAGE2_*`, `SCANNER_GOBUSTER_EXTRA_WORDLIST`, `SCANNER_NUCLEI_SCENARIO_TEMPLATES_PATH` |
| `backend/scanners/base.py` | Champ `ScanContext.profile`, alimenté uniquement par l'orchestrateur |
| `backend/scanners/implementations/nuclei.py` | `template_paths` multiples, profil par étape, timeout par profil, montage lecture seule, constats d'en-têtes distincts en scénario C |
| `backend/scanners/implementations/gobuster.py` | Seconde passe optionnelle, fusion et déduplication par chemin canonique |
| `backend/scanners/implementations/tool_run.py` | Budget explicite par invocation, utilisé par la seconde passe |
| `backend/scanners/executors/sandbox.py` | Autorisation du répertoire de templates scénario et montage `readonly` |
| `backend/scans/services/steps_builder.py` | `_JOURNEY_STAGE2_STEPS`, `get_steps_for_scan()` |
| `backend/scans/services/orchestrator.py` | Sélection des étapes selon `journey_stage`, budget 360/540, déduplication à l'ingestion |
| `backend/docker/scanner-tools/Dockerfile` | Copie des 71 templates et de la wordlist, contexte de build élargi au backend |
| `backend/docker/scanner-tools/check-tools.sh` | Vérification des templates et de la wordlist complémentaire |
| `docker-compose.yml` | Contexte de build `backend`, chemin hôte des templates scénario |

### 2.2 Fichiers créés

| Chemin | Rôle |
|---|---|
| `backend/scans/services/finding_dedup.py` | Clé canonique, chemins canoniques, fusion de preuve complémentaire |
| `backend/scans/tests/test_scenario_c_integration.py` | 21 tests du profil, des étapes, du budget, de Gobuster et de la déduplication |
| `backend/scanners/templates/selected/` | 61 templates communautaires, arborescence source conservée |
| `backend/scanners/templates/selected-manifest.tsv` | Identifiant, chemin source, sévérité et SHA-256 des 61 templates |
| `backend/scanners/templates/selected/LICENSE.md` | Notice MIT ProjectDiscovery |
| `backend/scanners/templates/presence/` | 10 templates originaux Presence |
| `backend/scanners/templates/presence/LICENSE.md` | Notice MIT Presence |
| `backend/scanners/templates/LICENSE` | Notice d'ensemble des deux répertoires |
| `backend/scanners/wordlists/presence-extra.txt` | 19 chemins complémentaires |
| `backend/scanners/wordlists/LICENSE.md` | Origine et licence de la liste originale |
| `docs/audits/PRESENCE_LOT_C2_INTEGRATION_2026-10-30.md` | Le présent rapport |

Aucun fichier de `scans/models.py`, `scans/migrations/`, `ScanJourney`, `frontend/` ou des tâches Celery n'a été modifié par ce lot.

---

## 3. Inventaire de l'environnement de validation

| Élément | Valeur mesurée |
|---|---|
| Hôte | 4 vCPU, 15 Gio de RAM, environ 20 Gio disponibles sur `/` |
| Charge pendant la validation | environ 3,6 à 5,6 ; aucun benchmark lourd concurrent |
| Nuclei | `v3.11.1`, image `projectdiscovery/nuclei:latest`, digest `sha256:582d5546902e67052097cb2d07296c642d50a1afc5e44623cb038845df9a32eb` |
| Gobuster | `3.6`, dans `presence-scanner-tools:2026-10-27` |
| Nikto | `2.6.1 (LW 2.5)`, toujours présent dans l'image |
| Wordlist principale | `/usr/share/dirb/wordlists/common.txt`, 4 614 entrées, inchangée |
| Laboratoire | `pentest-lab-core`, DVWA `10.42.10.5`, conteneurs `pentest-lab-*` déjà présents |
| Cible utilisée | DVWA locale uniquement ; aucune cible externe |
| Image scanner après reconstruction | `sha256:b94d19b98e32d36bfc29044ddece95018bee92ccaee3d27e46e77f71ff4cdc76` |

Le laboratoire n'a reçu aucune connexion aux bases Presence, à OmniRoute ou à AI Platform. Aucun conteneur d'un autre projet n'a été arrêté, aucun volume supprimé, aucun `docker system prune` exécuté.

---

## 4. Profil Nuclei `scenario_c`

### 4.1 Configuration exacte

Le profil est déclaré dans `SCANNER_CONFIG["nuclei"]["profiles"]["scenario_c"]` :

```python
"scenario_c": {
    "description": (
        "Stage-2 progressive journey profile: 61 explicitly "
        "selected exposure/misconfiguration templates plus the "
        "10 original Presence controls.  Not the full catalogue; "
        "used only for journey_stage=2."
    ),
    "template_paths": [
        "/opt/scanner-templates/selected",
        "/opt/scanner-templates/presence",
    ],
    "severity": "info,low,medium,high,critical",
    "protocol": "http",
    "request_timeout": 5,
    "retries": 1,
    "concurrency": 20,
    "bulk_size": 10,
    "rate_limit": 60,
    "max_host_error": 40,
    "exclude_tags": [
        "dos", "fuzz", "fuzzing", "intrusive",
        "brute-force", "default-login",
        "credential-stuffing", "token-spray",
    ],
    "extra_args": ["-duc"],
    "requires_advanced_security": True,
    "time_budget_seconds": 180,
    "timeout": 180,
    "duration_alert_s": 180,
    "resolve_missing": False,
}
```

`resolve_missing=False` est volontaire : un profil qui ne charge qu'une sélection de 71 templates ne peut pas prouver la disparition d'un constat hors sélection.

### 4.2 Commande produite

`build_command()` émet un `-t` par chemin lorsque le profil contient `template_paths`, et un seul `-t` pour les profils historiques qui utilisent `templates` :

```text
nuclei -u <cible> -jsonl -no-color -disable-update-check \
  -stats -stats-json -stats-interval 5 \
  -timeout 5 -retries 1 -bulk-size 10 -concurrency 20 \
  -rate-limit 60 -max-host-error 40 -ip-version 4 -type http \
  -exclude-tags dos,fuzz,fuzzing,intrusive,brute-force,default-login,credential-stuffing,token-spray \
  -t /opt/scanner-templates/selected \
  -t /opt/scanner-templates/presence \
  -severity info,low,medium,high,critical -duc
```

Le parsing JSONL est inchangé : Nuclei écrit toujours une ligne JSON par résultat, y compris avec plusieurs `-t`.

### 4.3 Contrôle des en-têtes manquants

Nuclei émet **un enregistrement JSONL par matcher** pour `http-missing-security-headers`. Sur DVWA, le test réel a produit 10 lignes partageant le même `template-id` et la même URL, mais avec des `matcher-name` différents :

```text
strict-transport-security
content-security-policy
x-content-type-options
x-permitted-cross-domain-policies
cross-origin-opener-policy
cross-origin-resource-policy
permissions-policy
x-frame-options
referrer-policy
cross-origin-embedder-policy
```

La normalisation du palier 2 conserve donc 10 constats distincts, avec des `check_code` de la forme `nuclei.http-missing-security-headers.<en-tête>`. La normalisation des profils classiques conserve son comportement historique d'agrégation (un seul constat pour le couple template/URL) ; le test dédié vérifie explicitement les deux comportements.

---

## 5. Templates intégrés

### 5.1 Licences et provenance

- **61 templates communautaires** : `projectdiscovery/nuclei-templates`, licence MIT, commit de catalogue `5cfe87d58464ab47a871d0be3d2844bf51e6eda5` (2026-10-30). Notice complète dans `backend/scanners/templates/selected/LICENSE.md`.
- **10 templates Presence** : travaux originaux Presence, licence MIT, notice dans `backend/scanners/templates/presence/LICENSE.md`.
- **Notice d'ensemble** : `backend/scanners/templates/LICENSE`.

Aucune signature, aucun identifiant et aucune structure de la base Nikto n'a été copié, traduit ou adapté. Le pack Presence a été rédigé à partir de RFC HTTP, des recommandations OWASP, des documentations Apache/nginx/PHP/Git et des comportements observés sur les cibles de laboratoire.

### 5.2 Sécurité des templates

Vérifications statiques sur les 71 templates :

```text
méthodes HTTP : 71 × GET
POST / PUT / DELETE / PATCH : 0
attack / fuzzing / race / exploitation intrusive : 0
service externe hors bande : 0
```

Le seul terme `interactsh` trouvé est un **nom de technologie** dans les matchers de `tech-detect`, pas une interaction OOB. Les fichiers sensibles sont lus avec des limites de taille ; aucun fichier volumineux n'est téléchargé intégralement.

### 5.3 Liste exacte des 61 templates communautaires

Le manifeste `selected-manifest.tsv` contient les mêmes 61 entrées. Vérification effectuée : **61 entrées, 0 écart SHA-256**.

| # | Identifiant | Chemin source | Sévérité | SHA-256 |
|---:|---|---|---|---|
| 1 | `backup-directory-listing` | `http/exposures/backups/backup-directory-listing.yaml` | low | `8fc24c56ee2d244ab988743c0b1cc83c083996ffd1f03d292d8aa27f78ee7760` |
| 2 | `sql-server-dump` | `http/exposures/backups/sql-server-dump.yaml` | medium | `792c1c23d9c19ea231c9a47606b7bbb437d281e6f3d173a354818c53bc94e12d` |
| 3 | `ansible-config-disclosure` | `http/exposures/configs/ansible-config-disclosure.yaml` | medium | `d502c3d274e3f4e88fc86e063d05239e0239566b4f6b39a4ce98448931a89fe3` |
| 4 | `apache-config` | `http/exposures/configs/apache-config.yaml` | medium | `09425476e1f0fc1bc0710cd575255d82f09d3204ca73e2431a27b097dd6e412a` |
| 5 | `aws-credentials` | `http/exposures/configs/aws-credentials.yaml` | high | `c269f281e873a7fad391eb3f1f41b054c99537101ff2efc13dd4937be984b093` |
| 6 | `cgi-printenv` | `http/exposures/configs/cgi-printenv.yaml` | medium | `914c2a8d01d948653ab82fc7d00d55a40e3e41af9c7c4fd7b3ff56416e3e3c5d` |
| 7 | `circleci-config` | `http/exposures/configs/circleci-config.yaml` | medium | `55f360aede187563778f69ea17b39908d60a8a1c74a59dff2e93e986821ff7d6` |
| 8 | `composer-config` | `http/exposures/configs/composer-config.yaml` | info | `01631377e15e83ed6306d7c02105a3b3d78f388e7393a733f4a354f1a1baf572` |
| 9 | `configuration-listing` | `http/exposures/configs/configuration-listing.yaml` | medium | `b034c589ba835975bd0d538e7d76aaf5218d8e89e4b2930c3b939eaa864abceb` |
| 10 | `debug-vars` | `http/exposures/configs/debug-vars.yaml` | low | `2e072469a3979f24d3cd89b848786af91bd0d6087c3091e97206968fba74b2b3` |
| 11 | `docker-compose-config` | `http/exposures/configs/docker-compose-config.yaml` | medium | `b2603cd2bf3fdb6f74a835746774894d8dc21b7cb21c9b679eaba293213a0fb0` |
| 12 | `dockercfg-config` | `http/exposures/configs/dockercfg-config.yaml` | high | `b5f8748f326f4c195eb46bc2791f454f5b796de1f570b0cd548041f9e2e94a80` |
| 13 | `dockerfile-hidden-disclosure` | `http/exposures/configs/dockerfile-hidden-disclosure.yaml` | medium | `40f7a62d7dd39959fd74b2a574d2b6c31ac87bf17623df295d34c2ad477eed04` |
| 14 | `exposed-bzr` | `http/exposures/configs/exposed-bzr.yaml` | info | `7b79c1c30766674d34e2471ce10ddd168bf26c9a184b9d623067180dc145d9a4` |
| 15 | `exposed-gitignore` | `http/exposures/configs/exposed-gitignore.yaml` | info | `c8cd9fa4c56e5f7c6266d2c362a995bb3d53dafbbac036f7a6341e397a2d6a7e` |
| 16 | `exposed-gitmodules` | `http/exposures/configs/exposed-gitmodules.yaml` | high | `22f95dd5d0a15b314e81d2d18b8840f2f004280cac4508054840dac311f3b892` |
| 17 | `exposed-hg` | `http/exposures/configs/exposed-hg.yaml` | medium | `30bcaad1958cd29d099b06ec7a6db3b077ff20e1f628594ad6390233212f7199` |
| 18 | `exposed-svn` | `http/exposures/configs/exposed-svn.yaml` | medium | `4f99844c8a34d0d418b1b56a708199f157c66b94f91dc551ed0fb73556c80192` |
| 19 | `git-config` | `http/exposures/configs/git-config.yaml` | medium | `bd8bdfa0b5ed5bf4d3712edb793adfd0987d9282e51c6f7d673bf14b9e4dd524` |
| 20 | `git-credentials-disclosure` | `http/exposures/configs/git-credentials-disclosure.yaml` | medium | `cd11b069ef6cddca723a38d44b932b9042d5f22a34a5d1bd8bb2423e9b85a9a4` |
| 21 | `htpasswd-detection` | `http/exposures/configs/htpasswd-detection.yaml` | high | `c3237fd7d8caf732c23396451209d45cc9138e05632feb54afc1d056fcdd8c01` |
| 22 | `mysql-config-exposure` | `http/exposures/configs/mysql-config-exposure.yaml` | high | `4af26c6ac85f7640d9486c47e560d24665f00f1cf9a19b27997c7b50e5937395` |
| 23 | `netrc` | `http/exposures/configs/netrc.yaml` | high | `51441cd1fa206d397e5b7e7e5dba166df09c2466fa8a8eb6cabc092a1286cb95` |
| 24 | `nginx-config` | `http/exposures/configs/nginx-config.yaml` | info | `e4c8c0208a3d7c6e21cc164990998d19646988ec5a8aeea7d2b428300cf56c0e` |
| 25 | `package-json` | `http/exposures/configs/package-json.yaml` | low | `55992232b5a1dd8f931e88574cca7d238f9a387b26e68d49a81f886136aaa842` |
| 26 | `perl-status` | `http/exposures/configs/perl-status.yaml` | medium | `8e904565bc8773bfeb8d065402edffabc610b8a8b2029dfbd17338a6605aefc1` |
| 27 | `php-fpm-config` | `http/exposures/configs/php-fpm-config.yaml` | info | `c08e11436b8934c88582867f271905376053926d02cd4929f46ab1eb654d6557` |
| 28 | `phpinfo-files` | `http/exposures/configs/phpinfo-files.yaml` | low | `8cbe8c980a71099bcaf84f195bf46fef9b24b3b7caa8476f713a4c01ed044a31` |
| 29 | `pyproject-toml` | `http/exposures/configs/pyproject-toml.yaml` | info | `f77dc6578ee8ae19f97268069d6b83918303178fb46fcb8134de99e424bd69bc` |
| 30 | `rails-database-config` | `http/exposures/configs/rails-database-config.yaml` | high | `3e5d2799a526c2b9dc2826da4c1d14d9e42e60e38ea2ded821bd2e8cc0e8c99e` |
| 31 | `redis-config` | `http/exposures/configs/redis-config.yaml` | medium | `25b5c517dda7c6c78d5ad0d60e4b2f9b51906f5ea4a85f3c8577c3aaece2077c` |
| 32 | `symfony-security-config` | `http/exposures/configs/symfony-security-config.yaml` | info | `cede13ed24e17b4f2b4b3d8bee358a298c7d8c630fe589a20809bc0d8bcb6a43` |
| 33 | `terraformrc-credentials-exposure` | `http/exposures/configs/terraformrc-credentials-exposure.yaml` | high | `15cc609e0b1120c4aa7cd6e73bfe7efd5c32ce3e2376d7f23bc4b0ca365d1237` |
| 34 | `vite-config` | `http/exposures/configs/vite-config.yaml` | low | `8f50db4abbe5280c75970ccfdc9d76d79cfacf86b1c89bec69449743135ad89b` |
| 35 | `webpack-config` | `http/exposures/configs/webpack-config.yaml` | info | `7ae737bce6d7b3ac5b749b6d01617ffd88855c1eb749d2a253d1502ebfd34136` |
| 36 | `credentials-json` | `http/exposures/files/credentials-json.yaml` | medium | `6caa5bebd698c5e8080898cf1a0b92ff5f9ceeef52f0fd563a1e3a28e1464546` |
| 37 | `database-credentials` | `http/exposures/files/database-credentials.yaml` | low | `fdedc67577c9cbde3ef00a6cac6e95d740bd83276428854280a7947fbcf4583d` |
| 38 | `django-secret-key` | `http/exposures/files/django-secret-key.yaml` | high | `96971909e59260d1dc789172199d1b630bdac3a626657f53684720eccd1b91a8` |
| 39 | `ds-store-file` | `http/exposures/files/ds-store-file.yaml` | low | `eeaa88a701796f263e8e4c32a5d16ae3e18b2cc97d65338632e4ac8b9e49b7a8` |
| 40 | `ftpconfig` | `http/exposures/files/ftpconfig.yaml` | high | `455083bbfbdbde511c2fb1d7df3bb070c2d5684e9760dc3445da1318b33bfdfa` |
| 41 | `gitlab-ci-yml` | `http/exposures/files/gitlab-ci-yml.yaml` | medium | `3662e0d10a0a7432cebee3d564e3ac536066c2f31efa85a346aa6d823d9bc024` |
| 42 | `npmrc-authtoken` | `http/exposures/files/npmrc-authtoken.yaml` | info | `dbeb9ec6ee2942bbf37c31c7c7e977413a7f5d773e07d71fc01dcca132d5fee4` |
| 43 | `readme-md` | `http/exposures/files/readme-md.yaml` | info | `e1e56ba22f54ce2177f6f26fdaf86efc975d8aac6f53c2b732c26feb574d6dbe` |
| 44 | `development-logs` | `http/exposures/logs/development-logs.yaml` | info | `2917febaea0ad0d7d8da3d836c9be2f4ed7e789b656a326a08086d242184c275` |
| 45 | `error-logs` | `http/exposures/logs/error-logs.yaml` | low | `a34e047efde3d7d0d5ca16bd019369bbb4ca2df7867a8af3ba3132a855f6b616` |
| 46 | `git-logs-exposure` | `http/exposures/logs/git-logs-exposure.yaml` | info | `3b4860cab67178c876788291c6f572c262290c6db71ddeafa5a38b9cef47f309` |
| 47 | `laravel-log-file` | `http/exposures/logs/laravel-log-file.yaml` | high | `293104a714bbcbd49ab87d09cfa4325969290804fc567a6435826a5be12cfbd2` |
| 48 | `production-logs` | `http/exposures/logs/production-logs.yaml` | info | `32064ab49b43b2d099ddf6874dd8a8b02b9aec57be1ee9524189e363d34139b9` |
| 49 | `robots-txt` | `http/miscellaneous/robots-txt.yaml` | info | `cbb85087c144aaa6ba3dd7f50cd1dd86e2476ce71c1493863f30fccd5a459fa5` |
| 50 | `apache-server-status` | `http/misconfiguration/apache/apache-server-status.yaml` | low | `a0b401b09818e26203a06fdfdffdfd3a5a1af18a7b3ebd72eaaa982adb27f456` |
| 51 | `cookies-without-httponly` | `http/misconfiguration/cookies-without-httponly.yaml` | info | `57bb6c47db154b227ac20f1bfd1f67417e578d05eda6b5067e5fdc120589d7c1` |
| 52 | `cookies-without-secure` | `http/misconfiguration/cookies-without-secure.yaml` | info | `07053e22c4ef28f450ad1b8148f4b9f307ce810ad4404387ed53883203f6b685` |
| 53 | `http-missing-security-headers` | `http/misconfiguration/http-missing-security-headers.yaml` | info | `7f45803f73ac6810b9b302df6be2c472a82d9164a7807328614efa83e6eac275` |
| 54 | `missing-cookie-samesite-strict` | `http/misconfiguration/missing-cookie-samesite-strict.yaml` | info | `4a22055d24d58e07f73a97967f0faf0dbaf80ee421641082c7561143e54bd9d8` |
| 55 | `nginx-status` | `http/misconfiguration/nginx/nginx-status.yaml` | info | `931c4e8049b9d94d2a79d9a476f295db87fe5f5b65d760491a5ca2b4cb80b307` |
| 56 | `server-status` | `http/misconfiguration/server-status.yaml` | info | `540d4cc923eb76f1291b5f2e33a4aabda9c2c1f44ad2c58576bcbd4cfe755950` |
| 57 | `weak-csp-detect` | `http/misconfiguration/weak-csp-detect.yaml` | info | `19a538b692c062b1d6bcb075b572663fcce3fa8f02289413eece914fdd6747d2` |
| 58 | `apache-detect` | `http/technologies/apache/apache-detect.yaml` | info | `2b15aaf0e02234242b44a86684fa38aa7bb68cb01d88b41de5f78cc971a8cdd3` |
| 59 | `apache-httpd-eol` | `http/technologies/eol/apache-httpd-eol.yaml` | info | `14d48353ea16076b8f398e61f465ce214b3e6bfd5f4f34c54d2629691dd1733d` |
| 60 | `nginx-version` | `http/technologies/nginx/nginx-version.yaml` | info | `aa410fb8361f2109ac247b16419040cc2cce1e3d9c76f0a51593806e7c1b7cd7` |
| 61 | `tech-detect` | `http/technologies/tech-detect.yaml` | info | `981080e049c7a1c9e418048e41ef7d7089d9f4f1b1c9d3d8094136349c087a95` |

### 5.4 Les 10 templates Presence

| Identifiant | Fichier | Sévérité | SHA-256 |
|---|---|---|---|
| `presence-admin-login-surface` | `presence-admin-login-surface.yaml` | info | `81c67b876f4d40a6a1bb442f618ce166bb9f864c6b7b4b9889e0c82a6d3a3e57` |
| `presence-backup-archive` | `presence-backup-archive.yaml` | high | `132a8aa8ff6bdfc8ae1839480efd89c97940259aee7d6ddbe0fad94f286da736` |
| `presence-cors-credentials` | `presence-cors-credentials.yaml` | medium | `1d22ccad4c9d2b40449cb4aede9862067d07a8a5769d44e6920c73a0a405cd4d` |
| `presence-directory-listing` | `presence-directory-listing.yaml` | low | `042870eed4d8ee7336fc8d6a6b54c997b6fc220e36db92c10b723892fddb4d7c` |
| `presence-env-exposure` | `presence-env-exposure.yaml` | high | `cd8f5f25e467956ae244e499fd27f7477985e74bf9d00c8903b69aaa2bf96b00` |
| `presence-icons-readme` | `presence-icons-readme.yaml` | low | `06d6aebabea87cbea05ea20ba848378a1a9d8a6cd8fbd88ca542c3c1fcc3a10e` |
| `presence-php-config-backup` | `presence-php-config-backup.yaml` | high | `acc4bf0d218b881abe46fd2da1e83995e284d9511c3af648cf5c78d0ffb5287d` |
| `presence-robots-sensitive-paths` | `presence-robots-sensitive-paths.yaml` | info | `92bed6c14569de18fa5cb56669202726ce2bcf57fb48d99baf40b4b97c7104bc` |
| `presence-server-version-banner` | `presence-server-version-banner.yaml` | info | `dcfa48ca4bf4c10fefc2f1ccb4e212bd4e19b39f6f271c6459e02fae0d4782dd` |
| `presence-sql-dump` | `presence-sql-dump.yaml` | high | `cd4792585d912e72aa920d8eba8683c953574129864d97490759abcf4b37c9cd` |

### 5.5 Validation syntaxique

```text
$ docker run --rm -v .../templates/presence:/presence:ro \
    --entrypoint nuclei projectdiscovery/nuclei:latest -validate -t /presence
presence_exit=0
[INF] All templates validated successfully

$ docker run --rm -v .../templates/selected:/selected:ro \
    --entrypoint nuclei projectdiscovery/nuclei:latest -validate -t /selected
selected_exit=0
[INF] All templates validated successfully
```

Nuclei émet un avertissement sur la résolution des sous-templates relatifs hors du répertoire par défaut ; les 71 templates sont autonomes et la validation aboutit avec exit 0.

---

## 6. Wordlist Gobuster complémentaire

### 6.1 Contenu

`backend/scanners/wordlists/presence-extra.txt`, 19 lignes :

```text
.git/config
.git/HEAD
.gitignore
backup.zip
backup.tar.gz
database.sql
dump.sql
db.sql
config.php.bak
config.inc.php.bak
config/config.inc.php.bak
wp-config.php.bak
.env
.env.local
docker-compose.yml
icons/README
server-status
login.php
README.md
```

SHA-256 :

```text
b8b3f87057c9689b2f9d861b67e9d23e685c8ab196577fe2cdbf562024af5c47  presence-extra.txt
```

La wordlist principale `/usr/share/dirb/wordlists/common.txt` (4 614 entrées) n'est ni remplacée ni modifiée. La seconde passe émet **19 requêtes, soit 0,41 %** de la passe principale ; après déduplication, elle apporte **17 entrées uniques** (0,37 %). Ce coût négligeable justifie l'exécution de la seconde passe pour tous les scans, y compris classiques, conformément à la décision demandée.

### 6.2 Licence

`presence-extra.txt` est une création originale Presence : 19 noms de chemins HTTP génériques, sans dérivation de `dirb/common.txt`, de la base Nikto ou d'une autre wordlist tierce. La notice `backend/scanners/wordlists/LICENSE.md` accorde la licence MIT et rappelle que la wordlist principale reste couverte par le paquet Debian `dirb`.

### 6.3 Fusion et déduplication

Les deux passes utilisent les mêmes threads, le même timeout de requête et la même exclusion soft-404. Les résultats sont fusionnés par chemin canonique (schéma retiré, query string et slash final normalisés, casse ignorée). La seconde passe reçoit le **reste du budget de l'étape**, jamais un nouveau timeout complet.

---

## 7. Modifications du pipeline

### 7.1 Étapes du palier 2

```python
_JOURNEY_STAGE2_STEPS = [
    {
        "key": "nuclei",
        "label": "Optimised Template Scan (Nuclei)",
        "scanner": "nuclei",
        "weight": 25,
        "profile": "scenario_c",
        "timeout_setting": "SCAN_JOURNEY_STAGE2_NUCLEI_TIMEOUT",
    },
    {
        "key": "gobuster",
        "label": "Directory Enumeration (Gobuster)",
        "scanner": "gobuster",
        "weight": 10,
        "timeout_setting": "SCAN_JOURNEY_STAGE2_GOBUSTER_TIMEOUT",
    },
]
```

`get_steps_for_scan(scan)` retourne ces étapes uniquement si `journey_stage == 2`. Tous les autres cas, y compris `journey_stage=NULL`, conservent `_SECURITY_STEPS` ou `_FULL_STEPS` selon le `scan_type`.

### 7.2 Budgets

| Paramètre | Valeur | Portée |
|---|---:|---|
| `SCAN_JOURNEY_STAGE2_TIME_BUDGET_SECONDS` | 360 | parcours, palier 2 uniquement |
| `SCAN_JOURNEY_STAGE2_NUCLEI_TIMEOUT` | 180 | étape Nuclei du palier 2 |
| `SCAN_JOURNEY_STAGE2_GOBUSTER_TIMEOUT` | 120 | étape Gobuster du palier 2 |
| `SCAN_TOTAL_TIME_BUDGET_SECONDS` | 540 | scans classiques, inchangé |

L'orchestrateur choisit le budget avec `_budget_settings_for_scan(scan)` et le timeout d'étape avec `_effective_timeout()`. Un dépassement produit un statut `partial` et conserve les résultats déjà obtenus ; aucun budget n'est rallongé pour masquer un partiel.

### 7.3 Isolation des templates

Le répertoire hôte `SCANNER_NUCLEI_SCENARIO_TEMPLATES_PATH` est monté dans le conteneur Nuclei à `/opt/scanner-templates` avec l'option Docker `readonly`. Le sandbox n'autorise ce montage que pour ce chemin de configuration, jamais pour un chemin fourni par une requête. Le profil standard continue d'utiliser `/nuclei-templates` et le catalogue complet.

---

## 8. Déduplication des findings

### 8.1 Principe

`backend/scans/services/finding_dedup.py` fournit :

```python
def finding_dedup_key(category, check_code, url):
    normalized_url = url.rstrip("/").lower()
    return (category, check_code, normalized_url)
```

La déduplication est activée **uniquement** quand `scan.journey_stage == 2`. Les scans classiques gardent le `bulk_create` historique et ne fusionnent rien.

### 8.2 Règles

1. Deux constats de contenu ne sont identiques que si `(catégorie, check_code, URL canonique)` est identique.
2. En cas de doublon de même source, la sévérité la plus élevée est conservée.
3. Une découverte Gobuster dont le chemin correspond à un constat de contenu déjà persisté est ajoutée dans `Finding.evidence["complementary_evidence"]` ; aucun second `Finding` n'est créé.
4. Si aucun constat de contenu ne correspond, le chemin Gobuster reste un constat distinct.
5. Les 10 en-têtes manquants ont des `check_code` distincts et ne sont jamais fusionnés entre eux.
6. `robots.txt` et `presence-robots-sensitive-paths` restent deux problèmes distincts (codes différents).
7. HSTS absent sur une cible HTTP reste un constat informatif ; il n'est pas transformé en vulnérabilité TLS et n'est pas dédupliqué avec testssl.

Les preuves complémentaires ne contiennent que le chemin, le code HTTP et la taille ; aucun corps de réponse, cookie ou secret n'est recopié.

---

## 9. Tests

### 9.1 Tests dédiés

Commande :

```bash
bash scripts/run_backend_tests.sh scans.tests.test_scenario_c_integration
```

Résultat :

```text
Found 21 test(s).
----------------------------------------------------------------------
Ran 21 tests in 8.355s

OK
```

Couverture :

- profil `scenario_c` : deux `-t`, sévérité, exclusions, `-duc` ;
- profils `standard`, `thorough`, `deep` : un seul `-t`, commande inchangée ;
- budget 180 s du profil et 360 s du palier 2 ;
- sélection `_JOURNEY_STAGE2_STEPS` sans Nikto, sélection classique avec Nikto ;
- priorité du timeout d'étape 120 s sur le timeout générique Gobuster ;
- seconde passe Gobuster, fusion, déduplication, budget restant ;
- absence de seconde passe quand `extra_wordlist` est vide ;
- montage `/opt/scanner-templates` en lecture seule ;
- clé canonique, fusion de preuve, conservation de la sévérité maximale ;
- 10 en-têtes distincts en scénario C, agrégation historique en profil classique ;
- `robots.txt` et chemins divulgués distincts ;
- scan classique conservant les deux sources.

### 9.2 Non-régression complète

Commande :

```bash
bash scripts/run_backend_tests.sh
```

Résultat :

```text
Ran 1037 tests in 936.755s

OK
```

1 037 = 1 016 tests existants + 21 nouveaux tests. Exit code 0. Aucun test existant n'a été modifié.

### 9.3 Contrôle des migrations

```text
$ docker compose run --rm --no-deps web python manage.py makemigrations --check --dry-run scans
No changes detected in app 'scans'
scans_makemigrations_exit=0
```

Aucune migration n'a été créée. Le contrôle global `makemigrations --check` signale un écart **préexistant et hors périmètre** dans `monitoring` (`alter field enabled on monitoringconfig`) ; ce lot n'a pas touché `monitoring/models.py` ni ses migrations et n'a pas créé la migration proposée.

---

## 10. Tests d'intégration sur le laboratoire

### 10.1 Périmètre et isolation

Cible : DVWA locale `http://10.42.10.5/`, réseau Docker `pentest-lab-core`. Aucun port public, aucune cible externe, aucune connexion aux bases Presence. Les conteneurs du laboratoire étaient déjà démarrés et n'ont pas été modifiés.

Le scan Django complet `journey_stage=2` contre cette adresse n'est pas possible : `core.security` bloque les IP privées/RFC1918 avant tout outil externe. C'est le comportement attendu du produit. L'intégration a donc été exécutée au niveau des deux outils, avec les assets et les paramètres du profil.

### 10.2 Nuclei

Commande exacte (réseau de laboratoire, montage lecture seule) :

```bash
docker run --rm --network pentest-lab-core \
  -v ".../templates:/opt/scanner-templates:ro" \
  --entrypoint nuclei projectdiscovery/nuclei:latest \
  -u http://10.42.10.5/ -jsonl -no-color -disable-update-check \
  -stats -stats-json -stats-interval 5 \
  -timeout 5 -retries 1 -bulk-size 10 -concurrency 20 \
  -rate-limit 60 -max-host-error 40 -ip-version 4 -type http \
  -exclude-tags dos,fuzz,fuzzing,intrusive,brute-force,default-login,credential-stuffing,token-spray \
  -t /opt/scanner-templates/selected -t /opt/scanner-templates/presence \
  -severity info,low,medium,high,critical -duc
```

Résultat :

```text
exit=0 duration=5s
jsonl_lines=15
templates_distinct=6
header_findings=10
templates=71
requests=202
errors=0
Scan completed in 2.872260292s. 15 matches found.
```

Détail des 15 résultats :

| Template | Nombre | Exemple |
|---|---:|---|
| `http-missing-security-headers` | 10 | 10 en-têtes absents sur `/login.php` |
| `robots-txt` | 1 | `robots.txt` accessible |
| `cookies-without-secure` | 1 | cookie sans attribut `Secure` |
| `readme-md` | 1 | `/README.md` accessible |
| `tech-detect` | 1 | technologie PHP |
| `presence-admin-login-surface` | 1 | page de connexion sur `/login.php` |

Les 10 constats d'en-têtes sont bien distincts dans le JSONL et sont conservés par la normalisation du palier 2.

### 10.3 Gobuster

Commande principale puis seconde passe, même image, même réseau :

```bash
gobuster dir -u http://10.42.10.5/ -w /usr/share/dirb/wordlists/common.txt -t 10 -q --timeout 10s --no-color
gobuster dir -u http://10.42.10.5/ -w /opt/scanner-wordlists/presence-extra.txt -t 10 -q --timeout 10s --no-color
```

Résultat :

```text
main_exit=0 extra_exit=0 total_duration=5s
main_paths=14
extra_paths=3
merged_unique_paths=16
```

Chemins complémentaires trouvés :

```text
/server-status   (Status: 403) [Size: 315]
/README.md       (Status: 200) [Size: 33392]
/login.php       (Status: 200) [Size: 1342]
```

La wordlist complémentaire apporte donc bien `README.md` et `login.php` sur DVWA, et `server-status` est déjà couvert par la passe principale ; la fusion élimine ce doublon.

### 10.4 Soft-404

Le laboratoire de cette session expose `/` sur `127.0.0.1:8091` avec une réponse 200 de 1 526 octets, mais les chemins inexistants y répondent 400 et le port 8090 n'était pas disponible. Ce montage ne reproduit donc pas la cible soft-404 du benchmark précédent. Aucun résultat négatif n'est revendiqué pour ce montage. La sonde soft-404 existante reste couverte par les tests unitaires et par le rapport QA du 2026-10-30 ; elle n'a pas été modifiée.

---

## 11. Image Docker

Commande :

```bash
docker compose build scanner-tools
```

Résultat : `build_exit=0`, image `presence-scanner-tools:2026-10-27`, identifiant `sha256:b94d19b98e32d36bfc29044ddece95018bee92ccaee3d27e46e77f71ff4cdc76`.

Vérification dans l'image :

```text
nmap         Nmap version 7.93
nikto        Nikto 2.6.1 (LW 2.5)
whatweb      WhatWeb version 0.5.5
testssl.sh   <no version output>
dnsrecon     DNSRecon version 1.1.3
gobuster     3.6
wordlist     /usr/share/dirb/wordlists/common.txt (4614 entries)
templates    /opt/scanner-templates/selected (61 templates)
templates    /opt/scanner-templates/presence (10 templates)
extra-list   /opt/scanner-wordlists/presence-extra.txt (19 entries)
check_exit=0
```

Nikto est toujours présent. `common.txt` est inchangée. La notice de licence de la wordlist est embarquée dans l'image.

---

## 12. Rétrocompatibilité

| Point | Preuve |
|---|---|
| Profil `standard` | Test : un seul `-t`, durée 150 s ; commande inchangée |
| Profils `thorough` et `deep` | Test : un seul `-t`, commande inchangée |
| Étapes classiques | `_SECURITY_STEPS` inchangé : `nmap, nikto, nuclei, whatweb, testssl, dnsrecon, gobuster, zap` |
| Budget classique | 540 s inchangé, test dédié |
| Persistance classique | Test : deux sources Nuclei + Gobuster produisent deux findings, sans fusion |
| Wordlist principale | `common.txt` non modifiée |
| Nikto | Toujours dans l'image et dans `_SECURITY_STEPS` |
| Modèles et migrations | Aucun changement de modèle, `scans` sans migration |
| Frontend / Celery / quotas | Aucun fichier modifié |

La seule différence volontaire pour les scans classiques est la seconde passe Gobuster de 19 chemins, décidée explicitement dans la mission ; elle ajoute 19 requêtes (0,41 %) et 17 entrées uniques (0,37 %) sans remplacer la liste principale.

---

## 13. Sécurité et absence de production

### 13.1 Scan anti-secrets

Les fichiers modifiés et créés ont été inspectés avec :

```bash
git diff --check
git diff -- <fichiers> | grep -nEi 'password|passwd|secret|api[_-]?key|token|BEGIN ... PRIVATE'
grep -RInE 'password|passwd|secret|api[_-]?key|token|BEGIN ... PRIVATE' <nouveaux fichiers>
```

Résultats : aucune clé, aucun mot de passe, aucun token réel. Les seules occurrences sont :

- `token-spray` dans la liste d'exclusion des tags ;
- `import secrets` dans le code de sonde Gobuster existant ;
- les mots `password`, `secret`, `token` dans les descriptions et expressions régulières des templates Presence.

### 13.2 Fichiers de production

```bash
git diff --name-only -- \
  backend/scans/models.py \
  backend/scans/migrations \
  backend/monitoring/models.py \
  backend/monitoring/migrations \
  frontend
```

Résultat : **aucune sortie**. Aucun modèle, aucune migration, aucun fichier frontend, aucune tâche Celery, aucun quota, aucune alerte, aucun scoring et aucun reaper n'a été modifié.

### 13.3 Déploiement

Aucun `docker compose up`, aucun redémarrage de service, aucun déploiement VPS, aucun scan externe. L'image a été construite localement pour vérification uniquement. Le code en cours d'exécution dans les conteneurs n'a pas été rechargé.

---

## 14. Limites connues

1. **Vérification end-to-end Django non exécutée sur DVWA** : le validateur SSRF refuse les adresses privées. Les outils ont été validés directement sur le laboratoire, pas le chemin Celery complet.
2. **Cible soft-404 indisponible** : le montage local de cette session ne reproduit pas le comportement 200 catch-all du benchmark ; aucun test négatif soft-404 supplémentaire n'est revendiqué.
3. **Couverture volontairement partielle** : 71 templates, pas le catalogue complet. `resolve_missing=False` empêche de conclure à la disparition d'un constat hors sélection.
4. **Nuclei reste opt-in** : le scanner exige `SCANNER_ADVANCED_SECURITY_ENABLED=true` et une cible autorisée. Le palier 2 d'un parcours devra respecter cette barrière.
5. **Seconde passe Gobuster pour tous les scans** : décision assumée, coût de 19 requêtes (0,41 %) et 17 entrées uniques (0,37 %), wordlist principale inchangée.
6. **Écart de migration préexistant dans `monitoring`** : détecté par `makemigrations --check`, non créé et hors périmètre C2.
7. **Image taguée `2026-10-27`** : la reconstruction réutilise le tag local existant ; une activation en production devra utiliser un tag/digest explicitement approuvé.

---

## 15. Décisions prises et justifications

| Décision | Justification |
|---|---|
| Profil `scenario_c` séparé | Évite toute modification des profils standard/thorough/deep et tout effet sur les scans classiques |
| Deux `-t` explicites | Permet de garder les 61 templates et les 10 contrôles Presence dans un seul processus, sans copier les templates dans le catalogue complet |
| Montage `readonly` | Les templates sont des entrées, pas des sorties ; le sandbox ne doit jamais pouvoir modifier le dépôt |
| Budget 360/180/120 | Compatible avec les mesures QA et avec la marge de 60 s du palier 2 |
| `extra_wordlist` pour tous les scans | Coût négligeable (19 requêtes, 0,41 %), gain de couverture, pas de remplacement de `common.txt` |
| Déduplication uniquement en `journey_stage=2` | Préserve exactement le comportement historique des scans classiques |
| 10 constats d'en-têtes distincts en scénario C | Répond au besoin d'actionnabilité ; l'agrégation historique reste en place pour les profils classiques |
| Aucune migration | Le schéma Lot A suffit ; aucune modification de `Scan`, `ScanJourney`, `Finding` ou `ScannerRun` |
| Statut `À VÉRIFIER MANUELLEMENT` | Une vérification end-to-end sur cible publique autorisée reste nécessaire avant activation |

---

## 16. Prochaines étapes

1. **Lot B** : `JourneyRunner`, admission, verrouillage, quotas atomiques. Le Lot C2 ne l'anticipe pas.
2. **Vérification end-to-end** : créer un scan `journey_stage=2` contre une cible publique explicitement autorisée, vérifier les deux étapes, les artefacts, les findings dédupliqués et le budget de 360 s.
3. **Lot C3** : retirer Nikto du palier 2 après validation du Lot B et du présent lot en conditions réelles.
4. **Lot C4** : étendre le scénario C aux scans classiques, après validation C3.
5. **Lot D/E/F** : API du parcours, reaper/métriques, frontend. Hors périmètre C2.

Aucune activation du scénario C en production n'est autorisée par ce rapport. Une autorisation explicite distincte reste nécessaire.

---

## 17. Preuves et artefacts

### 17.1 Sorties conservées

| Artefact | Chemin |
|---|---|
| Suite complète | `/tmp/c2-full-tests2.log` (sortie de la session de validation) |
| Tests ciblés | sortie `Ran 21 tests in 8.355s / OK` |
| Nucli DVWA | `/tmp/c2-nuclei-dvwa.jsonl`, `/tmp/c2-nuclei-dvwa.err` |
| Gobuster DVWA | `/tmp/c2-gobuster-main.txt`, `/tmp/c2-gobuster-extra.txt` |
| En-têtes DVWA | `/tmp/c2-headers-dvwa.jsonl` |
| Manifeste des templates | `backend/scanners/templates/selected-manifest.tsv` |
| Wordlist | `backend/scanners/wordlists/presence-extra.txt` |

Les fichiers `/tmp` sont des artefacts de session, non versionnés. Les éléments durables sont dans le dépôt.

### 17.2 Vérification SHA-256 des 61 templates

```text
manifest entries=61 mismatches=0
```

### 17.3 Contrôle Git

```bash
git status --short
git diff --check
git diff --name-only
```

Les modifications suivies sont limitées aux fichiers C2 listés au §2.1. Les fichiers non suivis préexistants du dépôt (rapports QA antérieurs, archives, journaux, sauvegardes de frontend) ne font pas partie du commit C2 et n'ont pas été ajoutés.

### 17.4 Validation finale

```text
Suite backend : 1037 tests, OK, exit 0
Tests C2      : 21 tests, OK, exit 0
Nuclei        : All templates validated successfully (2 répertoires), exit 0
Image         : présence-scanner-tools:2026-10-27, check-tools exit 0
Migrations    : scans, no changes detected
Production    : aucun déploiement, aucun redémarrage, aucune migration
```
