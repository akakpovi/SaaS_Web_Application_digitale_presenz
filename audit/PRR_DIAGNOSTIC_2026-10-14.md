# Production Readiness Review — Diagnostic complet

Date : 2026-10-14
Dépôt : `~/Schreibtisch/SaaS_Web_Application_digitale_presenz` (branche `main`)
Périmètre : intégration produit, viabilité commerciale, alerting/e-mails, conformité & opérations.
Méthode : inspection du code + interrogation de la pile réellement déployée (PostgreSQL live).

---

## VERDICT

# ❌ NO-GO — mise en production **commerciale** immédiate

Le socle technique (pipeline de scan, sécurité IDOR/SSRF, TLS) est solide, mais **le produit n'est
pas intégré de bout en bout et le modèle commercial n'est pas opérationnel**. En l'état :

- Le frontend est une **maquette statique** : aucun parcours produit n'appelle l'API (seule
  l'authentification est branchée).
- La **facturation n'existe pas** (aucun prestataire de paiement, plans non amorcés, quotas non
  appliqués).
- Le **moteur d'alerte est dormant** (`detect_alerts` jamais déclenché) et les **e-mails partent
  dans la console**, pas vers un serveur SMTP.
- **Aucune fonction RGPD** (suppression/export de compte) et **aucune sauvegarde automatisée** ni
  observabilité applicative.

Autorisé au mieux : **bêta privée fermée** (allowlist, plan gratuit, sans promesse de facturation ni
d'alertes), après correctifs d'intégration minimaux. Lancement commercial : **non**.

---

## 1. Intégration Produit (Frontend ↔ API) — ❌ ÉCHEC

**Ce qui existe (bon)** : une couche API propre côté frontend — `api/client.ts` (Bearer JWT,
rafraîchissement du token, gestion 401), `api/endpoints.ts` (toutes les routes), `contexts/AuthContext.tsx`.

**Ce qui manque** : cette couche n'est utilisée **que pour l'authentification**.
Preuve — seuls appels API réels du dépôt :

```
contexts/AuthContext.tsx:42  api.get(endpoints.auth.me)
contexts/AuthContext.tsx:73  api.post(endpoints.auth.login)
contexts/AuthContext.tsx:82  api.post(endpoints.auth.register)
contexts/AuthContext.tsx:89  api.post(endpoints.auth.logout)
contexts/AuthContext.tsx:100 api.post(endpoints.auth.passwordReset)
contexts/AuthContext.tsx:106 api.post(endpoints.auth.passwordResetConfirm)
```

**Toutes les pages métier affichent des données codées en dur** (tableaux `const` locaux) :
`Dashboard` (`const websites`, `kpis`, `criticalIssues`), `Scans`, `Reports`, `Alerts`, `Websites`,
`WebsiteDetails`, `Monitoring`, `Billing`, `Settings`, `Reviews`. Les commentaires du code le
confirment : *« Data is representative demo — in production this connects to GET /api/scans/ »*
(`Scans.tsx`), *« In production this would fetch from /api/reports/public/:publicId »* (`PublicReport.tsx`).
`Settings.tsx` affiche en dur « Maria Schmidt / maria@schmidt-bakery.de » et un « Pro Plan » fictif.

**Impact** : un client payant ne peut ni voir ses sites, ni lancer un scan, ni consulter ses résultats,
alertes ou rapports depuis l'interface. **Release blocker absolu.**

---

## 2. Viabilité commerciale & quotas — ❌ ÉCHEC

| Élément | État | Preuve |
|---|---|---|
| Modèles `Plan` / `Subscription` | Présents | `subscriptions/models.py` |
| Endpoints abonnement | Présents (`plans/`, `me/`, `upgrade/`, `cancel/`) | `subscriptions/urls.py` |
| Prestataire de paiement | **Absent** (aucun Stripe/Paddle/checkout/webhook) | `grep` : seul le champ texte `billing_provider` |
| Plans amorcés en base | **Non — `subscriptions_plan = 0`** | requête PostgreSQL live |
| Application des quotas | **Aucune** (`max_scans_per_month` seulement déclaré + sérialisé) | aucun contrôle dans `websites/views.py`, `monitoring/*`, `public_checker/views.py` |
| Blocage quota dépassé (HTTP 402) | **Inexistant** | aucun `402`/`Quota` dans le code |

Conséquences directes :
- `UpgradeSubscriptionView` **change le plan sans aucun paiement** — n'importe quel utilisateur peut
  s'attribuer « Business » gratuitement.
- La table `Plan` étant vide, l'abonnement gratuit auto-créé échoue silencieusement (signal
  `Free plan not found — subscription not created`) : `subscriptions_subscription = 0`.
- La commande d'amorçage `create_plans` est **manuelle** et n'a jamais été exécutée.

**Release blocker absolu** pour tout lancement payant.

---

## 3. Alerting & e-mails transactionnels — ❌ ÉCHEC

### 3.1 Moteur d'alerte dormant
`alerts/tasks.py::detect_alerts` est **entièrement implémenté** (SSL, site hors ligne, DNS, headers,
performance, chute de score, déduplication, auto-résolution, fenêtres de silence). Mais il n'est
**jamais appelé** :

```
grep "alerts.tasks.detect_alerts" dans tout le backend → AUCUNE référence de déclenchement
Scans créés par websites/views.py, monitoring/views.py, monitoring/tasks.py,
public_checker/views.py → tous appellent run_*_scan.delay(), jamais detect_alerts
alerts_alert en base = 0
```

`run_authenticated_scan` (fin de scan) ne déclenche aucun hook post-scan. Le beat ne planifie que
`cleanup_old_alerts` (suppression), pas la détection. **Aucune alerte ne sera jamais émise.**
*(À noter : `run_due_monitors` est bien planifié toutes les 5 min et crée des scans automatiques —
le monitoring tourne, mais rien n'alerte.)*

### 3.2 E-mails non délivrés
`.env` live :

```
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend   ← e-mails imprimés, jamais envoyés
EMAIL_HOST=localhost   EMAIL_PORT=25                           ← pas de serveur SMTP
DEFAULT_FROM_EMAIL=noreply@presence.local                      ← domaine non routable
FRONTEND_URL=http://localhost:8080                             ← liens e-mail cassés (le site est en :443)
```

Les e-mails de vérification, de reset de mot de passe, de rapport public et d'alerte existent dans le
code mais **ne partent nulle part**. **Release blocker absolu** (impossible de vérifier un compte ou
de réinitialiser un mot de passe en production).

---

## 4. Conformité & Opérations (Day 2) — ❌ ÉCHEC

| Exigence | État | Preuve |
|---|---|---|
| Suppression de compte (RGPD art. 17) | **Absente** | `accounts/urls.py` : aucun endpoint |
| Export des données (RGPD art. 20) | **Absent** | aucune route `export` |
| Désactivation de site | Présente | `websites/tests/...test_owner_can_deactivate_website` |
| Sauvegarde automatisée | **Absente** (script manuel uniquement) | `scripts/backup_pre_remediation.sh` ; aucun service `backup` dans `docker-compose.yml` |
| Rétention des données | **Partielle** | purge des scans *invités* > 24 h + suppression des alertes résolues > 90 j ; **rien** pour les données utilisateurs |
| Observabilité applicative | **Quasi inexistante** | logs JSON console + `/api/v1/health/` ; **aucun** Sentry/APM/métriques/tracing |
| TLS | Auto-signé (`nginx/ssl`) | à remplacer par ACME/Let's Encrypt + domaine réel |

Ajouter à cela : `ALLOWED_HOSTS=localhost,127.0.0.1,web` (pas de domaine public), certificat local
auto-signé, et une CI (`.github/workflows/ci.yml`) qui ne fait que `manage.py test` (aucun déploiement,
aucune sauvegarde, aucun test de restauration).

---

## 5. Release Blockers (priorisés)

1. **Intégration frontend↔API** des parcours critiques (sites, scans+finding+résultats, alertes,
   dashboard, rapports, monitoring, réglages) — remplacer les jeux de données codés en dur.
2. **Facturation réelle** : prestataire de paiement + webhooks d'abonnement, amorçage des plans
   (migration de données), et **application des quotas** (402/limites).
3. **Déclenchement du moteur d'alerte** (`detect_alerts.delay` en fin de scan + filet de sécurité beat).
4. **E-mails réels** : serveur SMTP/transactionnel + `FRONTEND_URL` HTTPS correcte + SPF/DKIM + tests de
   délivrabilité (vérification, reset, alertes).
5. **RGPD** : suppression et export de compte, politique de rétention des données utilisateurs.
6. **Ops** : sauvegardes automatisées testées (dump + restauration), remontée d'erreurs (Sentry
   backend+frontend), domaine public + TLS valide.

---

## 6. Plan d'action — Itération 3 « Ready for Production »

Cible : lever les 6 blockers ci-dessus, dans cet ordre. Chaque livrable est vérifiable.

### Étape 1 — Intégration produit (frontend)
- Brancher chaque page sur `api`/`endpoints` : `Dashboard` (KPIs via `/websites/`, `/scans/`,
  `/alerts/`), `Websites`/`WebsiteDetails` (CRUD + `active_scan`), `Scans` (liste + `findings` +
  `scanner-runs` + `recommendations`), `Alerts` (liste + acquittement/résolution), `Reports`
  (génération + PDF), `Monitoring`, `Settings`/`Billing`.
- Ajouter les états *loading / empty / error* et la gestion du **409 scan déjà en cours** et du futur
  **402 quota**.
- Critère de sortie : parcours complet « inscrire → ajouter un site → lancer un scan → voir le score
  et les findings → recevoir/mesurer une alerte » réalisable depuis l'UI, sans donnée en dur.

### Étape 2 — Facturation & quotas
- Intégrer un prestataire de paiement (Stripe recommandé) : Checkout/Portail + webhooks
  (`subscription.created/updated/deleted`, `invoice.paid`, `payment_failed`), idempotents.
- Amorcer les plans par **migration de données** (plus `create_plans` manuel).
- Centraliser l'application des quotas dans un service (`plan_limits`) et le brancher sur : création
  de site (`max_websites`), création/planification de scan (`max_scans_per_month`, `min_scan_interval`),
  canaux d'alerte (`max_alert_channels`) → **HTTP 402** quand dépassé.
- Critère de sortie : un compte gratuit est bloqué au-delà de son quota ; un upgrade **payé** débloque
  les limites ; `subscriptions_plan` peuplé.

### Étape 3 — Alerting réel
- Appeler `detect_alerts.delay(scan.id)` à la fin de `run_authenticated_scan` (après `_finalize_scan`),
  y compris pour les scans de monitoring ; ajouter une passe beat de rattrapage.
- Vérifier la chaîne complète : scan → `Alert` créée → `dispatch_alert` → e-mail/push/webhook.
- Critère de sortie : un site hors ligne / certificat expirant produit une alerte visible dans l'UI et
  notifiée.

### Étape 4 — E-mails transactionnels
- Configurer un SMTP/transactional réel (Resend/Postmark/SES/SMTP), `DEFAULT_FROM_EMAIL` sur le domaine,
  `FRONTEND_URL` en HTTPS, SPF/DKIM/DMARC.
- Tests d'envoi réels pour : vérification, reset, rapport public, alerte.
- Critère de sortie : e-mails reçus en boîte, liens fonctionnels.

### Étape 5 — Conformité RGPD
- `DELETE /api/v1/account/` (suppression/anonymisation + purge des données liées, journalisée) et
  `GET /api/v1/account/export/` (JSON/archive).
- Politique de rétention documentée + tâche de purge pour les données utilisateurs.
- Critère de sortie : suppression et export testés de bout en bout.

### Étape 6 — Opérations (Day 2)
- Sauvegardes automatisées (`pg_dump` planifié vers stockage externe) **et procédure de restauration
  testée**.
- Observabilité : Sentry (backend + frontend), alerting sur erreurs, métriques de base.
- Domaine public + certificat TLS valide (ACME), `ALLOWED_HOSTS`/CORS sur le domaine réel.
- Critère de sortie : une erreur applicative déclenche une alerte ; une restauration est prouvée.

---

## 7. Synthèse

| Domaine | Verdict |
|---|---|
| Socle technique (scan, sécurité, TLS) | ✅ Bon |
| Intégration produit | ❌ Maquette non branchée |
| Facturation / quotas | ❌ Inexistant |
| Alerting | ❌ Dormant |
| E-mails transactionnels | ❌ Console uniquement |
| Conformité RGPD | ❌ Absent |
| Sauvegarde / observabilité | ❌ Manuel / quasi nul |

**Décision : NO-GO commercial.** Autorisé : bêta privée fermée uniquement, après au minimum
l'Étape 1 (intégration) et l'Étape 4 (e-mails) si l'inscription publique est ouverte.
