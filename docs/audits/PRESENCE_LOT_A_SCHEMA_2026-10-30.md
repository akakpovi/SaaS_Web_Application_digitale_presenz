# Presence — Lot A : schéma `ScanJourney` et champs additifs sur `Scan`

**Date :** 2026-10-30
**Périmètre :** schéma de données et migrations uniquement.
**Statut final :** VALIDÉ TECHNIQUEMENT.

## 1. Périmètre réellement modifié

Fichiers modifiés ou créés :

- `SaaS_Web_Application_digitale_presenz_v2/backend/scans/models.py`
- `SaaS_Web_Application_digitale_presenz_v2/backend/config/settings/base.py`
- `SaaS_Web_Application_digitale_presenz_v2/backend/scans/migrations/0008_scan_journey_stage_scan_quota_charged_scanjourney_and_more.py`
- `SaaS_Web_Application_digitale_presenz_v2/backend/scans/tests/test_models.py`
- `docs/audits/PRESENCE_LOT_A_SCHEMA_2026-10-30.md`

Aucun endpoint, sérialiseur, URL, tâche Celery, service, orchestrateur ou
transition de `Scan` n'a été modifié. Le diff ne contient aucune ligne
touchant `Scan.status`, `Scan.scan_type`, `_TRANSITIONS` ou
`transition_to()`.

Preuve du contrôle ciblé :

```text
$ git diff -U0 -- .../scans/models.py | grep -E '^[+-].*(status|scan_type|_TRANSITIONS|transition_to|class Scan)'
+class ScanJourney(models.Model):
+    terminal status machine unchanged.
```

Les deux seules occurrences sont l'ajout de la classe `ScanJourney` et la
phrase de docstring qui confirme que la machine à états de `Scan` reste
inchangée. Aucune ligne `Scan.status`, `scan_type` ou `_TRANSITIONS` n'est
apparaît dans le diff.

## 2. Modèle `ScanJourney`

Ajouté dans `scans/models.py:16-71`.

- `JourneyState` : `TextChoices` avec `running`, `awaiting_confirmation`,
  `completed`, `partial`, `failed`, `expired`, `cancelled`.
- `website` : FK `websites.Website`, `on_delete=CASCADE`,
  `related_name="scan_journeys"`.
- `requested_by` : FK vers `AUTH_USER_MODEL`, `on_delete=SET_NULL`,
  `null=True`, `blank=True`.
- `state` : `CharField(max_length=24)`, défaut `running`.
- `current_stage` : `PositiveSmallIntegerField(default=1)`.
- `total_stages` : `PositiveSmallIntegerField(default=2)`.
- `expires_at` : `DateTimeField(null=True, blank=True)`.
- `created_at` / `updated_at` : horodatages automatiques.
- `Meta.ordering = ["-created_at"]`.
- `__str__` : `Journey <id> - <website_id> [<state>]`.

Contraintes et index :

- `unique_active_journey_per_website` : index unique partiel sur `website`
  lorsque `state` vaut `running` ou `awaiting_confirmation`.
- `journey_stage_range` : `current_stage >= 1` et
  `current_stage <= total_stages`.
- index `(website, created_at)`.
- index `(state, expires_at)`.

## 3. Champs additifs sur `Scan`

Ajoutés dans `scans/models.py:113-121`, sans toucher au reste du modèle :

- `journey` : FK vers `ScanJourney`, `on_delete=CASCADE`, `null=True`,
  `blank=True`, `related_name="stages"`.
- `journey_stage` : `PositiveSmallIntegerField(null=True, blank=True)`.
- `quota_charged` : `BooleanField(default=True)`.

Contraintes et index ajoutés :

- `unique_scan_per_journey_stage` : index unique partiel sur
  `(journey, journey_stage)` lorsque `journey` n'est pas NULL.
- `scan_journey_stage_consistent` : soit `journey` et `journey_stage` sont
  tous deux NULL, soit `journey` est renseigné et `journey_stage >= 1` avec
  `journey_stage IS NOT NULL`.
- index `(quota_charged, created_at)`.

### 3.1 Correction effectuée pendant le lot

La première version de la contrainte s'écrivait :

```python
Q(journey__isnull=False, journey_stage__gte=1)
```

En SQL, `NULL >= 1` vaut `NULL`, et PostgreSQL accepte un `CHECK` qui
évalue à `NULL`. Le test `test_scan_with_journey_requires_a_stage` a donc
échoué :

```text
FAIL: test_scan_with_journey_requires_a_stage
AssertionError: IntegrityError not raised
Ran 12 tests in 14.432s
FAILED (failures=1)
```

La contrainte a été corrigée en ajoutant explicitement
`journey_stage__isnull=False` dans la seconde branche. La migration 0008 a
été corrigée avant commit, puis l'état local a été rembobiné et réappliqué.
Le test repasse.

## 4. Réglage TTL

Ajouté dans `config/settings/base.py:873-875` :

```python
# A scan journey waiting for the user's confirmation expires after this delay,
# so an abandoned journey never keeps the per-website active-journey slot.
SCAN_JOURNEY_TTL_HOURS = 24
```

Ce réglage n'est encore lu par aucun service : le lot A ne fait que le
déclarer. Son exploitation appartient au lot B/E.

## 5. Migration

### 5.1 Sortie de génération

```text
$ python manage.py check && python manage.py makemigrations scans
System check identified no issues (0 silenced).
Migrations for 'scans':
  scans/migrations/0008_scan_journey_stage_scan_quota_charged_scanjourney_and_more.py
    + Add field journey_stage to scan
    + Add field quota_charged to scan
    + Create model ScanJourney
    + Add field journey to scan
    + Create index scans_scan_quota_c_8c5075_idx on field(s) quota_charged, created_at of model scan
    + Create constraint unique_scan_per_journey_stage on model scan
    + Create constraint scan_journey_stage_consistent on model scan
    + Create index scans_scanj_website_5af927_idx on field(s) website, created_at of model scanjourney
    + Create index scans_scanj_state_58ce0c_idx on field(s) state, expires_at of model scanjourney
    + Create constraint unique_active_journey_per_website on model scanjourney
    + Create constraint journey_stage_range on model scanjourney
```

Aucune opération `RemoveField`, `DeleteModel` ou `AlterField` n'est présente.
La migration est purement additive : deux `AddField`, un `CreateModel`, deux
`AddIndex`, deux `AddConstraint` côté `ScanJourney`, un `AddConstraint` et un
`AddIndex` côté `Scan`.

### 5.2 Contenu intégral du fichier 0008

```python
# Generated by Django 5.2.18 on 2026-10-30 06:26

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scans', '0007_scan_partial_status'),
        ('websites', '0006_website_websites_we_organiz_d596c4_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='scan',
            name='journey_stage',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='scan',
            name='quota_charged',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name='ScanJourney',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(choices=[('running', 'Running'), ('awaiting_confirmation', 'Awaiting confirmation'), ('completed', 'Completed'), ('partial', 'Partial'), ('failed', 'Failed'), ('expired', 'Expired'), ('cancelled', 'Cancelled')], default='running', max_length=24)),
                ('current_stage', models.PositiveSmallIntegerField(default=1)),
                ('total_stages', models.PositiveSmallIntegerField(default=2)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('website', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scan_journeys', to='websites.website')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='scan',
            name='journey',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='stages', to='scans.scanjourney'),
        ),
        migrations.AddIndex(
            model_name='scan',
            index=models.Index(fields=['quota_charged', 'created_at'], name='scans_scan_quota_c_8c5075_idx'),
        ),
        migrations.AddConstraint(
            model_name='scan',
            constraint=models.UniqueConstraint(condition=models.Q(('journey__isnull', False)), fields=('journey', 'journey_stage'), name='unique_scan_per_journey_stage'),
        ),
        migrations.AddConstraint(
            model_name='scan',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('journey__isnull', True), ('journey_stage__isnull', True)), models.Q(('journey__isnull', False), ('journey_stage__gte', 1), ('journey_stage__isnull', False)), _connector='OR'), name='scan_journey_stage_consistent'),
        ),
        migrations.AddIndex(
            model_name='scanjourney',
            index=models.Index(fields=['website', 'created_at'], name='scans_scanj_website_5af927_idx'),
        ),
        migrations.AddIndex(
            model_name='scanjourney',
            index=models.Index(fields=['state', 'expires_at'], name='scans_scanj_state_58ce0c_idx'),
        ),
        migrations.AddConstraint(
            model_name='scanjourney',
            constraint=models.UniqueConstraint(condition=models.Q(('state__in', ['running', 'awaiting_confirmation'])), fields=('website',), name='unique_active_journey_per_website'),
        ),
        migrations.AddConstraint(
            model_name='scanjourney',
            constraint=models.CheckConstraint(condition=models.Q(('current_stage__gte', 1), ('current_stage__lte', models.F('total_stages'))), name='journey_stage_range'),
        ),
    ]
```

### 5.3 SQL réellement généré

```text
$ python manage.py sqlmigrate scans 0008
BEGIN;
ALTER TABLE "scans_scan" ADD COLUMN "journey_stage" smallint NULL CHECK ("journey_stage" >= 0);
ALTER TABLE "scans_scan" ADD COLUMN "quota_charged" boolean DEFAULT true NOT NULL;
ALTER TABLE "scans_scan" ALTER COLUMN "quota_charged" DROP DEFAULT;
CREATE TABLE "scans_scanjourney" ("id" bigint NOT NULL PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY, "state" varchar(24) NOT NULL, "current_stage" smallint NOT NULL CHECK ("current_stage" >= 0), "total_stages" smallint NOT NULL CHECK ("total_stages" >= 0), "expires_at" timestamp with time zone NULL, "created_at" timestamp with time zone NOT NULL, "updated_at" timestamp with time zone NOT NULL, "requested_by_id" bigint NULL, "website_id" bigint NOT NULL);
ALTER TABLE "scans_scan" ADD COLUMN "journey_id" bigint NULL CONSTRAINT "scans_scan_journey_id_2fc188b4_fk_scans_scanjourney_id" REFERENCES "scans_scanjourney"("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "scans_scan_quota_c_8c5075_idx" ON "scans_scan" ("quota_charged", "created_at");
CREATE UNIQUE INDEX "unique_scan_per_journey_stage" ON "scans_scan" ("journey_id", "journey_stage") WHERE "journey_id" IS NOT NULL;
ALTER TABLE "scans_scan" ADD CONSTRAINT "scan_journey_stage_consistent" CHECK ((("journey_id" IS NULL AND "journey_stage" IS NULL) OR ("journey_id" IS NOT NULL AND "journey_stage" >= 1 AND "journey_stage" IS NOT NULL)));
CREATE INDEX "scans_scanj_website_5af927_idx" ON "scans_scanjourney" ("website_id", "created_at");
CREATE INDEX "scans_scanj_state_58ce0c_idx" ON "scans_scanjourney" ("state", "expires_at");
CREATE UNIQUE INDEX "unique_active_journey_per_website" ON "scans_scanjourney" ("website_id") WHERE "state" IN ('running', 'awaiting_confirmation');
ALTER TABLE "scans_scanjourney" ADD CONSTRAINT "journey_stage_range" CHECK (("current_stage" >= 1 AND "current_stage" <= ("total_stages")));
ALTER TABLE "scans_scanjourney" ADD CONSTRAINT "scans_scanjourney_requested_by_id_4e86c156_fk_accounts_user_id" FOREIGN KEY ("requested_by_id") REFERENCES "accounts_user" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "scans_scanjourney" ADD CONSTRAINT "scans_scanjourney_website_id_39671f84_fk_websites_website_id" FOREIGN KEY ("website_id") REFERENCES "websites_website" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "scans_scanjourney_requested_by_id_4e86c156" ON "scans_scanjourney" ("requested_by_id");
CREATE INDEX "scans_scanjourney_website_id_39671f84" ON "scans_scanjourney" ("website_id");
CREATE INDEX "scans_scan_journey_id_2fc188b4" ON "scans_scan" ("journey_id");
COMMIT;
```

### 5.4 Application sur la base locale

```text
$ python manage.py migrate --noinput
Operations to perform:
  Apply all migrations: ... scans ...
Running migrations:
  Applying scans.0008_scan_journey_stage_scan_quota_charged_scanjourney_and_more... OK
```

La migration a été appliquée après un rembobinage `migrate scans 0007`
destiné à corriger la contrainte avant commit. Le rembobinage ne touche que
les objets créés par ce lot : aucune donnée métier existante n'est modifiée.

## 6. Compatibilité des données existantes

État de la base locale après migration :

```text
scans_total= 23
journeys_total= 0
scans_with_journey= 0
scans_with_stage= 0
scans_not_quota_charged= 0
sample= [(1, None, None, True), (2, None, None, True), (3, None, None, True), (4, None, None, True), (5, None, None, True)]
```

Le nombre actuel est 23, et non 62 : les scans de test ont été nettoyés lors
du lot documenté dans `PRESENCE_TEST_DATA_ACCOUNTS_2026-10-28.md`. Aucun
backfill n'est nécessaire : `journey` et `journey_stage` sont NULL, et
`quota_charged` vaut `True` sur tous les scans existants.

## 7. Tests unitaires du modèle

Fichier créé : `scans/tests/test_models.py` (12 tests).

Couverture :

- création valide d'un parcours et d'un scan enfant ;
- valeurs par défaut (`state=running`, `current_stage=1`, `total_stages=2`) ;
- `quota_charged=True` par défaut, y compris sans parcours ;
- rejet d'un second parcours actif sur le même site ;
- un parcours terminé ne bloque pas un nouveau parcours ;
- rejet de deux scans pour le même `(journey, journey_stage)` ;
- rejet d'un scan avec `journey` mais sans `journey_stage` ;
- rejet d'un scan avec `journey_stage` mais sans `journey` ;
- rejet de `current_stage > total_stages` et de `current_stage < 1` ;
- acceptation du dernier palier ;
- suppression en cascade des scans enfants avec le parcours.

Sortie réelle :

```text
$ bash scripts/run_backend_tests.sh scans.tests.test_models
Found 12 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
...
Ran 12 tests in 12.257s

OK
Destroying test database for alias 'default'...
EXIT=0
```

## 8. Suite complète de non-régression

```text
$ bash scripts/run_backend_tests.sh
...
Ran 1016 tests in 897.640s

OK
Destroying test database for alias 'default'...
EXIT=0
```

Aucun test existant n'a été modifié. Aucun échec, aucune erreur, aucun test
ignoré supplémentaire.

## 9. Absence de dérive de migration

```text
$ python manage.py makemigrations --check --dry-run
No changes detected
EXIT=0
```

```text
$ python manage.py showmigrations scans
scans
 [X] 0001_initial
 [X] 0002_scan_add_pending_status
 [X] 0003_scan_guest_fields
 [X] 0004_finding_scannerrun_remove_scan_scan_status_valid_and_more
 [X] 0005_add_external_security_categories
 [X] 0006_scannerrun_partial_status
 [X] 0007_scan_partial_status
 [X] 0008_scan_journey_stage_scan_quota_charged_scanjourney_and_more
```

```text
$ python manage.py migrate --plan
Planned operations:
  No planned migration operations.
```

## 10. Preuves SQL des contraintes et index

Contraintes lues dans `pg_constraint` :

```text
journey_stage_range | CHECK (((current_stage >= 1) AND (current_stage <= total_stages)))
scan_health_score_range | CHECK (((health_score IS NULL) OR ((health_score >= 0) AND (health_score <= 100))))
scan_journey_stage_consistent | CHECK ((((journey_id IS NULL) AND (journey_stage IS NULL)) OR ((journey_id IS NOT NULL) AND (journey_stage >= 1) AND (journey_stage IS NOT NULL))))
scan_status_valid | CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'queued'::character varying, 'running'::character varying, 'completed'::character varying, 'partial'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[])))
```

Index lus dans `pg_indexes` :

```text
unique_scan_per_journey_stage | CREATE UNIQUE INDEX unique_scan_per_journey_stage ON public.scans_scan USING btree (journey_id, journey_stage) WHERE (journey_id IS NOT NULL)
unique_active_journey_per_website | CREATE UNIQUE INDEX unique_active_journey_per_website ON public.scans_scanjourney USING btree (website_id) WHERE ((state)::text = ANY ((ARRAY['running'::character varying, 'awaiting_confirmation'::character varying])::text[]))
scans_scan_quota_c_8c5075_idx | CREATE INDEX scans_scan_quota_c_8c5075_idx ON public.scans_scan USING btree (quota_charged, created_at)
scans_scanj_website_5af927_idx | CREATE INDEX scans_scanj_website_5af927_idx ON public.scans_scanjourney USING btree (website_id, created_at)
scans_scanj_state_58ce0c_idx | CREATE INDEX scans_scanj_state_58ce0c_idx ON public.scans_scanjourney USING btree (state, expires_at)
```

Les index uniques partiels sont bien créés par PostgreSQL ; Django les
représente comme des `UniqueConstraint` conditionnelles et non comme des
contraintes `pg_constraint` classiques.

## 11. Scan anti-secrets des fichiers du lot

Scan exécuté avant commit sur les cinq fichiers du lot (modèle, settings,
migration, tests, ce rapport). `rg` n'étant pas installé sur l'hôte, le scan
a été réalisé par un script Python en lecture seule, avec les motifs à haute
signature suivants : clé privée PEM, URL PostgreSQL/Redis avec mot de passe,
jetons `sk-`, `ghp_`, `xox*`, `AIza*`, `Bearer`, et affectations littérales
`AKA_AI_API_KEY`, `SECRET_KEY` ou `PASSWORD`.

Résultat : `AUCUNE_OCCURRENCE_SIGNATURE_SECRETE` (0 occurrence).

Le mot de passe de fixture `CorrectHorseBattery1!` du test est le même motif
que dans les tests existants ; ce n'est pas un secret d'exploitation, il
n'est utilisé que pour créer un utilisateur éphémère dans la base de test.

## 12. Commit et push

Message de commit :

```text
Lot A: add ScanJourney model and additive Scan fields for progressive scan journeys
```

Hash du commit de mise en œuvre : fourni dans la réponse de clôture. Un
fichier ne peut pas contenir le hash du commit qui le contient ; le hash est
vérifiable par `git log -1 --format=%H`.

Vérification du remote avant push :

```text
origin  https://github.com/akakpovi/SaaS_Web_Application_digitale_presenz.git (fetch)
origin  https://github.com/akakpovi/SaaS_Web_Application_digitale_presenz.git (push)
```

Après push, la vérification indépendante est effectuée avec
`git ls-remote origin refs/heads/main` et sa sortie exacte est fournie dans
la réponse de clôture.

## 13. Limites et points reportés aux lots suivants

1. **Aucun producteur de `expires_at`.** Le champ existe et
   `SCAN_JOURNEY_TTL_HOURS=24` est déclaré, mais aucun service ne calcule
   l'expiration tant que le lot B n'existe pas.
2. **Aucun endpoint de création ou d'avancement.** Le lot A ne permet pas
   encore de créer un parcours via l'API ni de déclencher le palier 2.
3. **Aucune lecture de `quota_charged`.** Le champ est stocké mais
   `assert_can_scan()` et `scans_used_this_month()` ne le lisent pas encore ;
   l'option de quota A sera appliquée au lot B/D.
4. **Pas de contrainte globale sur les scans actifs.** La contrainte
   `unique_active_journey_per_website` protège les parcours, pas les scans
   classiques ; le verrou applicatif inter-sites reste à implémenter au lot B.
5. **`journey_stage` n'a pas de borne supérieure liée à `total_stages`.**
   La cohérence parcours/palier est garantie par le service et par
   `journey_stage_range` sur le parcours, pas par une contrainte croisée
   entre les deux tables.
6. **Suppression en cascade.** Supprimer un `ScanJourney` supprime ses scans
   enfants ; c'est le comportement demandé par `on_delete=CASCADE`, mais il
   devra être pris en compte par le reaper et par toute future API de
   suppression.
7. **`expires_at` est nullable.** Un parcours peut rester sans expiration
   tant que le lot B ne l'a pas renseignée ; le reaper devra traiter ce cas
   explicitement.

## 14. Conclusion

Le schéma du lot A est en place, additif, appliqué et couvert par 12 tests
dédiés. La suite complète de 1016 tests passe. Aucun endpoint, service,
worker ou transition de scan n'a été touché. Le lot B peut démarrer sur cette
base, en particulier pour le service d'admission, le claim atomique et
l'orchestrateur à sous-ensemble d'étapes.

**Statut final : VALIDÉ TECHNIQUEMENT.**
