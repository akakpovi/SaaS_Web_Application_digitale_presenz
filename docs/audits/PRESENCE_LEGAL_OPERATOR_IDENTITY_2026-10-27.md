# Presence — Identité de l'exploitant centralisée sur les pages juridiques

**Date :** 27 octobre 2026
**Périmètre :** `/impressum`, `/privacy` (Datenschutz), `/terms` (AGB), `/widerruf` — centralisation des informations de l'exploitant dans une source unique, propagation cohérente, placeholders localisés DE/EN.
**Verdict technique : `VALIDÉ TECHNQUEMENT`.** **Verdict conformité : `BLOQUÉ`** — aucune conformité juridique n'est certifiée ; aucune donnée d'exploitant n'a été inventée, l'identité reste à fournir.

> Note de chemin : le dépôt demandé (`~/Schreibtisch/SaaS_Web_Application_digitale_presenz_v2`) n'existe pas sous cette forme ; le projet réel est `~/Schreibtisch/SaaS_Web_Application_digitale_presenz/SaaS_Web_Application_digitale_presenz_v2`. Toutes les modifications sont locales, non commitées, aucun déploiement.

---

## 1. Résultat en une page

| Élément | Avant | Après |
| --- | --- | --- |
| Source de l'identité | 7 chaînes allemandes codées en dur dans `ImpressumPage.tsx` | `src/config/operator.json` + accès typé `src/config/operator.ts` |
| Pages branchées sur la source | 1 (Impressum seul) | **4** : Impressum, Datenschutz §1 + §12, AGB §1, Widerruf |
| Placeholders sur la page anglaise | texte **allemand** (`[Firmenname eintragen]`…) | placeholders **anglais** (`legal.operator.*Placeholder`) |
| États distingués | implicite (tout est placeholder) | `provided` / `missing` / `not-applicable`, documentés par champ |
| Clés de catalogue (DE = EN) | 1829 | **1858** (+29, parité stricte) |
| Littéraux d'identité dans `pages/` + `components/` | 7 | **0** (vérifié par grep) |
| Fichiers consommant la source | — | `ImpressumPage`, `PrivacyPage`, `TermsPage`, `WithdrawalPage`, `OperatorIdentityDetails` |
| `tsc`, build, E2E | — | **exit 0 / exit 0 / 9 passed** + simulation contrôlée du mode résolu |

---

## 2. État initial constaté (avant modification)

| Constat | Preuve |
| --- | --- |
| Aucune source centrale d'identité n'existait | aucun `config/` ; l'identité n'existait que comme littéraux dans `ImpressumPage.tsx` |
| Les 7 valeurs d'imprimeur étaient **codées en dur, en allemand**, y compris sur la version anglaise | `ImpressumPage.tsx` : `"Presence — [Firmenname eintragen]"`, `"[Straße, Hausnummer] · [PLZ, Ort] · [Land]"`, `contact@[domain eintragen]`… |
| Datenschutz, AGB et Widerruf ne citaient aucune donnée : ils renvoyaient au « im Impressum genannte Anbieter » | `legal.privacyControllerBody`, `legal.termsScopeBody`, `legal.withdrawalProcessBody` |
| Aucune identité ailleurs dans le produit | `grep` backend : 0 occurrence d'`Impressum`/`Geschäftsführer`/`USt-IdNr` ; templates e-mails sans adresse ; footers = marque + liens uniquement |
| `[Anbieter eintragen]` (mentionné dans le rapport précédent) n'existait **pas** dans le code | `grep -rn "Anbieter eintragen" src/` → 0 résultat ; c'était une entrée d'inventaire du rapport, pas un placeholder rendu |
| `support@presence.local` n'est pas une identité publique | `backend/config/settings/base.py:226` — claim VAPID par défaut, écarté volontairement |

**Aucune donnée réelle n'existe dans le dépôt :** ni raison sociale, ni adresse, ni registre, ni TVA, ni e-mail d'exploitant. Rien n'a été déduit ou inventé.

---

## 3. Source unique de vérité

- **Données :** `src/config/operator.json` — 14 champs, chacun avec `requirement` (`mandatory` / `conditional` / `optional`), `usedOn` (pages concernées), `labelKey`, `placeholderKey` (sauf champ optionnel), et `condition` pour les champs conditionnels. Entrée `_readme` pour la personne qui édite.
- **Trois états, jamais confondus :**
  - `provided` — `value` réelle et vérifiée, rendue telle quelle ;
  - `missing` — `value: null` → placeholder **localisé** + badge « must be replaced » ;
  - `not-applicable` — `notApplicable: "raison"` → ligne **omise**, raison conservée pour l'audit.
- **Accès typé :** `src/config/operator.ts` expose `operatorDisplayName()`, `operatorAddressLines()`, `operatorValue()`, `operatorImpressumRows()`, `missingOperatorFields()`, `hasUnresolvedPlaceholders()`, `isOperatorIdentityComplete()`. Les clés de catalogue sont typées `MessageKey` ; une clé manquante casse `tsc`.
- **Pourquoi un fichier Git et non des variables d'environnement :** l'identité est du **contenu juridique relu et versionné**, pas de la configuration de déploiement ; elle doit apparaître dans le HTML pré-rendu/publique sans rebuild par environnement, et ne contient aucun secret. `.env.example` n'a donc pas été modifié (il documente uniquement la configuration d'exécution).

---

## 4. Propagation, page par page

| Page | Comportement identité incomplète (état actuel) | Comportement identité complète |
| --- | --- | --- |
| `/impressum` | lignes de la source : 13 placeholders localisés + badge ; `legal.legalNoticeBody` « à compléter » | valeurs réelles ; bandeau bascule sur `legalNoticeTitleComplete`/`BodyComplete` ; les champs `not-applicable` disparaissent |
| `/privacy` §1 | phrase existante « Verantwortlicher … der im Impressum genannte Anbieter » | `privacyControllerResolvedBody` + bloc `OperatorIdentityDetails` (nom+forme, adresse, e-mail, registre/TVA/DPO si fournis) |
| `/privacy` §12 | phrase existante (adresse de réponse à compléter) | `privacyContactResolvedBody` avec interpolation `{email}` |
| `/terms` §1 | phrase existante + avertissement B2B/B2C | `termsScopeResolvedBody` + même bloc ; l'avertissement B2B/B2C (`termsScopeAudienceNote`) reste **toujours** affiché |
| `/widerruf` | pas de bloc ; renvoi à l'adresse de l'Impressum | section `withdrawalRecipientTitle` + bloc variante `address` (nom, adresse, e-mail) |
| Footers | inchangés : marque + liens (`/impressum`, `/privacy`, `/terms`) — aucune identité n'y figure | idem |

Détails de conception : les valeurs ne sont **jamais** dupliquées dans `de.json`/`en.json` — seuls les libellés et placeholders y vivent ; `phone` n'a pas de placeholder (optionnel : absent = ligne omise, pas d'avertissement) ; le nom affiché est `legalName` + `legalForm` joints par un espace, la forme juridique restant un champ distinct (pas de concaténation devinée si l'un manque).

---

## 5. Inventaire des informations manquantes (à fournir)

État réel : **0 fourni · 14 manquants · 0 non applicable.** Aucune valeur inventée ; les 6 obligatoires sont en P1 bloquant, les 7 conditionnels exigent une décision (valeur **ou** non-applicabilité motivée).

| # | Champ | Statut | Exigence | Utilisé sur | À fournir par | Prio |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `legalName` (raison sociale) | manquant | obligatoire | Impressum, Datenschutz, AGB, Widerruf | Exploitant | **P1** |
| 2 | `representedBy` (représentant légal) | manquant | obligatoire | Impressum | Exploitant | **P1** |
| 3 | `street` | manquant | obligatoire | 4 pages | Exploitant | **P1** |
| 4 | `postalCity` | manquant | obligatoire | 4 pages | Exploitant | **P1** |
| 5 | `country` | manquant | obligatoire | 4 pages | Exploitant | **P1** |
| 6 | `email` (adresse de contact joignable) | manquant | obligatoire | 4 pages | Exploitant | **P1** |
| 7 | `legalForm` | à trancher | conditionnel (GmbH/UG/AG ; aucun pour un particulier) | Impressum, Datenschutz, AGB | Exploitant | **P1** |
| 8 | `registerCourt` | à trancher | conditionnel (inscription au registre) | Impressum | Exploitant | **P1** |
| 9 | `registerNumber` | à trancher | conditionnel | Impressum | Exploitant | **P1** |
| 10 | `vatId` (USt-IdNr.) | à trancher | conditionnel (§ 19 UStG possible) | Impressum | Exploitant + fiscaliste | **P1** |
| 11 | `editorialResponsible` (§ 18 al. 2 MStV) | à trancher | conditionnel (blog prévu) | Impressum | Exploitant | **P1** |
| 12 | `supervisoryAuthority` | à trancher | conditionnel (profession réglementée uniquement) | Impressum | Exploitant | P2 |
| 13 | `dataProtectionOfficer` | à trancher | conditionnel (obligation à évaluer) | Impressum, Datenschutz | Juriste | P2 |
| 14 | `phone` | manquant | **optionnel** | Impressum (affiché si fourni) | Exploitant | P3 |

Décisions non couvertes par ces champs et toujours ouvertes (cf. rapport précédent) : B2B/B2C, texte définitif du Widerrufsrecht, droit applicable, fournisseurs (hébergement, e-mail, passerelle AKA IA).

---

## 6. Tests réellement exécutés

Toutes les commandes ont été lancées localement ; aucun déploiement, aucune donnée supprimée, aucun conteneur ou volume touché.

| # | Commande | Résultat |
| --- | --- | --- |
| 1 | `node scripts/check-operator-identity.mjs` | **exit 0** — 14 champs, schéma/états/clés valides, 6 obligatoires et 7 conditionnels listés avec pages |
| 2 | `node scripts/check-i18n.mjs` | **exit 0** — **1858/1858** clés, interpolations identiques, `legal.*` = 118 clés |
| 3 | `node scripts/check-i18n.mjs --verbose` (pages légales) | littéraux restants : `Presence` (fil d'Ariane) et `© 2026 Presence ·` uniquement |
| 4 | `npx tsc --noEmit` | **exit 0** |
| 5 | `npm run build` | **exit 0** — 32 routes pré-rendues, sitemap 27 URL |
| 6 | `npx playwright test e2e/operator-identity.spec.ts e2e/legal-pages-i18n.spec.ts e2e/launch-readiness.spec.ts --workers=1` | **9 passed** (dont 2 nouvelles : identité rendue/marquée, cohérence entre les 3 pages) |
| 7 | `grep` de contrôle | **0** littéral d'identité restant dans `pages/`+`components/` ; la source est consommée par exactement 5 fichiers |
| 8 | Simulation contrôlée (voir §7) | mode résolu **2/2**, gate `--require-complete` **exit 1**, fichier restauré à l'identique |

Les specs existants valident au passage : aucune clé brute affichée sur les 5 pages légales, bascule DE/EN, persistance après rechargement, mobile 390 px, parcours public complet.

---

## 7. Simulation contrôlée du mode résolu — et sa distinction

Le dépôt ne contient **aucune** donnée d'exploitant réelle ; le mode « identité complète » ne pouvait donc pas être prouvé avec les données livrées. Pour ne pas laisser cette branche non testée :

1. des valeurs **synthétiques et explicitement fictives** (`Presence Beispiel GmbH`, `Erika Mustermann`, `Beispielweg 1`, `10115 Berlin`, `kontakt@example.com`, `HRB 000000`, `DE000000000`) ont été écrites **temporairement** dans `operator.json` ;
2. l'audit a montré 11 fournis · 1 non applicable · 2 à trancher (`phone`, DPO) ;
3. la spec `operator-identity.spec.ts` a basculé automatiquement en **branche résolue : 2/2 passed** — les mêmes valeurs apparaissent sur `/privacy`, `/terms` et `/widerruf`, les placeholders des champs fournis disparaissent, le seul badge restant est celui du DPO ;
4. le gate `--require-complete` a correctement échoué (**exit 1**) tant que `phone`/DPO n'étaient pas décidés ;
5. le fichier a été **restauré byte-identique** (vérifié par `diff` → vide), puis la spec relancée sur l'état livré : **2/2 passed**, audit de nouveau « 0 fourni · 14 manquants ».

**Aucune de ces valeurs fictives n'est présente dans le dépôt après l'opération** ; elles ne sont pas une transaction ni une donnée réelle et ne sont présentées nulle part comme telles. Les tests 1-6 ci-dessus portent sur l'état livré ; le test 8 est cette simulation, clairement distinguée.

---

## 8. Limites et constats restants

| Constat | Gravité | Détail |
| --- | --- | --- |
| `/impressum` et `/cookies` absents de `src/seo/routes.json` → non pré-rendus et absents du sitemap | P3 (SEO, pré-existant) | `dist/` contient `privacy/`, `terms/`, `widerruf/` mais pas `impressum/` ni `cookies/` ; le sitemap généré les omet. **Non introduit par ce changement** ; recommandé avant le lancement (titre/description DE+EN à ajouter). |
| Validité juridique non évaluée | **BLOQUÉ** | Le fait de remplir l'identité ne rend pas les textes conformes ; la relecture par un juriste reste obligatoire. |
| La branche « identité complète » est prouvée par simulation, pas par des données permanentes | À VÉRIFIER MANUELLEMENT | Dès que les valeurs réelles sont saisies, la spec E2E devient un test de propagation permanent (elle lit le même fichier). |
| Le script valide la **structure** et les clés, pas la véracité des valeurs | — | Une adresse fausse passe le schéma ; la véracité relève de l'exploitant. |
| Aucune donnée d'identité dans les logs, les métadonnées SEO ou les endpoints | — | Les titres SEO viennent de `meta.impressum.*`, pas de l'identité ; la page n'est pas pré-rendue, donc aucune exposition involontaire non plus. |

---

## 9. Checklist finale

### VALIDÉ TECHNQUEMENT

- [x] Une seule source de vérité (`src/config/operator.json`), consommée par les 4 pages légales et le composant partagé.
- [x] Fin des placeholders allemands codés en dur ; 0 littéral d'identité dans `pages/`+`components/`.
- [x] Placeholders **localisés** : la page anglaise n'affiche plus de texte allemand ; la page allemande n'affiche plus de placeholder anglais (vérifié en E2E dans les deux sens).
- [x] Trois états distingués (`provided` / `missing` / `not-applicable`) ; « non renseigné » ≠ « non applicable » ; ligne omise pour un champ non applicable.
- [x] Bandeau d'avertissement conservé tant qu'un placeholder est rendu ; bascule prévue quand l'identité est complète.
- [x] Parité stricte des catalogues (1858/1858) et interpolations identiques ; `tsc` et build verts.
- [x] E2E : 9/9 sur les trois suites ; mode résolu prouvé par simulation, puis état livré restauré et re-testé.
- [x] Aucune donnée, aucun volume, aucun conteneur supprimé ; aucun secret introduit ; rien de commité ni déployé.

### BLOQUÉ (décision ou tiers)

- [ ] Décision **B2B / B2C** (conditionne Widerruf, prix, informations précontractuelles).
- [ ] Texte définitif du Widerrufsrecht, droit applicable, clause de responsabilité.
- [ ] Validation juridique des pages — **aucune conformité n'est certifiée ici**.

### À FOURNIR (exploitant)

- [ ] Les **6 valeurs obligatoires** : raison sociale, représentant, rue, PLZ+ville, pays, e-mail.
- [ ] Les **7 décisions conditionnelles** : forme juridique, registre (tribunal + numéro), USt-IdNr., responsable éditorial, autorité de tutelle, DPO — chacune soit une valeur, soit un `notApplicable` motivé.
- [ ] Téléphone si publication souhaitée (optionnel).

### À VÉRIFIER MANUELLEMENT

- [ ] Relire le rendu une fois les valeurs saisies (les valeurs modifieront aussi `/privacy`, `/terms`, `/widerruf`).
- [ ] Exécuter `node scripts/check-operator-identity.mjs --require-complete` comme porte de lancement (exit 0 attendu).
- [ ] Relecture native allemande et relecture juriste (inchangées depuis le rapport précédent).
- [ ] Décider d'ajouter `/impressum` et `/cookies` à `src/seo/routes.json` (titre/description DE+EN) pour le pré-rendu et le sitemap.

---

## 10. Fichiers modifiés

```
src/config/operator.json                        nouveau — source unique, 14 champs, 0 valeur inventée
src/config/operator.ts                          nouveau — états, sélecteurs, lignes d'Impressum, complétude
src/components/OperatorIdentityDetails.tsx      nouveau — bloc d'identité partagé (variantes full/address)
src/pages/ImpressumPage.tsx                     réécrit — lignes depuis la source, placeholders localisés, bandeau conditionnel
src/pages/PrivacyPage.tsx                       §1 et §12 conditionnels + bloc d'identité
src/pages/TermsPage.tsx                         §1 conditionnel + note B2B/B2C toujours visible + bloc
src/pages/WithdrawalPage.tsx                    section « adresse de rétractation » quand l'identité est complète
src/i18n/de.json / en.json                      +29 clés chacune (9 libellés, 13 placeholders, 7 textes) → 1858
scripts/check-operator-identity.mjs             nouveau — schéma, fuites de placeholders, clés i18n, porte de lancement
e2e/operator-identity.spec.ts                   nouveau — rendu, localisation, états, propagation
docs/audits/PRESENCE_LEGAL_OPERATOR_IDENTITY_2026-10-27.md   ce rapport
```

Non modifiés volontairement : routes/seo/sitemap (constat §8), DPO/prix juridiques, backend, dépendances. Toutes les modifications restent **non commitées** ; l'état Git préexistant a été préservé.

---

## 11. Prochaines priorités

1. **P1 — fournir les 6 valeurs obligatoires** puis relancer l'audit : l'Impressum passe en mode complet et les 3 autres pages basculent automatiquement.
2. **P1 — trancher les 7 champs conditionnels** (valeur ou non-applicabilité motivée) puis `--require-complete` en porte de lancement.
3. **P1 — revue juridique** (inchangée) : la centralisation ne remplace aucune validation.
4. **P3 — SEO** : pré-rendre `/impressum` et `/cookies` comme les autres pages légales.
