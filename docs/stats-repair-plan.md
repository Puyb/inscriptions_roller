# Spec : réparation des pages de statistiques

> **Statut : lots 1 à 7 exécutés** (branche `stats-repair`, un commit par lot, 578 tests unitaires + 102 e2e verts). Lot 8 (modernisation, optionnel) non fait. Décision prise : le géocodage passe sur un **référentiel local de codes postaux (GeoNames)**, sans aucun appel externe (« solution C »).
>
> Écarts et constats d'exécution :
> - `import_codes_postaux` : FR contient ~51 600 lignes (pas ~38 000) ; un pays absent de GeoNames (404, ex. `BT`) est ignoré au lieu de faire échouer l'import.
> - Rattrapage validé sur le dump du 2026-08-04 : **99,8 % des équipes des courses 60+** localisées (1 282 / 1 332 sur l'ensemble, les non résolues sont surtout des adresses `?`).
> - `REGION_NORMALISATION` fusionnait à tort *Pays de la Loire* dans *Centre-Val de Loire* (et `Grand-est` mal casé) : corrigé au lot 5.
> - L'alignement « Date de début » de l'admin était cassé (`delta.start` inexistant → graphique vide) : corrigé au lot 6.
> - `geocoder_equipes` renseigne aussi `Course.ville2`.
> - Procédure de déploiement : `migrate`, `import_codes_postaux`, `geocoder_equipes --toutes --dry-run`, puis sans `--dry-run`.

## 1. Contexte et constats

Les statistiques existent en trois endroits :

| Page | Code | Front |
|---|---|---|
| Publique `/<uid>/stats/` | `views.stats`, `Course.stats()` | `templates/stats.html` : Bluff + Leaflet 0.5 (CDN), scripts inline |
| Publique `/<uid>/stats/<uid2,...>` | `views.stats_compare` | `templates/stats_compare.html` : Chart.js 2 (bundle webpack `stats.js`) |
| Admin `/course/stats/` | `CourseAdminSite.stats` / `get_stats_api` | `templates/admin/stats.html` : Chart.js 2 (bundle `admin.js`) |

Constats (audit du 2026-11-14, dump `enduroller-2026-08-04.sql`) :

1. **Le géocodage est mort depuis octobre 2022.** `lookup_ville()` (`models.py`) appelle `http://open.mapquestapi.com/...` qui ne répond plus. L'exception est avalée, `Equipe.gerant_ville2` reste `NULL`. Dans le dump, aucune équipe des courses 60 et suivantes (~2 000 équipes) n'a de ville. Conséquence : carte, répartition par distance et origine des équipes (pays / régions) sont vides ou cassées.
2. **Le cache `Ville` ne fonctionne quasiment pas** : recherche par `nom=` en minuscules alors que `Ville.nom` stocke `adminArea5` avec sa casse, et sans filtre sur le pays (homonymes → `MultipleObjectsReturned`).
3. **Le commit `d5e2b86` a supprimé les adresses des équipiers** (`Equipier.ville2` etc.). Les villes viennent désormais uniquement de l'adresse du responsable d'équipe (`Equipe.gerant_*`), pondérée par `Equipe.nombre`. Le calcul tient, mais les libellés (« Villes des participants ») sont devenus inexacts.
4. **Bugs front de la page publique** :
   - `stats.course.paiement_paypal` n'existe pas dans `model_stats` → le template génère `Math.round( / 5 * 100)` (erreur de syntaxe) et le graphique des paiements (staff) disparaît.
   - `points[0]` est `undefined` quand `villes` est vide → le script de la carte plante.
   - Tuiles `http://{s}.tile.osm.org` (redirigées en 301 vers https, politique d'usage OSM non respectée).
   - L'origine du calcul de distance est codée en dur (Paris) pour toutes les courses.
   - Le `{% endif %}` du bloc `user.is_staff` est mal placé (HTML déséquilibré pour un non-staff).
   - Pays vide (`''`) → ligne vide et image `flags/.png`.
5. **Dates de tarif multiples** (`Course.dates_augmentation`, `ArrayField`) : l'API admin et `stats_compare` n'utilisent que `dates_augmentation[0]` (`FIXME support multiple date`). Le tarif lui-même est correct (`Categorie.prix(d)`), seul l'alignement et l'affichage des courbes ignorent les dates suivantes.
6. **Robustesse** : `dates_augmentation` est `null=True` (`len(None)` plante), `stats[equipe.categorie.code]` plante si la catégorie est nulle, `equipiers_count` compte tous les `Equipier` sans filtrer `numero <= nombre` (possible surcomptage, **à vérifier sur des données réelles avant de corriger**).
7. **Les tests ne voient rien** : `test_public_pages` n'assert que le contexte Django ; `BaseTestCase` patche `lookup_ville` ; aucun test n'exécute le JS de la page publique.
8. **Hygiène** : une clé MapQuest en clair est committée dans `docker-compose.yml` (ligne `MAPQUEST_API_KEY` du service `django`).

## 2. Objectifs et hors périmètre

**Objectifs**
- Toutes les sections des trois pages s'affichent sans erreur console, sur des courses avec et sans données géographiques.
- Géocodage déterministe, hors-ligne, sans clé ni dépendance réseau, sans transmettre de données personnelles à un tiers.
- Rattrapage des équipes déjà inscrites sans ville.
- Alignement sur *n'importe quelle* date de changement de tarif.
- Un filet de tests qui aurait détecté ces régressions.

**Hors périmètre**
- Retrouver les adresses des équipiers (supprimées volontairement).
- Géocodage à l'adresse (rue) : la précision visée est la **commune / le code postal**.
- Refonte visuelle des pages (voir lot 8, optionnel).

## 3. Vue d'ensemble des lots

```
Lot 1  Corrections rapides (front + back)          ─┐ indépendant
Lot 2  Référentiel local + import                   ─┤
Lot 3  Moteur de lookup (remplace MapQuest)  ← 2    │
Lot 4  Rattrapage + déploiement              ← 3    │
Lot 5  Stats : pays / régions / distance     ← 3,1  │
Lot 6  Dates de tarif multiples                     ─┘ indépendant
Lot 7  Tests e2e du front public             ← 1 (puis complété par 5)
Lot 8  Modernisation front (optionnel)       ← 5
```

Ordre conseillé : **1 → 2 → 3 → 4 → 5 → 6 → 7**, chaque lot livrable et testable seul (un commit par lot). Les lots 1 et 6 peuvent être faits à tout moment, en parallèle des lots 2-4.

| Lot | Contenu | Effort |
|---|---|---|
| 1 | Corrections rapides | 0,5 j |
| 2 | Référentiel + import GeoNames | 0,5 j |
| 3 | Moteur de lookup | 0,75 j |
| 4 | Rattrapage + déploiement | 0,25 j |
| 5 | Stats pays / régions / distance | 0,5 j |
| 6 | Dates multiples | 0,5 à 1 j |
| 7 | Tests e2e front public | 0,5 j |
| **Total** | | **~3,5 à 4 j** |
| 8 | Modernisation (optionnel) | +1 à 1,5 j |

---

## Lot 1 : Corrections rapides (0,5 j)

Indépendant du reste ; rend la page publique utilisable même avec des villes vides.

**Back (`models.py`, `Course.stats()`)**
- Remplacer `paiement_paypal` par une ventilation par `Paiement.type` (`espèce`, `chèque`, `paypal`, `stripe`, `helloasso`, `virement`, `offert`, `autre`). Exposer `result['course']['paiements_par_type'] = {type: nombre_d_equipes}` (calcul en une requête agrégée sur `PaiementRepartition`/`Paiement`, pas une requête par équipe). Une équipe payée par plusieurs types est comptée dans chacun ; le total « impayé » reste `equipes - p`.
- Garde-fous : `dates_augmentation or []` partout où elle est lue (`stats_compare`, `get_stats_api`, propriétés de `Course`) ; `equipe.categorie_id` nul → ne pas incrémenter `stats[code]`.
- Clé de pays manquante : `keys['pays'] = ''` devient une constante `PAYS_INCONNU = '?'` (voir lot 5 pour son affichage).

**Front (`templates/stats.html`)**
- Graphique des paiements : consommer `paiements_par_type` (un secteur par type non nul + « Impayé »).
- Carte : ne rien construire si `stats.villes` est vide (masquer `#map` et `#canvas_distance`, afficher « Localisation indisponible » à la place) ; plus aucun accès à `points[0]` sans test.
- Tuiles : `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, attribution `© OpenStreetMap contributors` conservée.
- Corriger le `{% endif %}` du bloc staff (ouvrir et fermer `{% if user.is_staff %}` autour du même élément HTML).
- Ne pas afficher d'`<img>` de drapeau quand le code pays est vide/inconnu.
- Renommer « Villes des participants » en « Villes des responsables d'équipe » (clé de traduction + `inscriptions/locale/en`), idem l'infobulle de la carte.

**Hygiène**
- Retirer la clé MapQuest committée de `docker-compose.yml` (lot 3 supprime ensuite toute la configuration MapQuest). Considérer la clé comme compromise.

**Critères d'acceptation**
- Course sans aucune ville géocodée : la page publique se charge, **0 erreur console**, les sections clubs / catégories / courbe / paiements (staff) s'affichent.
- Les tests de `test_public_pages` restent verts ; un test vérifie la clé `paiements_par_type`.

---

## Lot 2 : Référentiel local de codes postaux (0,5 j)

**Source** : GeoNames « Postal Code » (`https://download.geonames.org/export/zip/`, fichiers `FR.zip`, `BE.zip`, `allCountries.zip`…), licence **CC BY 4.0** → ajouter une mention d'attribution (« Données : GeoNames, CC BY 4.0 ») au pied de la page de stats. Colonnes du TSV : pays, code postal, nom, admin1 (région), admin2 (département), admin3, lat, lng, précision.

**Modèle** `CodePostal` (nouvelle migration, aucune modification de `Ville`) :

| Champ | Type | Remarque |
|---|---|---|
| `pays` | `CharField(2)` | ISO 3166-1 alpha-2 |
| `code_postal` | `CharField(20)` | forme normalisée (voir lot 3) |
| `nom` | `CharField(200)` | nom d'origine (affichage) |
| `nom_normalise` | `CharField(200)` | minuscules, sans accents ni ponctuation |
| `region` | `CharField(200)` | admin1 |
| `departement` | `CharField(200)` | admin2, vide si absent |
| `lat`, `lng` | `DecimalField(10,7)` | |

Index : `(pays, code_postal)` et `(pays, nom_normalise)`.

**Commande** `./manage.py import_codes_postaux`
- `--pays FR,BE,CH,DE,IT,ES,NL,LU,GB` (défaut : liste des pays réellement présents dans `Equipe.gerant_pays` ; à calculer par une requête `distinct` et afficher), `--fichier chemin.zip|.txt` (import hors-ligne), sinon téléchargement du zip du pays.
- **Idempotente** : remplace le contenu des pays importés dans une transaction (`delete` + `bulk_create` par lots de 5 000). Affiche le nombre de lignes par pays.
- Le téléchargement est **la seule opération réseau** et n'a lieu qu'à la demande de l'opérateur, jamais à l'exécution d'une requête HTTP.
- Les données ne sont pas versionnées dans git (taille) ; la procédure est documentée dans `docs/wiki/` (page « Statistiques ») et dans `CLAUDE.md`.

**Critères d'acceptation**
- Importer `FR` : ~38 000 lignes, rejouer la commande donne le même résultat.
- Test unitaire de l'import sur un mini-fichier de 10 lignes (fixture générée dans le test, pas de réseau).

---

## Lot 3 : Moteur de lookup (0,75 j)

Réécriture de `lookup_ville(nom, cp, pays)` dans un module dédié (`inscriptions/geocoding.py`), `models.lookup_ville` reste le point d'entrée (la signature ne change pas : `Equipe.save()` et le patch de `BaseTestCase` continuent de fonctionner). **Aucun appel réseau.**

**Normalisation**
- `normaliser_nom` : minuscules, suppression des accents (`unicodedata`), `-`, `'`, `,`, `/` → espace, réduction des espaces, `st`/`ste` → `saint`/`sainte`, suppression de `cedex [n]`, suppression de l'arrondissement (`paris 15e`, `lyon 3eme` → `paris`, `lyon` ; le code postal garde l'arrondissement).
- `normaliser_cp(cp, pays)` : majuscules, sans espace ; spécificités : `NL` (`1234 AB` → `1234AB`, repli sur les 4 chiffres), `GB` (repli sur la partie sortante), `CA` (3 premiers caractères), `FR`/`DE`/`IT`/`ES`/`BE`/`CH`/`LU` (chiffres seuls). Le cas FR de la Corse (`2A`/`2B`) est géré via les codes postaux (`20xxx`).
- Entrée sentinelle `'?'` (utilisée par `admin_course.py` à la création manuelle d'équipe) et valeurs vides → `None` sans requête.

**Algorithme (premier palier qui répond gagne)**
1. `(pays, code_postal exact)` **et** `nom_normalise` égal → résultat exact.
2. `(pays, code_postal exact)`, plusieurs communes : la plus proche du nom saisi (`difflib.SequenceMatcher` sur `nom_normalise`, seuil 0,6) ; sinon, la première par ordre alphabétique.
3. `(pays, code_postal exact)`, une seule commune : la prendre (nom saisi faux ou absent).
4. `(pays, nom_normalise)` sans code postal fiable : si une seule commune (ou une seule dans un rayon de 25 km), la prendre ; sinon, la plus peuplée n'étant pas connue, **renvoyer `None`** plutôt que deviner.
5. FR uniquement, code postal à 5 chiffres inconnu : repli sur le barycentre des communes du même département (2 premiers chiffres, 3 pour les DOM), marqué comme approximatif.
6. Sinon `None`.

**Matérialisation en `Ville`**
`Ville` reste la cible de `Equipe.gerant_ville2` (aucune migration de `Equipe`, `Course.stats()` inchangé). Le résultat est obtenu par `Ville.objects.get_or_create(nom=<nom GeoNames>, pays=<ISO2>, region=<admin1>, lat=..., lng=...)`. On corrige ainsi le cache : la clé de dédoublonnage est `(nom, pays, region)` avec le nom d'origine, et les 2 197 `Ville` MapQuest existantes restent valides (leurs régions sont traitées par `REGION_NORMALISATION`, qui est conservé).

**Nettoyage de MapQuest**
- Supprimer l'appel HTTP, `import requests`/`traceback` s'ils deviennent inutiles, `iriToUri` si plus utilisé, `MAPQUEST_API_KEY` (`settings/default.py`, `settings/docker.py`, `docker-compose.yml`, `docker-compose.override.yml.dist`), toute mention dans `CLAUDE.md`.
- `Equipe.save()` : ne cherche plus qu'une fois (si `gerant_ville2_id` est nul) et **re-géocode quand `gerant_ville`, `gerant_code_postal` ou `gerant_pays` changent** (aujourd'hui une correction de l'adresse ne corrigeait jamais la ville).

**Critères d'acceptation** (tests unitaires dans `tests/test_geocoding.py`, sur une mini-table de `CodePostal` créée par factory)
- Cas exact, nom approximatif (`St Etienne` ↔ `Saint-Étienne`), arrondissement (`Paris 15` / `75015`), `Cedex`, code postal inconnu avec repli département, nom homonyme avec deux codes postaux différents, `NL`/`GB` avec format étendu, sentinelle `'?'`, aucun résultat.
- Aucun test ne dépend du réseau ; `BaseTestCase` n'a plus besoin de patcher `lookup_ville` (le retirer, ou ne le conserver que dans les tests qui ne créent pas de `CodePostal`).

---

## Lot 4 : Rattrapage et déploiement (0,25 j)

**Commande** `./manage.py geocoder_equipes`
- `--course <uid>` (répétable) ou `--toutes` ; par défaut, uniquement les équipes avec `gerant_ville2` nul ; `--force` recalcule toutes les équipes ; `--dry-run` n'écrit rien.
- Sortie : nombre d'équipes traitées, résolues, restantes, plus la **liste des non résolues** (course, numéro, ville / code postal / pays saisis) pour correction manuelle ; code de retour 0.
- Utilise `QuerySet.update` / `bulk_update` (sans `Equipe.save()`, qui déclenche numérotation, mails, etc.).

**Déploiement (ordre)**
1. Déployer le code (migration `CodePostal`).
2. `./manage.py import_codes_postaux` (pays utilisés).
3. `./manage.py geocoder_equipes --toutes --dry-run`, relire le rapport, puis sans `--dry-run`.
4. Vérifier les pages de stats d'une course récente (60+).

**Critères d'acceptation**
- Sur le dump `enduroller-2026-08-04.sql` rechargé en local : > 95 % des équipes des courses 60+ résolues ; le rapport liste le reste.

---

## Lot 5 : Stats pays / régions / distance (0,5 j)

**Régions et pays**
- `Course.stats()` : pour une `Ville` française, `keys['pays']` = région normalisée (`REGION_NORMALISATION`) ; pour les autres pays, l'ISO2. Aucun changement de structure du résultat (`stats['pays'][clé]['pays']` reste l'ISO2 pour le drapeau). `PAYS_INCONNU` s'affiche « Non localisé » (pas de drapeau).
- Compléter `REGION_NORMALISATION` avec les libellés admin1 de GeoNames s'ils diffèrent (à contrôler sur l'import FR : comparer les régions distinctes obtenues aux 13 régions métropolitaines + DOM).

**Origine de la distance**
- Nouveau champ `Course.ville2` (`ForeignKey(Ville, null=True, blank=True, on_delete=SET_NULL)`, migration) renseigné automatiquement à l'enregistrement par `lookup_ville(course.ville, '', 'FR')` si vide, modifiable dans l'admin (`admin_main`, superuser) pour les courses hors de France.
- `stats()` expose `result['origine'] = {'lat', 'lng', 'nom'}` (ou `None`). `stats.html` remplace les coordonnées de Paris codées en dur ; sans origine, `canvas_distance` est masqué (même traitement que lot 1).
- Le paramètre `?tranche=` / `?distanceMax=` reste supporté.

**Critères d'acceptation**
- Test : une course à Nevers avec deux équipes (Nevers, Troyes) → origine Nevers, distances ≈ 0 et ≈ 230 km.
- Test : équipes étrangères → code ISO2 et drapeau corrects ; équipe sans ville → `Non localisé`.

---

## Lot 6 : Dates de tarif multiples (0,5 à 1 j)

Indépendant. `Categorie.prix()` gère déjà `n` dates ; il reste l'alignement et l'affichage.

**API admin** (`get_stats_api`) : remplacer `date.augmentation` / `delta.augmentation` par des listes :
```json
"augmentations": [{"date": "2026-02-01T00:00:00+0100", "delta": 31}, ...]
```
Conserver provisoirement les anciennes clés `augmentation` (= première date) pour ne pas casser le front pendant le déploiement, à supprimer en fin de lot.

**Front admin** (`admin/stats.html`)
- L'option « Date d'augmentation » devient « Augmentation n° » (liste `n = 1…max` selon les courses sélectionnées) ; une course qui a moins de `n` augmentations est alignée sur sa dernière (comportement documenté dans l'infobulle).
- Une annotation verticale par date d'augmentation (au lieu d'une seule).
- Persistance dans le hash d'URL (`align=augmentation:2`).

**Front public** (`stats_compare.html`, `views.stats_compare`)
- `?align=augment` accepte `augment:<n>` ; résoudre le `FIXME support multiple date`. `duree` / `augment` calculés avec la n-ième date (repli sur la dernière), garde `dates_augmentation or []`.

**Critères d'acceptation**
- Tests unitaires sur la vue et l'API (course à 0, 1 et 3 dates) ; le test e2e `e2e/test_admin_stats.py` est étendu pour vérifier le nombre d'annotations.

---

## Lot 7 : Tests du front public (0,5 j)

**Pourquoi** : les tests actuels (contexte Django) n'ont détecté aucun des bugs de la section 1.

- Nouveau `e2e/test_public_stats.py` (Playwright, stack `scripts/test-e2e.sh`) : ouvre `/<uid>/stats/` pour (a) une course avec équipes géocodées, (b) une course sans aucune ville. Vérifie : **aucune erreur console / `pageerror`**, présence des `canvas`, de `#map` (cas a) et de l'état « Localisation indisponible » (cas b), tableau des pays non vide, section staff visible uniquement connecté en staff.
- Étendre `setup_e2e_data` : quelques `CodePostal` + équipes avec `gerant_ville2`, une équipe avec ville inconnue, une course avec 3 dates d'augmentation.
- Test e2e de `stats_compare` (`?align=augment:2`).
- Test unitaire de `Course.stats()` avec un jeu complet (pays FR / étrangers, équipe sans ville, catégorie, paiements de plusieurs types) pour verrouiller la structure JSON consommée par le front.

**Critères d'acceptation** : les tests échouent sur `master` actuel (vérifier en les lançant avant les lots 1 et 5) et passent après.

---

## Lot 8 : Modernisation du front (optionnel, +1 à 1,5 j)

Seulement si le reste est livré et que le besoin existe.
- Remplacer Bluff (`bluff-src.js`, `js-class.js`) par Chart.js (déjà dans le bundle `stats.js`) et Leaflet 0.5 (CDN) par Leaflet 1.9 packagé via webpack (suppression de la dépendance à `cdnjs`).
- Mutualiser les helpers (tableaux « autres… », pourcentages) en un module JS plutôt que des `document.write` inline.
- Supprimer le `console.log` de debug de `stats_compare.html` et `admin/stats.html`.

## 4. Risques et points ouverts

| Risque | Mitigation |
|---|---|
| Codes postaux saisis erronés / homonymes | Paliers de lookup + rapport des non résolues (lot 4) ; on préfère `None` à une localisation fausse |
| Pays peu courants non couverts par GeoNames | La liste des pays importés est dérivée des données ; les équipes restantes apparaissent « Non localisé » |
| Régions GeoNames différentes de celles de MapQuest | Étendre `REGION_NORMALISATION` (lot 5), les `Ville` MapQuest historiques restent normalisées par le même dictionnaire |
| Surcomptage éventuel de `equipiers_count` | Vérifier sur un dump avant de modifier (section 1, point 6) ; hors lots sauf confirmation |
| Licence GeoNames (CC BY 4.0) | Attribution visible sur la page de stats (lot 2) |
| Clé MapQuest committée | La révoquer côté MapQuest et la retirer du dépôt (lot 1) |
