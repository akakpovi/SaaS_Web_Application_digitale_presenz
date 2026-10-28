# Presence — Pages juridiques allemandes : Datenschutzerklärung & AGB

**Date :** 27 octobre 2026
**Périmètre :** `/privacy` (Datenschutzerklärung), `/terms` (AGB) — traduction DE complète, cohérence avec `/widerruf`, `/cookies`, `/impressum` et l'état réel du produit.
**Verdict du volet traduction : `VALIDÉ TECHNIQUEMENT`.**
**Verdict du volet conformité : `BLOQUÉ` — aucune conformité juridique n'est certifiée par ce rapport.** Les textes restent des brouillons explicitement signalés comme tels dans l'interface.

---

## 1. Résultat en une page

| Élément | Avant | Après |
| --- | --- | --- |
| Chaînes anglaises codées en dur dans `PrivacyPage.tsx` + `TermsPage.tsx` | **105** | **2** (mention `© 2026 Presence ·`, légitime) |
| Clés de catalogue (DE = EN) | 1765 | **1829** |
| Bloc `legal.*` | 37 clés | **101 clés** |
| Parité DE/EN + interpolations | — | **1829 / 1829, ✅** |
| `tsc --noEmit` | — | **exit 0** |
| Build production | — | **exit 0**, 32 routes pré-rendues, sitemap 27 URL |
| E2E `legal-pages-i18n.spec.ts` (nouveau) | — | **2/2** |
| E2E `launch-readiness.spec.ts` (régression) | — | **5/5** |
| HTML pré-rendu `/privacy`, `/terms` | — | `lang="de"`, titres allemands, `hreflang` de/en/x-default |

Les deux pages affichent désormais un contenu allemand intégral, un sélecteur DE/EN dans leur en-tête, des titres SEO allemands, et conservent la bannière « Arbeitsentwurf » tant qu'une personne qualifiée n'a pas validé le texte.

---

## 2. Faits vérifiés dans le code avant de rédiger

Aucune affirmation du texte n'a été reprise du brouillon anglais sans contrôle. Chaque point ci-dessous a été lu dans le dépôt.

| Affirmation du texte | Preuve dans le dépôt | Verdict |
| --- | --- | --- |
| Suppression du compte **immédiate**, sans délai de 30 jours | `backend/accounts/services.py:214` `delete_user_account()` : suppression en cascade + purge explicite des lignes analytics/leads, puis passe de vérification | **vérifié** (l'ancien texte anglais « within 30 days » était inexact) |
| Export des données (Art. 15/20) disponible dans le compte | `backend/accounts/views.py:136` `GET /api/v1/auth/export/` (JSON en pièce jointe) | **vérifié** |
| Mesure d'audience **first-party**, IP hachée, pas de tiers | `backend/analytics/middleware.py` : `TrafficLog` (path, method, status, UA tronqué, referrer), IP → `sha256[:16]` | **vérifié** |
| Aucun cookie publicitaire/analytique, aucun script tiers | aucun `document.cookie` dans `src/` ; `index.html` ne charge que `main.tsx` ; aucun `posthog/gtag/plausible/matomo` ; clés locales = `presence_access`, `presence_refresh`, `presence-locale`, `presence-theme` | **vérifié** |
| AKA IA transmet la saisie + le contexte du scan à une passerelle | `backend/advisory/services/aka_client.py:340` `chat()` → `POST {base_url}/v1/chat/completions` avec `messages` construits depuis les résultats de scan | **vérifié** |
| Blog = WordPress séparé, contenu public uniquement | `docker-compose.yml` : `wordpress:6.7-php8.3-apache` + `mariadb:11`, volumes dédiés, nginx `/cms` ; `src/api/blog.ts` interroge l'API REST publique via `VITE_WP_API_URL`, sans identifiants | **vérifié** |
| Paiement via Paddle, **checkout actuellement désactivé** | `docker exec …web-1` → `BILLING_ENABLED=False`, `PADDLE_API_KEY_set=False`, `PADDLE_WEBHOOK_SECRET_set=False`, `PADDLE_ENVIRONMENT=sandbox` (booléens uniquement, aucune valeur affichée) | **vérifié le 2026-10-27** |
| Aucune purge automatique des scans « selon le plan » | `backend/scanners/artifacts.py:503` `prune_scan_archives(..., retention_days=0)` → suppression désactivée par défaut | **vérifié** (l'ancienne phrase « retained according to your plan » a été retirée) |

Conséquence : le brouillon anglais a été corrigé en même temps que sa traduction, sinon la version allemande aurait figé deux affirmations fausses (délai de 30 jours, rétention par tarif).

---

## 3. Ce qui a été traduit et modifié

### 3.1 Catalogues (`src/i18n/de.json`, `src/i18n/en.json`)

64 nouvelles clés par catalogue, ajoutées à la fin du bloc `legal.*` (donc diff minimal, ordre des clés existantes préservé) :

- **Datenschutz** : `privacySubtitle`, `privacyIntro`, `privacyControllerTitle/Body`, `privacyDataTitle` + 6 items, `privacyPurposeTitle` + 7 items, `privacyLawfulTitle/Intro` + 4 items, `privacyAiTitle/Body`, `privacySharingTitle/Intro` + 5 items, `privacyRetentionTitle/Body`, `privacyRightsTitle/Intro` + 7 items + `privacyRightsHow`, `privacySecurityTitle/Body`, `privacyCookiesTitle/Body/Link`, `privacyChangesTitle/Body`, `privacyContactTitle/Body`.
- **AGB** : `termsSubtitle`, `termsIntro`, `termsScope…`, `termsService…`, `termsAccount…`, `termsUseTitle/Intro` + 5 items, `termsBilling…`, `termsTerm…`, `termsWithdrawalTitle/Body/Link`, `termsAvailability…`, `termsLiability…`, `termsChanges…`, `termsLaw…`, `termsContact…`.
- **Libellés partagés** : `contactFormLink`, `privacyLinkLabel`, `termsLinkLabel`, `cookiesLinkLabel`, `lastUpdatedDate` (DE « 1. September 2026 » / EN « 1 September 2026 »).
- **Checklist de revue** (`legal.reviewChecklist`, 6 → 9 items) : décision B2B/B2C, passerelle IA (fournisseur/AVV/lieu), concept de suppression et durées de conservation des factures.

Aucune clé ajoutée sans usage : les 64 clés sont toutes consommées par les deux pages ou par la checklist affichée.

### 3.2 Pages

- `src/pages/PrivacyPage.tsx` — réécrit : 12 sections numérotées rendues depuis l'i18n, en-tête avec sélecteur DE/EN (remplace un « Log in » codé en dur en anglais), SEO et pied de page traduits, avertissement de brouillon conservé.
- `src/pages/TermsPage.tsx` — même traitement, 12 sections, lien vers `/widerruf` traduit.

### 3.3 Défaut réel corrigé au passage

Les deux pages avaient un en-tête **unilingue anglais** (« Log in ») sans sélecteur de langue : un visiteur allemand arrivé sur la Datenschutzerklärung ne pouvait pas changer de langue depuis la page. Elles utilisent désormais le même en-tête que `/cookies`, `/widerruf` et `/impressum`.

---

## 4. Corrections de fond par rapport au brouillon anglais

| Sujet | Ancien texte anglais | Texte DE/EN actuel | Raison |
| --- | --- | --- | --- |
| Suppression | « we delete your data within 30 days » | suppression **immédiate**, exception des obligations comptables/fiscales | le code supprime tout de suite ; l'ancienne phrase était fausse |
| Rétention des scans | « retained according to your plan » | « bleiben zusammen mit dem Konto abrufbar » | aucune purge par tarif n'est implémentée |
| Analytics | « privacy-friendly analytics » (vague) | mesure **serverseitig**, IP **gehasht**, pas de traqueur | décrit ce que fait réellement le middleware |
| AKA IA | **absent** de la politique | section dédiée : données transmises, caractère généré des réponses, aucun remplacement d'un audit | la fonction transmet des données à un tiers |
| Sous-traitants | « Our hosting … Servers based in the EU » (non prouvable) | liste avec **placeholders** `[Anbieter … eintragen]` pour hébergement, e-mail, IA | le code ne permet pas de connaître les fournisseurs |
| AGB – acceptation par usage | « Continued use … constitutes acceptance » | « ist vor dem Livegang zu klären » | clause juridiquement discutable, non validable ici |
| AGB – droit applicable | « laws of the European Union and … our jurisdiction » | laissé explicitement **à décider** | aucune juridiction réelle connue |
| AGB – remboursements | « no refunds for partial billing periods » | retiré, remplacé par « Kündigung zum Ende des Abrechnungszeitraums » | politique commerciale non décidée ; l'inventer serait faux |
| AGB – limitation de responsabilité | plafond affirmé comme valide | plafond **à faire vérifier**, renonciation aux droits impératifs interdite | ne pas présenter une clause non validée comme efficace |

Les textes juridiques ne sont pas « améliorés » par cette traduction : ils restent des brouillons, mais ils ne contiennent plus d'affirmation contraire au comportement du logiciel.

---

## 5. Informations manquantes (à fournir avant le live)

Aucune valeur n'a été inventée. Les emplacements sont marqués dans le texte (`[ … ]`) ou décrits comme points ouverts.

| # | Information manquante | Page(s) | Vérifiable dans le code ? | Qui doit fournir / valider | Priorité |
| --- | --- | --- | --- | --- | --- |
| 1 | Raison sociale, forme juridique, adresse, représentant, e-mail de contact | `/impressum`, `/privacy` §1, `/terms` §1 | Non | Exploitant | **P1** |
| 2 | USt-IdNr. (§ 27a UStG) et régime TVA (TTC/HT) | `/impressum`, `/terms` §5, `/pricing` | Non | Exploitant + conseil fiscal | **P1** |
| 3 | Inscription au registre du commerce (si applicable) | `/impressum` | Non | Exploitant | **P1** |
| 4 | Hébergement : fournisseur, localisation, contrat de sous-traitance | `/privacy` §6 | Non (configuré par env) | Exploitant | **P1** |
| 5 | Fournisseur d'e-mail transactionnel + DPA | `/privacy` §6 | Non (SMTP par env) | Exploitant | **P1** |
| 6 | Passerelle AKA IA : fournisseur, lieu de traitement, DPA/transferts | `/privacy` §5 et §6 | Non (URL/API key par env) | Exploitant | **P1** |
| 7 | Durée de conservation des factures + mise en œuvre chez Paddle | `/privacy` §7 | Non | Exploitant + fiscal | **P1** |
| 8 | Décision B2B / B2C / mixte | `/terms` §1, `/widerruf`, checkout | Non — **décision produit** | Direction produit + juriste | **P1** |
| 9 | Texte du Widerrufsrecht (délai, début, formulaire modèle, extinction) | `/widerruf` | Non | Juriste | **P1** |
| 10 | Droit applicable et juridiction | `/terms` §11 | Non | Juriste | **P1** |
| 11 | Information VSBG / plateforme européenne de règlement des litiges | `/terms` §12 | Non | Juriste | P2 |
| 12 | Obligation de nommer un DPO | `/privacy` §1 | Non | Juriste | P2 |
| 13 | Registre des sous-traitants et durées internes | interne (RGPD Art. 30) | Non | Exploitant | P2 |
| 14 | Politique de remboursement (si elle doit exister) | `/terms` §5-6 | Non | Direction produit | P2 |

---

## 6. Décision B2B / B2C — bloquante, non tranchée

Le produit est actuellement **indifférencié** : inscription libre, prix mensuels, page Widerruf présente, Paddle comme Merchant of Record. Aucun élément du code ne permet de dire si l'offre vise uniquement des professionnels.

Le texte AGB **ne présume donc rien** : il indique explicitement que la décision est ouverte et que les informations consommateur (Widerruf, affichage des prix) doivent être revues en conséquence. Trois options restent à trancher :

1. **B2C (ou mixte)** : Widerrufsbelehrung complète, Muster-Widerrufsformular, informations précontractuelles, éventuellement renonciation au droit pour service numérique — tout doit être rédigé et validé.
2. **B2B exclusif** : vérification d'entreprise à l'inscription (qui n'existe pas aujourd'hui), adaptation des prix et des clauses, suppression de la page Widerruf ou maintien à titre informatif.
3. **Mixte assumé** : mention explicite des deux publics et double jeu d'informations.

Tant que ce point n'est pas tranché, le lancement allemand ne peut pas être déclaré prêt (voir checklist §9).

---

## 7. Cohérence entre AGB, Datenschutz, Widerruf et Paddle

| Point | État constaté | Verdict |
| --- | --- | --- |
| Paiement : AGB et Datenschutz nomment Paddle comme Merchant of Record | cohérent ; `BILLING_ENABLED=False` est reflété par « solange er nicht aktiviert ist, kommt kein Abonnement zustande » | **cohérent** |
| Fin de période / annulation | AGB §6 décrit la fin de période ; `/widerruf` distingue explicitement Kündigung et Widerruf | **cohérent** |
| Widerruf renvoyé depuis les AGB | lien traduit vers `/widerruf`, qui porte encore ses placeholders (délai, formulaire modèle) | **BLOQUÉ** côté contenu juridique, lien fonctionnel |
| Cookies : Datenschutz §10 ↔ `/cookies` | même périmètre (token, langue, thème), aucun bandeau revendiqué | **cohérent** |
| Analytics : Datenschutz §3 ↔ `/cookies` | les deux décrivent un stockage technique uniquement ; la mesure d'audience est décrite comme serverseitige dans le Datenschutz | **cohérent**, mais `/cookies` ne mentionne pas `TrafficLog` (page orientée navigateur — acceptable) |
| Suppression de compte | Datenschutz §7 (immédiat) ↔ code (immédiat) | **cohérent** |
| Blog WordPress | Datenschutz §6 décrit un système séparé et un accès public en lecture | **cohérent** avec `docker-compose.yml` et `api/blog.ts` |

---

## 8. Tests réellement exécutés

Toutes les commandes ont été lancées dans le dépôt local ; aucun déploiement, aucune donnée supprimée, aucun volume touché.

| # | Commande | Résultat | Preuve |
| --- | --- | --- | --- |
| 1 | `node scripts/check-i18n.mjs` | **exit 0** — 1829 / 1829 clés, interpolations identiques | `✅ German catalogue matches the English reference exactly.` |
| 2 | `node scripts/scan-i18n-ast.mjs src/pages/PrivacyPage.tsx src/pages/TermsPage.tsx` | **105 → 2** littéraux | restants : `© 2026 Presence ·` sur chaque page |
| 3 | `npx tsc --noEmit` | **exit 0** | aucune erreur (les clés sont typées : une clé absente casse le build) |
| 4 | `npm run build` | **exit 0** — 3,28 s | 32 routes pré-rendues, sitemap 27 URL ; avertissements attendus `VITE_BASE_URL` / `VITE_WP_API_URL` |
| 5 | `npx playwright test e2e/legal-pages-i18n.spec.ts` | **2/2 passed** | desktop DE/EN sur 5 pages légales + mobile 390 px |
| 6 | `npx playwright test e2e/launch-readiness.spec.ts` | **5/5 passed** | régression : parcours public, pages légales allemandes, mobile, blog, quotas, admin |
| 7 | Inspection du pré-rendu `dist/privacy/index.html`, `dist/terms/index.html` | **conforme** | `<html lang="de">`, titres allemands, `hreflang` de/en/x-default |
| 8 | Hachage des IP / absence d'analytics tiers | **vérifié** | `grep` sur `src/`, `index.html`, `backend/analytics/middleware.py` |
| 9 | État Paddle | **vérifié** | `BILLING_ENABLED=False`, clés absentes, environnement `sandbox` |

**Un échec rencontré et corrigé honnêtement :** la première exécution du spec a échoué sur `/widerruf` parce que **le test** attendait la bannière `reviewNotice` (réservée à `/privacy` et `/terms`) sur une page qui affiche `legalNoticeTitle`. L'application était correcte ; l'attente du test a été corrigée (une clé `notice` par page), puis relancée : 2/2. Aucun test n'a été assoupli pour faire passer un défaut applicatif.

---

## 9. Checklist finale

### VALIDÉ TECHNIQUEMENT

- [x] Corps de `/privacy` et `/terms` intégralement en allemand (105 → 2 littéraux, mention ©).
- [x] Versions anglaises complètes et corrigées en parallèle.
- [x] Parité stricte des catalogues (1829/1829) et interpolations identiques.
- [x] Aucune clé brute affichée (vérifié en E2E sur les 5 pages légales).
- [x] `h1`, titres SEO et `<html lang>` corrects dans les deux langues.
- [x] Sélecteur DE/EN fonctionnel depuis les pages, persistance après rechargement.
- [x] Aucun débordement horizontal à 390 px sur les 5 pages, dans les deux langues.
- [x] Avertissement de brouillon visible dans les deux langues.
- [x] Faits sensibles (suppression, analytics, AKA IA, WordPress, Paddle) alignés sur le code.
- [x] `tsc`, build et E2E verts ; aucune régression sur `launch-readiness`.
- [x] Aucune donnée, aucun volume, aucun service Docker supprimé ou recréé.

### BLOQUÉ (décision humaine)

- [ ] Validation juridique des textes DE/EN — **aucune conformité n'est certifiée ici**.
- [ ] Décision **B2B / B2C / mixte** : conditionne Widerruf, prix et informations précontractuelles.
- [ ] Texte définitif du Widerrufsrecht (délai, formulaire modèle, extinction éventuelle).
- [ ] Droit applicable et juridiction.

### À FOURNIR (exploitant)

- [ ] Identité juridique complète (raison sociale, adresse, représentant, e-mail) — §5 lignes 1-3.
- [ ] USt-IdNr. et régime TVA.
- [ ] Fournisseurs et localisations : hébergement, e-mail, passerelle AKA IA (+ DPA).
- [ ] Durées de conservation des factures et politique de remboursement.

### À VÉRIFIER MANUELLEMENT

- [ ] Relecture par un locuteur natif allemand (style, terminologie, longueur des titres).
- [ ] Relecture par un juriste allemand (contenu, clauses, ordre des informations).
- [ ] Vérifier que la date « 1. September 2026 » correspond bien à la version validée le jour du live.
- [ ] Contrôler l'écran de checkout réel lorsque Paddle Sandbox sera activé (hors périmètre de ce cycle).
- [ ] Confirmer que aucun service d'analytics externe n'est ajouté avant le live (sinon : consentement requis).

---

## 10. Fichiers modifiés

```
src/i18n/de.json                                +64 clés legal.*, checklist 6 → 9
src/i18n/en.json                                +64 clés legal.*, checklist 6 → 9
src/pages/PrivacyPage.tsx                       réécrit (i18n, 12 sections, en-tête DE/EN)
src/pages/TermsPage.tsx                         réécrit (i18n, 12 sections, en-tête DE/EN)
e2e/legal-pages-i18n.spec.ts                    nouveau : DE/EN, passages exclusifs, mobile, clés brutes
docs/audits/PRESENCE_I18N_PUBLIC_PAGES_2026-10-27.md   passages « pages juridiques » mis à jour
docs/audits/PRESENCE_LEGAL_PAGES_DE_2026-10-27.md      ce rapport
```

Aucun fichier backend, aucun secret, aucune migration, aucun volume Docker. Toutes les modifications sont **non commitées** (`git status` conservé tel quel).

---

## 11. Prochaines priorités

1. **P1 — décision B2B/B2C** puis rédaction du Widerrufsrecht définitif : sans elle, les AGB et la page Widerruf restent incomplets.
2. **P1 — identité juridique + TVA** : remplir l'Impressum, puis propager les mêmes valeurs dans Datenschutz §1 et AGB §1.
3. **P1 — fournisseurs** (hébergement, e-mail, IA) : compléter les placeholders et vérifier les contrats de sous-traitance.
4. **P1 — revue juridique** des deux pages puis mise à jour de la date dans `legal.lastUpdatedDate`.
5. **P2 — relecture native allemande** et test du checkout dès que Paddle Sandbox est configuré.

> **Suivi (même journée) :** l'identité de l'exploitant est désormais centralisée dans `src/config/operator.json` et alimente l'Impressum, la Datenschutz (§1, §12), les AGB (§1) et le Widerruf ; les placeholders sont localisés DE/EN et plus aucun littéral d'identité ne subsiste dans les composants. Détail et preuves : `PRESENCE_LEGAL_OPERATOR_IDENTITY_2026-10-27.md`.
