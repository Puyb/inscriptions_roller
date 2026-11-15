# Plan — Export d'une course vers EnduChrono

Document de travail, aucune ligne de code applicatif n'a été modifiée pour produire cette analyse. Voir aussi la spec miroir côté EnduChrono : `../../enduchrono/docs/import_enduroller.md`.

## 1. Résumé du besoin

EnduChrono (`../../enduchrono`, application de chronométrage, projet séparé) doit pouvoir créer une nouvelle course en récupérant directement les inscriptions (équipes, équipiers, transpondeurs) d'une course Enduroller, sans passer par un export/import manuel de fichiers.

Depuis EnduChrono, l'organisateur clique sur "Importer depuis Enduroller", ce qui l'envoie vers une page Enduroller de sélection de course. Une fois la course choisie, Enduroller affiche une page contenant un **formulaire caché auto-soumis** qui poste directement vers EnduChrono (chez lui, sur le réseau du lieu de course) les 3 fichiers nécessaires (équipes, équipiers, transpondeurs), générés à la volée dans le format attendu par EnduChrono.

Aucune connexion serveur-à-serveur : c'est le **navigateur de l'organisateur** qui relaie les données d'Enduroller (Internet) vers EnduChrono (souvent sur un réseau local non exposé). Enduroller reçoit en paramètre, dès le premier lien, l'URL de callback (où poster) et l'URL de retour (où rediriger le navigateur une fois l'import fait) — ces deux URLs sont fournies par EnduChrono, Enduroller ne les connaît pas à l'avance.

## 2. Constats sur l'existant

- **Sélection de course** : `CourseAdminSite.course_choose` (`inscriptions/admin_course.py:88`), route `choose/` (`get_urls`, ligne 70), template `admin/course_choose.html`. Liste les courses accréditées pour l'utilisateur courant (+ toutes les courses si superuser), chaque ligne étant un lien `/{{ course.uid }}/admin/`. `has_permission` (ligne 52) autorise explicitement toute URL finissant par `/choose/` sans exiger de cookie `course_uid` — seule l'authentification Enduroller (login) est requise.
- **Fichiers CSV déjà générés pour le chronométrage** : `inscriptions/admin_views.py` définit 4 vues non authentifiées (`dossardsCSV`, `dossardsEquipesCSV`, `dossardsEquipiersCSV`, `transpondeursCSV`, lignes 37/106/138/81), routées dans `inscriptions/urls.py:68-71` sous `/<course_uid>/dossards*.csv` et `/<course_uid>/transpondeurs.csv`, et exposées à l'organisateur depuis `templates/admin/dashboard.html:286-306` ("Fichiers CSV (pour le chronomètrage)"). **Leurs colonnes correspondent exactement** à ce qu'attend EnduChrono (confirmé côté EnduChrono, cf. spec miroir §2) :
  - `dossardsEquipesCSV` (ligne 106) → `equipe,nom,categorie,gerant_nom,gerant_prenom,gerant_ville,gerant_code_postal,gerant_code_pays`
  - `dossardsEquipiersCSV` (ligne 138) → `equipe,dossard,nom,prenom,sexe,date_de_naissance,num_licence`
  - `transpondeursCSV` (ligne 81) → `dossard,id`

  Ce sont ces 3 vues, déjà en production et déjà utilisées par les organisateurs pour le chronométrage manuel, qu'il faut réutiliser telles quelles pour produire le contenu des 3 fichiers — aucune nouvelle fonction de génération ni transformation de colonnes n'est nécessaire (voir §4.3, simple extraction du contenu sans passer par une réponse HTTP).
- **Modèle `Course`** (`inscriptions/models.py:139`) : `nom`, `uid`, `date` (DateField, pas d'heure). Pas de champ "date+heure d'export" — l'horodatage ISO 8601 demandé par EnduChrono est celui du **moment de l'export**, pas la date de course.
- **Modèle `Equipier`** (`models.py:837`) : `numero` (position dans l'équipe, 1-based, **pas** un dossard), `dossard()` = `equipe.numero * 10 + equipier.numero` (méthode calculée, jamais stockée). `dossardsEquipiersCSV` (ligne 138) n'applique aucun filtre sur `numero` par rapport à `equipe.nombre` — tous les `Equipier` de la course sont exportés, y compris au-delà du nombre réel d'inscrits dans l'équipe. Comportement conservé à l'identique (§4.3, §5) puisqu'il s'agit du même export déjà utilisé en production pour le chronométrage.
- **Modèle `Transpondeur`** (`models.py`, déjà implémenté et utilisé en production par `transpondeursCSV`, ligne 81 — cf. `docs/transpondeurs-plan.md` pour le détail de la conception) : lié soit à `Equipe` soit à `Equipier` selon `course.transpondeur_mode`. `transpondeursCSV` montre déjà comment recalculer un "dossard" pour le mode équipe (compteur `%d%d` par équipe) vs le mode équipier (`t.equipier.dossard()`), et comment exclure les transpondeurs non assignés (`.exclude(equipe=None, equipier=None)`) — logique reprise à l'identique via le refactor du §4.3.
- **Permissions (`has_permission`, `admin_course.py:52`)** : toute URL non listée explicitement exige un cookie `course_uid` correspondant à une accréditation. Les nouvelles URLs de ce plan (choix en mode export, génération du formulaire) doivent soit être ajoutées à la liste des exceptions, soit vérifier l'accréditation manuellement dans la vue (pattern déjà utilisé par `course_ask_accreditation`, ligne 100, qui ne dépend pas du cookie).
- Aucune intégration serveur-à-serveur existante avec un système externe (les seules intégrations actuelles sont les webhooks de paiement Stripe/PayPal/HelloAsso). Ce plan introduit le premier mécanisme de ce type, mais **sans jamais faire d'appel HTTP sortant depuis Enduroller** — tout passe par le navigateur (§1).

## 3. Nouvelles routes

Toutes montées sur `CourseAdminSite` (`site = CourseAdminSite(name='course')`, préfixe `/course/`), à côté des routes existantes (`admin_course.py:69-84`) :

```python
url(r'^choose/import/$', self.admin_view(self.course_choose_import), name='course_choose_import'),
url(r'^export-enduchrono/(?P<course_uid>[^/]+)/$', self.admin_view(self.export_enduchrono), name='course_export_enduchrono'),
```

- `GET /course/choose/import/?callback=<url>&redirect=<url>` : variante de `course_choose` (§4.1), liste les mêmes courses accréditées, mais dont les liens pointent vers `export_enduchrono` (au lieu de `/{uid}/admin/`) en conservant `callback`/`redirect` en querystring.
- `GET /course/export-enduchrono/<course_uid>/?callback=<url>&redirect=<url>` : génère les 3 CSV et affiche le formulaire auto-soumis (§4.2, §5, §6).

`has_permission` (`admin_course.py:52-65`) : ajouter `request.path.endswith('/choose/import/')` à la liste des chemins toujours autorisés (même ligne que `/choose/`, ligne 60). Pour `export_enduchrono`, ne pas ajouter d'exception globale (l'URL contient un `course_uid` arbitraire) — la vue vérifie elle-même l'accréditation (§4.2), comme `course_ask_accreditation`.

## 4. Vues

### 4.1 `course_choose_import` — sélection de course en mode export

Réutilise la logique de filtrage de `course_choose` (même queryset par accréditation), template dédié ou variante du template existant avec un paramètre indiquant le mode :

```python
def course_choose_import(self, request):
    request.current_app = self.name
    accreditations = request.user.accreditations.all()
    qs = Course.objects.filter(date__gte=datetime.now() - timedelta(days=60))
    params = urlencode({'callback': request.GET['callback'], 'redirect': request.GET['redirect']})
    return TemplateResponse(request, 'admin/course_choose_import.html', dict(self.each_context(request),
        courses=qs.filter(accreditations__in=accreditations).order_by('date'),
        params=params,
    ))
```

Template (`admin/course_choose_import.html`, dérivé de `course_choose.html`) : chaque lien devient `/course/export-enduchrono/{{ course.uid }}/?{{ params }}` au lieu de `/{{ course.uid }}/admin/`. Pas de gestion "courses sans accréditation / superadmin" ici (contrairement à `course_choose` — l'export ne concerne que les courses de l'organisateur, pas l'administration technique).

**Point ouvert** : `callback`/`redirect` doivent être validés a minima (ex. présence obligatoire, sinon 400) — pas de validation de domaine prévue (cohérent avec la position prise côté EnduChrono, cf. spec miroir §6).

### 4.2 `export_enduchrono` — génération et page auto-soumise

```python
def export_enduchrono(self, request, course_uid):
    request.current_app = self.name
    course = get_object_or_404(Course, uid=course_uid)
    if not (request.user.is_superuser or request.user.accreditations.filter(course=course).exclude(role='').exists()):
        return HttpResponseForbidden()

    name = '%s %s' % (course.nom, datetime.now().astimezone(timezone('Europe/Paris')).isoformat())

    return TemplateResponse(request, 'admin/export_enduchrono.html', dict(self.each_context(request),
        callback=request.GET['callback'],
        redirect=request.GET['redirect'],
        name=name,
        equipes_csv=_dossards_equipes_csv_content(course.uid).decode('utf-8'),
        equipiers_csv=_dossards_equipiers_csv_content(course.uid).decode('utf-8'),
        transpondeurs_csv=_transpondeurs_csv_content(course.uid).decode('utf-8'),
    ))
```

Vérification d'accréditation manuelle (pas de dépendance au cookie `course_uid`, cf. §3) — même pattern que `course_ask_accreditation` (`admin_course.py:100`).

`datetime.now().astimezone(timezone('Europe/Paris')).isoformat()` : même pattern que celui déjà utilisé dans `get_stats_api` (`admin_course.py:622-623`) pour produire un ISO 8601 avec offset explicite (ex. `2026-07-22T14:30:00+02:00`).

### 4.3 Réutilisation des vues CSV existantes — pas de nouvelle logique de génération

Les 3 vues existantes (`dossardsEquipesCSV`, `dossardsEquipiersCSV`, `transpondeursCSV`) produisent déjà exactement les colonnes attendues (§2, §5) — **aucune nouvelle fonction de génération n'est nécessaire**. Le seul obstacle technique : ces vues renvoient directement un `HttpResponse`, alors que `export_enduchrono` a besoin du **texte CSV brut** pour le placer dans les champs cachés du formulaire (§6).

Refactor minimal proposé : extraire, pour chacune des 3 vues, la construction du CSV dans une fonction séparée qui renvoie la chaîne (ou les bytes) plutôt qu'un `HttpResponse`, et faire de la vue existante un simple appelant de cette fonction — comportement des 3 URLs `/<course_uid>/dossards_equipes.csv` etc. strictement inchangé :

```python
def _dossards_equipes_csv_content(course_uid, code='utf-8'):
    out = io.StringIO()
    o = csv.writer(out, dialect='excel')
    o.writerow(['equipe', 'nom', 'categorie', 'gerant_nom', 'gerant_prenom', 'gerant_ville', 'gerant_code_postal', 'gerant_code_pays'])
    for e in Equipe.objects.filter(course__uid=course_uid):
        row = [e.numero, e.nom, e.categorie, e.gerant_nom, e.gerant_prenom, e.gerant_ville, e.gerant_code_postal, e.gerant_pays]
        o.writerow([str(i) for i in row])
    return out.getvalue().encode(code)

def dossardsEquipesCSV(request, course_uid):
    code = request.GET.get('code', 'utf-8')
    r = HttpResponse(_dossards_equipes_csv_content(course_uid, code), content_type='text/csv', charset=code)
    return r
```

Même traitement pour `dossardsEquipiersCSV` → `_dossards_equipiers_csv_content` et `transpondeursCSV` → `_transpondeurs_csv_content` (logique interne inchangée, y compris le calcul du "dossard" transpondeur selon `course.transpondeur_mode`, déjà correct dans le code existant, lignes 92-97).

`export_enduchrono` (§4.2) appelle directement ces 3 fonctions `_..._content(course.uid)` et les décode en texte pour les passer au template. Si `course.transpondeur_mode` n'est pas configuré pour cette course (aucun transpondeur assigné), `_transpondeurs_csv_content` renvoie un CSV avec seulement l'en-tête — comportement accepté côté EnduChrono (cf. spec miroir §4.1).

## 5. Mapping des colonnes

Correspondance exacte, confirmée avec le format réellement attendu par EnduChrono (colonnes des tables `equipes`/`equipiers`/`transpondeurs` de `classements`, cf. spec miroir §2) — **aucune transformation de colonne n'est nécessaire**, les 3 vues existantes sont réutilisées telles quelles (§4.3) :

| Fichier EnduChrono | Colonnes attendues | Vue Enduroller réutilisée |
|---|---|---|
| `equipes` | `equipe,nom,categorie,gerant_nom,gerant_prenom,gerant_ville,gerant_code_postal,gerant_code_pays` | `dossardsEquipesCSV` (`admin_views.py:106`) — colonnes identiques |
| `equipiers` | `equipe,dossard,nom,prenom,sexe,date_de_naissance,num_licence` | `dossardsEquipiersCSV` (`admin_views.py:138`) — colonnes identiques |
| `transpondeurs` | `dossard,id` | `transpondeursCSV` (`admin_views.py:81`) — colonnes identiques |

Le filtrage/absence de filtrage des équipes et équipiers exportés (dossier incomplet, paiement non reçu, équipiers au-delà de `equipe.nombre`, etc.) est celui déjà en place dans ces 3 vues aujourd'hui — comportement déjà validé en production pour cet usage précis (organisateurs les utilisant déjà pour le chronométrage manuel, cf. `dashboard.html:286-306`), non modifié par ce plan.

## 6. Template de la page auto-soumise

`templates/admin/export_enduchrono.html` — page minimale, dans l'esprit du script inline déjà présent dans `dashboard.html:18-20` :

```html
{% extends "admin/base_site_common.html" %}
{% block content %}
<form id="export-form" method="post" action="{{ callback }}" enctype="multipart/form-data">
    <input type="hidden" name="name" value="{{ name }}">
    <input type="hidden" name="redirect" value="{{ redirect }}">
    <textarea style="display:none" name="equipes">{{ equipes_csv }}</textarea>
    <textarea style="display:none" name="equipiers">{{ equipiers_csv }}</textarea>
    <textarea style="display:none" name="transpondeurs">{{ transpondeurs_csv }}</textarea>
</form>
<script>document.getElementById('export-form').submit()</script>
{% endblock %}
```

`<textarea>` plutôt que `<input type="hidden" value="...">` : le contenu CSV (guillemets, retours ligne, virgules) est un nœud texte à l'intérieur de la balise, donc seul l'échappement HTML standard de Django (`{{ }}`, auto-échappement activé) s'applique — pas de risque de casser l'attribut `value` avec un caractère spécial, contrairement à un `<input>`.

Pas de token CSRF nécessaire : c'est une requête **sortante** d'Enduroller vers EnduChrono, la protection CSRF Django protège les requêtes entrantes vers Enduroller, pas celle-ci.

## 7. Points ouverts / hypothèses à confirmer

1. Faut-il restreindre `export_enduchrono` à des courses "actives" (`course.active=True`) uniquement, comme un garde-fou supplémentaire ? Non traité ici, à trancher si besoin.
2. Pas de mécanisme pour re-synchroniser une course déjà exportée (l'export crée toujours une nouvelle course côté EnduChrono) — cohérent avec le comportement EnduChrono actuel (`POST /import` crée toujours un nouveau fichier), pas un manque à combler dans ce plan.

## 8. Plan d'action (étapes d'implémentation)

1. **`admin_course.py`** : ajouter `choose/import/` à `has_permission` (exception, ligne ~60) et aux `get_urls()` (§3) ; nouvelles méthodes `course_choose_import` (§4.1) et `export_enduchrono` (§4.2).
2. **`admin_views.py`** : refactor minimal de `dossardsEquipesCSV`, `dossardsEquipiersCSV`, `transpondeursCSV` pour extraire leur construction CSV dans 3 fonctions réutilisables `_dossards_equipes_csv_content`, `_dossards_equipiers_csv_content`, `_transpondeurs_csv_content` (§4.3) — comportement des 3 vues existantes inchangé, juste appelées par `export_enduchrono` en plus.
3. **Templates** : `admin/course_choose_import.html` (variante de `course_choose.html`), `admin/export_enduchrono.html` (§6).
4. **Tests** (`inscriptions/tests/`) : non-régression des 3 vues CSV existantes après refactor (§4.3, mêmes colonnes/mêmes URLs), page `course_choose_import` (liste filtrée par accréditation, `callback`/`redirect` transmis), page `export_enduchrono` (403 si non accrédité, contenu du formulaire généré identique au contenu des 3 CSV existants).
5. Coordination avec l'implémentation côté EnduChrono (`../../enduchrono/docs/import_enduroller.md`) : noms des paramètres `callback`/`redirect` doivent rester synchronisés entre les deux specs (le format des 3 fichiers, lui, est déjà figé et confirmé, §5).

Aucun fichier n'a été modifié pour produire ce document — seule une exploration en lecture seule du code existant a été faite.
