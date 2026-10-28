# Connecteurs sociaux — socle OAuth et coffre de jetons

**Date :** 25 octobre 2026  
**Périmètre :** Phase 2, fondations serveur uniquement — aucune route externe, aucun flux OAuth réel, aucune publication.  
**Dépôt réel :** `~/Schreibtisch/SaaS_Web_Application_digitale_presenz` (le chemin `..._presenz_v2` cité dans la demande n'existe pas en tant que dépôt séparé ; le backend est dans `SaaS_Web_Application_digitale_presenz_v2/backend`).

---

## 1. Résultat

| Élément | État |
|---|---|
| Application Django `integrations` | Créée et enregistrée dans `INSTALLED_APPS` |
| Modèles `OAuthConnection`, `OAuthState` | Créés, migration initiale incluse |
| Coffre AES-256-GCM en enveloppe | Implémenté, KEK uniquement côté environnement |
| DEK par organisation | Implémentée, versionnée et emballée par la KEK |
| AAD liée au tenant | Implémentée : organisation + fournisseur + compte + champ |
| Commande `rotate_connector_keys` | Implémentée (rotation KEK seule ou KEK + DEK) |
| Jeu de données mockées | Fonction + commande `seed_connector_mock_data` |
| Sérialiseurs sans jetons | `OAuthConnectionSerializer`, `OAuthStateSerializer` |
| Tests dédiés | **22 tests, OK** |
| Suite backend complète | **645 tests, OK** |
| `makemigrations --check` | Aucun changement détecté |
| Démarrage sans KEK | Refusé par le system check `integrations.E001` et par les entrypoints WSGI/ASGI |

Aucune route API, aucun callback OAuth et aucun envoi de jeton vers un fournisseur n'a été ajouté.

---

## 2. Modélisation

### `OAuthConnection`

Champs demandés :

- `provider` : Google, LinkedIn, Facebook, Instagram, Twitter/X.
- `external_account_id`.
- `access_token_ciphertext`, `refresh_token_ciphertext` : uniquement du texte chiffré.
- `status` : `active`, `expired`, `revoked`, `error`.
- `expires_at` : nullable pour les fournisseurs sans expiration connue.
- `key_version` : version de DEK utilisée pour cette ligne.

Champs de service ajoutés : `id` UUID, `organization`, `created_at`, `updated_at`.

Contraintes :

- unicité `(organization, provider, external_account_id)` ;
- index `(organization, provider, status)` et `(status, expires_at)`.

`__str__` n'expose ni jeton clair ni texte chiffré.

### `OAuthState`

Champs demandés : `state_hash`, `organization`, `user`, `provider`, `expires_at`.

Le hash SHA-256 est unique. Le state clair n'est jamais persisté. `created_at` est ajouté pour l'audit. Le modèle ne contient volontairement aucune méthode de consommation : le futur endpoint de callback devra vérifier le hash, l'expiration et l'usage unique dans une transaction.

### `OrganizationDataKey`

Table technique nécessaire à l'enveloppe :

- `organization`, `version`, `wrapped_dek`, `kek_version`, `is_active`, `created_at`, `rotated_at`.

Contraintes :

- unicité `(organization, version)` ;
- une seule DEK active par organisation via une contrainte partielle PostgreSQL ;
- les anciennes versions restent disponibles pour déchiffrer les lignes non encore migrées ou pour un rollback.

---

## 3. Chiffrement en enveloppe

### Format

Chaque secret est stocké sous la forme :

```text
v1.<nonce-base64>.<ciphertext+tag-base64>
```

La DEK est stockée dans `OrganizationDataKey.wrapped_dek`, elle-même chiffrée par la KEK avec le même format. Le tag GCM est inclus dans le ciphertext et authentifié au déchiffrement.

### Hiérarchie des clés

1. **KEK** : lue dans `CONNECTOR_KEK_V1`, `CONNECTOR_KEK_V2`, etc. Elle ne touche jamais la base.
2. **DEK** : 32 octets aléatoires générés par organisation, stockés uniquement emballés par la KEK active.
3. **Jetons** : chiffrés par la DEK de l'organisation.

Une fuite de la base seule ne donne donc ni les DEK ni les jetons. Une fuite de l'environnement seul ne donne pas les ciphertexts.

### AAD

L'AAD canonique est :

```text
org=<uuid>|provider=<provider>|account=<external_account_id>|field=<access_token|refresh_token>
```

Les composants sont encodés en pourcentage pour éviter toute ambiguïté de séparateur. Cela empêche :

- l'organisation B de déchiffrer un ciphertext de l'organisation A ;
- d'échanger un access token et un refresh token ;
- de déplacer un ciphertext vers un autre compte du même fournisseur.

L'AAD d'emballage de la DEK lie en plus `version` et `kek_version` :

```text
org=<uuid>|dek=<version>|kek=<kek_version>
```

### Journalisation

`integrations.crypto` ne journalise que :

- l'identifiant d'organisation ;
- le fournisseur ;
- l'identifiant de compte externe ;
- le champ concerné ;
- la version de clé.

Aucun jeton clair, aucun ciphertext, aucune clé n'est loggé. Les exceptions de déchiffrement sont génériques et n'incluent jamais l'enveloppe.

### Démarrage sans KEK

`IntegrationsConfig.ready()` enregistre un system check. Sans KEK valide, `manage.py check`, `runserver`, `migrate` et les commandes de gestion échouent avec :

```text
(integrations.E001) No connector KEK is configured; set CONNECTOR_KEK_V1.
```

Les entrypoints `config/wsgi.py` et `config/asgi.py` appellent aussi explicitement `assert_connector_kek_configured()` : les serveurs WSGI/ASGI ne lancent pas les system checks Django, donc gunicorn et uvicorn refusent eux aussi de démarrer sans clé.

La KEK doit décoder exactement 32 octets en base64. `CONNECTOR_KEK_ACTIVE_VERSION` doit référencer une version présente.

---

## 4. Rotation

### Rotation de l'emballage KEK uniquement

```bash
python manage.py rotate_connector_keys --kek-version 2
```

- réemballe toutes les DEK, y compris les versions historiques ;
- ne touche pas aux ciphertexts des jetons ;
- ne change pas `OAuthConnection.key_version` ;
- met à jour `OrganizationDataKey.kek_version` et `rotated_at`.

La KEK V1 doit rester configurée pendant l'opération. Elle peut être retirée après vérification que toutes les DEK sont en V2. Une fois la rotation terminée, mettre `CONNECTOR_KEK_ACTIVE_VERSION` sur la nouvelle version puis redémarrer, afin que les nouvelles DEK utilisent bien la KEK cible.

### Rotation KEK + DEK

```bash
python manage.py rotate_connector_keys --kek-version 2 --rotate-dek --batch-size 200
```

Pour chaque organisation, dans une transaction :

1. verrouille l'organisation et ses DEK ;
2. crée une nouvelle DEK de version `N+1`, emballée par la KEK cible ;
3. déchiffre chaque connexion avec sa DEK d'origine ;
4. rechiffre les jetons avec la nouvelle DEK ;
5. bascule le marqueur actif seulement après la dernière ligne ;
6. réemballe les anciennes DEK sous la KEK cible.

En cas d'échec, la transaction restaure l'ancienne DEK active et les anciens ciphertexts.

### Jeu de données mockées

```bash
python manage.py seed_connector_mock_data \
  --organizations 5 \
  --connections-per-org 12 \
  --prefix loadtest
```

La fonction `seed_mock_connector_data()` retourne les jetons synthétiques au caller de test uniquement. Ils ne sont jamais journalisés. La commande affiche seulement le nombre de lignes créées.

---

## 5. Tests de sécurité

Commande exécutée :

```bash
bash scripts/run_backend_tests.sh integrations
```

Résultat :

```text
Ran 22 tests in 58.659s

OK
```

Couverture explicite :

| Exigence | Test |
|---|---|
| Chiffrement / déchiffrement complets | `EnvelopeEncryptionTests.test_encrypt_decrypt_round_trip` |
| Nonce aléatoire | `test_same_plaintext_uses_a_fresh_nonce` |
| Détection d'altération | `test_tampered_ciphertext_fails_closed` |
| Mauvaise clé | `test_wrong_key_fails_closed_without_leaking_secret` |
| AAD inter-organisations | `AADBindingTests.test_organization_b_cannot_open_organization_a_ciphertext` |
| AAD inter-champs | `test_access_and_refresh_ciphertexts_are_not_interchangeable` |
| Copie de ciphertext entre tenants | `test_copied_ciphertext_fails_in_another_tenant_row` |
| Sérialiseur sans jeton | `test_serializer_omits_ciphertext_and_plaintext` |
| Sérialiseur de state sans hash | `test_oauth_state_serializer_omits_state_hash` |
| Logs sans jeton/ciphertext | `test_logs_never_contain_plaintext_or_ciphertext` |
| Absence de KEK | `KeyConfigurationTests.test_missing_kek_blocks_startup` |
| KEK de mauvaise taille | `test_wrong_key_length_blocks_startup` |
| Version active absente | `test_active_version_must_exist` |
| Base64 invalide | `test_invalid_base64_key_blocks_startup` |
| Rotation sur 60 connexions | `test_rotate_dek_over_mock_dataset_keeps_every_token_readable` |
| Rotation KEK seule | `test_kek_only_rotation_keeps_ciphertext_and_dek_version` |
| Version KEK inconnue | `test_unknown_kek_version_aborts_without_touching_data` |
| Commande de seed | `test_seed_command_creates_expected_rows` |

Vérifications complémentaires :

```text
python manage.py makemigrations --check --dry-run
→ No changes detected

python manage.py check  (sans KEK)
→ SystemCheckError: integrations.E001
→ exit status 1

python -c "import config.wsgi"  (sans KEK)
→ ConnectorKeyConfigurationError: No connector KEK is configured
→ exit status 1

python -c "import config.wsgi"  (KEK présente)
→ wsgi import ok
→ exit status 0
```

Suite complète :

```text
Ran 645 tests in 1089.208s

OK
```

---

## 6. Fichiers ajoutés / modifiés

Ajoutés :

- `integrations/models.py`
- `integrations/services/encryption.py`
- `integrations/services/rotation.py`
- `integrations/services/mock_data.py`
- `integrations/serializers.py`
- `integrations/checks.py`
- `integrations/apps.py`
- `integrations/migrations/0001_initial.py`
- `integrations/management/commands/rotate_connector_keys.py`
- `integrations/management/commands/seed_connector_mock_data.py`
- `integrations/tests/` (22 tests)
- ce rapport

Modifiés :

- `config/settings/base.py` : parsing `CONNECTOR_KEK_V*`, ajout de l'app.
- `config/settings/test.py` : KEK de test déterministes V1/V2.
- `config/wsgi.py` et `config/asgi.py` : refus de démarrer sans KEK valide.
- `.env.example` : documentation et placeholder de la KEK.

Le fichier local `backend/.env` (ignoré par Git) a reçu une KEK de développement générée aléatoirement, sans affichage de sa valeur, afin que le stack local puisse démarrer après reconstruction. Aucun secret de production n'a été créé ni versionné.

---

## 7. Limites et suite

- Aucun endpoint OAuth, callback, refresh ou publication n'est encore exposé.
- Aucun test contre les vrais fournisseurs Google/LinkedIn : les callbacks, scopes et consentements seront validés à l'étape suivante.
- Le state est modélisé mais pas encore consommé : le futur callback devra implémenter la vérification transactionnelle et l'usage unique.
- La rotation DEK est transactionnelle par organisation. Pour des volumes très importants (dizaines de milliers de connexions par organisation), il faudra une rotation par lots reprenable avec un état de migration explicite.
- La KEK doit être fournie par le gestionnaire de secrets de production (Docker secret, Vault, KMS, variable d'environnement injectée). Elle ne doit jamais être commitée, loggée ou stockée en base.
- Les sauvegardes de la base restent sensibles : elles contiennent les ciphertexts et les DEK emballées. Sans la KEK elles restent inexploitables, mais la KEK doit être sauvegardée séparément.

Prochaine étape recommandée : endpoints `connect` / `callback` avec state à usage unique, PKCE, scopes minimaux et tests d'intégration multi-tenant, puis premier connecteur LinkedIn en sandbox.
