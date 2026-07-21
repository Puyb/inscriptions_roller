# Plan — Assignation de transpondeurs

Document de travail, aucune ligne de code applicatif n'a été modifiée pour produire cette analyse.

## 1. Résumé du besoin

L'organisateur d'une course doit pouvoir assigner des numéros de transpondeurs (puces de chronométrage) aux équipes ou aux équipiers, depuis le backoffice course (`/course/`).

- **Deux modes**, choisis par course :
  - **"Par équipe"** : chaque équipe se voit assigner N transpondeurs non nominatifs, partagés entre équipiers (typiquement N=2).
  - **"Par équipier"** : chaque équipier a ses propres transpondeurs (typiquement 1, mais un solo peut en avoir 2).
- Le **nombre de transpondeurs par équipe/équipier dépend de la catégorie** (tableau catégorie → nombre).
- L'organisateur **uploade un fichier texte ASCII** (1 code transpondeur par ligne, trié) : tout caractère non-ASCII ou non affichable dans le fichier est une erreur bloquante, aucun double décodage (pas de repli `utf-8`/`iso8859-1`).
- L'assignation se fait automatiquement, dans l'**ordre des numéros de dossard** (équipe ou équipier selon le mode) ; si une équipe/un équipier a plusieurs transpondeurs, ils doivent être **consécutifs** dans le fichier.
- Si le total de transpondeurs uploadés est **insuffisant**, on affiche une erreur et **rien n'est enregistré** (opération atomique).
- Si le fichier contient des **doublons**, on affiche une erreur et rien n'est enregistré.
- Une fois assignée, la liste est affichée via l'**admin standard** (voir §5), avec édition manuelle possible (numéro, équipe/équipier associé) et ajout manuel d'un transpondeur.
- Les transpondeurs assignés sont aussi visibles (et éditables quand c'est possible) sur la **fiche équipe**.
- Un moyen de **réinitialiser la liste** doit permettre de revenir au formulaire d'upload.
- Une nouvelle **icône "Transpondeurs"** doit apparaître dans le dashboard organisateur.
- **Hors scope pour cette version** : la détection d'anomalies (transpondeurs manquants, doublons, etc.) pour les équipes/équipiers ajoutés après l'assignation initiale sera traitée plus tard, en même temps qu'une future fonctionnalité de téléchargement de la liste des transpondeurs assignés. Ce plan ne couvre donc que l'upload initial, l'admin standard, et l'affichage lecture seule sur la fiche équipe.

## 2. Constats sur l'existant (`inscriptions/models.py`)

- Pas de champ ni de modèle "transpondeur" existant (confirmé par grep sur tout le dépôt).
- `Categorie` (l.398) a déjà un pattern de **configuration numérique par catégorie** pour les dossards (`numero_debut`, `numero_fin`, `ajouter_nombre`) — même esprit à réutiliser pour le nombre de transpondeurs par catégorie.
- Pas de flag "solo" : solo/duo/relais se déduit de `min_equipiers`/`max_equipiers`. Donc rien à faire de spécial pour "les solos ont souvent 2 transpondeurs" — ça découle naturellement du tableau par catégorie.
- `Equipe.numero` (l.529) = numéro de dossard équipe, unique par course. `Equipe.nombre` = nombre d'équipiers réellement inscrits dans l'équipe (peut différer de `min/max_equipiers` de la catégorie).
- `Equipier.numero` (l.765) = position dans l'équipe (1-based), **pas** un dossard. `Equipier.dossard()` est **calculé** (`equipe.numero * 10 + equipier.numero`), jamais stocké. Les équipiers "actifs" d'une équipe sont ceux avec `numero <= equipe.nombre` (convention déjà utilisée ailleurs, ex. `licence_manquantes()`).
- **Pas de statut "annulé/désactivé"** sur `Equipe` — pour l'ordre d'assignation, on prend toutes les équipes de la course, sans filtre d'exclusion.
- Le dashboard organisateur (`admin_course.py`, `CourseAdminSite`) ajoute ses pages custom via `get_urls()` + méthodes `admin_view(...)` renvoyant un `TemplateResponse`. Le template `admin/dashboard.html` a une section `Imports` avec des tuiles `<a><i class="fa fa-...">...<label>` — c'est là qu'ajouter la tuile "Transpondeurs". D'autres tuiles du dashboard pointent déjà directement vers des changelists d'admin standard (ex. équipes) — on suit ce même principe plutôt que de construire une page de listing custom.
- Le meilleur exemple d'upload de fichier + traitement est `CourseAdminSite.resultats()` (import CSV des résultats) : formulaire (`ImportResultatForm` dans `forms.py`), traitement dans `transaction.atomic()` avec une exception locale pour annuler proprement et ré-afficher le formulaire avec une erreur via `messages.add_message(..., messages.ERROR, ...)`. On suit ce pattern pour la structure de la vue, **à l'exception du décodage** : `resultats()` fait un décodage `utf-8` puis repli `iso8859-1` — pour le fichier de transpondeurs, décision actée de ne **pas** reproduire ce double décodage (voir §4.1).
- `CourseFilteredObjectAdmin` (`admin_course.py`) est la base habituelle des `ModelAdmin` scopés à la course courante (cookie `course_uid` + `Accreditation`) — c'est elle qu'on réutilise pour le nouveau `TranspondeurAdmin`, comme pour `EquipeAdmin`/`EquipierAdmin`.
- Prochaine migration disponible : `0083_...` (dernière existante : `0082_course_lien_externe.py`).
- `receivers.py` (via `AppConfig.ready`) accorde automatiquement les permissions de gestion à tout nouvel utilisateur pour les modèles que l'organisateur doit pouvoir gérer — si on ajoute un modèle `Transpondeur`, il faut l'ajouter là (et rattraper les utilisateurs existants via une migration de données, voir §3.5).
- `admin_course.CourseAdmin` (fiche course organisateur) construit ses champs via `get_fields(request, obj)` avec juste `exclude = ('active',)` — tout nouveau champ du modèle `Course` y apparaît donc **automatiquement** sauf à l'exclure explicitement. `admin_main.CourseAdmin` (fiche course superuser, `/admin/`) n'a ni `fields` ni `exclude` : un `ModelAdmin` par défaut, donc pareil, tout nouveau champ y apparaît automatiquement. À l'inverse, `admin_course.CategorieAdmin` déclare un `fieldsets` explicite listant chaque champ un par un : un nouveau champ de modèle n'y apparaît **pas** tant qu'il n'est pas ajouté explicitement à ce `fieldsets`. Point important pour §3.5 (ne pas impacter les formulaires existants).

## 3. Modèle de données proposé

### 3.1 `Course` — nouveau champ

```python
class Course(models.Model):
    ...
    TRANSPONDEUR_MODE_EQUIPE = 'equipe'
    TRANSPONDEUR_MODE_EQUIPIER = 'equipier'
    TRANSPONDEUR_MODE_CHOICES = (
        (TRANSPONDEUR_MODE_EQUIPE, _(u"Par équipe (non nominatif)")),
        (TRANSPONDEUR_MODE_EQUIPIER, _(u"Par équipier (nominatif)")),
    )
    transpondeur_mode = models.CharField(_(u"Mode d'assignation des transpondeurs"),
                                          max_length=10, choices=TRANSPONDEUR_MODE_CHOICES,
                                          null=True, blank=True)
```

`null=True` tant qu'aucun upload n'a eu lieu (permet de distinguer "jamais configuré" de "configuré avec le mode équipe"), et sert aussi de signal pour savoir si la liste a été réinitialisée.

### 3.2 `Categorie` — nouveau champ

```python
class Categorie(models.Model):
    ...
    nombre_transpondeurs = models.PositiveIntegerField(
        _(u"Nombre de transpondeurs (par équipe ou par équipier selon le mode de la course)"),
        default=1)
```

Un même champ sert pour les deux modes ; sa signification ("par équipe" ou "par équipier") dépend de `course.transpondeur_mode` au moment de l'assignation. Valeur `0` autorisée (catégorie sans transpondeur, ex. catégorie non chronométrée).

### 3.3 Nouveau modèle `Transpondeur`

```python
class Transpondeur(models.Model):
    course   = models.ForeignKey(Course, related_name='transpondeurs', on_delete=models.CASCADE)
    ordre    = models.PositiveIntegerField()          # position dans le fichier uploadé (1-based)
    numero   = models.CharField(_(u"Numéro de transpondeur"), max_length=50)
    equipe   = models.ForeignKey(Equipe, null=True, blank=True,
                                  related_name='transpondeurs', on_delete=models.SET_NULL)
    equipier = models.ForeignKey(Equipier, null=True, blank=True,
                                  related_name='transpondeurs', on_delete=models.SET_NULL)

    class Meta:
        unique_together = (('course', 'ordre'), ('course', 'numero'))
        ordering = ['ordre']
```

Décisions actées :
- **Champ `ordre` conservé** : il fixe explicitement la position dans le fichier uploadé, pour garantir que la liste s'affiche toujours dans le même ordre que le fichier d'origine (indépendamment de l'ordre d'insertion en base ou d'éventuels ajouts manuels ultérieurs). Un transpondeur ajouté manuellement via l'admin se voit attribuer l'`ordre` suivant (max existant + 1) pour la course.
- **Format du numéro : texte libre** (`CharField`), pas d'hypothèse de format numérique (codes de puce RFID potentiellement alphanumériques). Le tri "dans l'ordre du fichier" repose donc sur `ordre`, jamais sur un tri lexicographique/numérique de `numero`.
- Un upload = régénération complète : suppression de tous les `Transpondeur` existants de la course puis recréation, une ligne par transpondeur du fichier, dans l'ordre (`ordre` = position 1-based dans le fichier).
- `equipe`/`equipier` restent `null` pour les transpondeurs excédentaires (surplus non assigné en cas de fichier plus long que nécessaire).
- `on_delete=SET_NULL` : si une équipe/un équipier est supprimé après coup, la ligne transpondeur redevient "non assignée" plutôt que de disparaître silencieusement.
- Un seul des deux FK (`equipe`/`equipier`) est renseigné, selon `course.transpondeur_mode` — pas de contrainte DB pour l'exclusivité (comme ailleurs dans le code, ex. `PaiementRepartition`), juste respecté par le code d'assignation et validé dans le formulaire d'édition admin (voir §5.2).

### 3.4 Migration

`0083_transpondeur.py` : `AddField(Course.transpondeur_mode)`, `AddField(Categorie.nombre_transpondeurs)`, `CreateModel(Transpondeur)`.

### 3.5 Ne pas impacter les formulaires existants de `Course`/`Categorie`

Décision : les nouveaux champs `Course.transpondeur_mode` et `Categorie.nombre_transpondeurs` ne doivent **pas** apparaître dans les formulaires standards de création/édition de ces objets (ils sont gérés uniquement via le formulaire d'upload §5.4 et l'admin `Transpondeur` §5.2). Conséquence concrète, d'après le constat du §2 :

- `inscriptions/admin_course.py` → `CourseAdmin.exclude` : ajouter `'transpondeur_mode'` (actuellement `exclude = ('active', )`), pour qu'il ne soit pas inclus par `get_fields(request, obj)`.
- `inscriptions/admin_main.py` → `CourseAdmin` (superuser) : ajouter explicitement `exclude = ('transpondeur_mode', )` (actuellement aucun `fields`/`exclude`, donc tout champ de modèle est inclus par défaut).
- `inscriptions/admin_course.py` → `CategorieAdmin.fieldsets` : **déjà sûr par construction** (fieldsets explicite, `nombre_transpondeurs` n'y est simplement pas listé) — aucune modification requise, mais un test de non-régression est prévu (§8) pour le garantir dans la durée.
- Le champ `nombre_transpondeurs` par catégorie est saisi/modifié uniquement depuis le tableau du formulaire d'upload (§5.4), pas depuis la fiche `Categorie` standard.

### 3.6 Permissions — utilisateurs existants et nouveaux

`receivers.py` (`post_save` sur `User`) n'accorde les permissions de gestion qu'aux **nouveaux** utilisateurs créés après le déploiement. Décision : les utilisateurs existants doivent recevoir les mêmes permissions sur `Transpondeur`, via une **migration de données** (`RunPython`) livrée avec la migration `0083` (ou une `0084` dédiée juste après, selon préférence au moment du code) :

```python
def grant_transpondeur_permissions(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Permission = apps.get_model('auth', 'Permission')
    perms = Permission.objects.filter(
        content_type__app_label='inscriptions',
        codename__in=('add_transpondeur', 'change_transpondeur', 'delete_transpondeur'),
    )
    for user in User.objects.all():
        user.user_permissions.add(*perms)
```

Et dans `receivers.py`, ajouter à la liste déjà accordée aux nouveaux utilisateurs (`handle_user_postsave`) :

```python
Permission.objects.get(codename='add_transpondeur'),
Permission.objects.get(codename='change_transpondeur'),
Permission.objects.get(codename='delete_transpondeur'),
```

## 4. Algorithme d'assignation (upload)

### 4.1 Lecture et validation du fichier (ASCII strict)

Décision actée : le fichier uploadé est considéré comme **ASCII strict**, sans repli d'encodage. Pas de tentative `utf-8` puis `iso8859-1` comme dans `resultats()` (§2) — un seul décodage `ascii`, et toute présence de caractère non-ASCII ou non affichable est une erreur bloquante (rien n'est enregistré) :

```python
def parse_transpondeurs_file(f):
    raw = f.read()
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError:
        raise InvalidTranspondeurFileException(_(u"Le fichier doit être encodé en ASCII (caractère non-ASCII détecté)."))

    codes = []
    for line in text.splitlines():
        code = line.strip()
        if not code:
            continue
        if not all(0x20 <= ord(c) <= 0x7E for c in code):
            raise InvalidTranspondeurFileException(_(u"Le fichier contient des caractères non affichables."))
        codes.append(code)
    return codes
```

`InvalidTranspondeurFileException` : nouvelle exception, remontée à la vue d'upload comme les deux autres (§4.2) pour afficher une erreur et ré-afficher le formulaire sans rien avoir modifié.

### 4.2 Assignation

Méthode proposée : `Course.assign_transpondeurs(self, mode, codes)` dans `models.py` (même esprit que `Equipe.getNumero()` / `Categorie.get_prefix()`), appelée depuis la vue d'upload dans un `transaction.atomic()`, avec `codes` déjà validé par `parse_transpondeurs_file()` (§4.1).

```
def assign_transpondeurs(self, mode, codes):
    # codes : liste de str, dans l'ordre du fichier, déjà validée (ASCII, non vide, strip) par parse_transpondeurs_file()

    # doublons -> erreur, rien n'est fait
    doublons = {c for c in codes if codes.count(c) > 1}
    if doublons:
        raise DuplicateTranspondeurException(doublons)

    if mode == Course.TRANSPONDEUR_MODE_EQUIPE:
        unites = list(self.equipes.order_by('numero'))
        compte = lambda e: e.categorie.nombre_transpondeurs
    else:
        unites = [eq for e in self.equipes.order_by('numero').select_related('categorie')
                    for eq in e.equipiers.filter(numero__lte=e.nombre).order_by('numero')]
        compte = lambda eq: eq.equipe.categorie.nombre_transpondeurs

    total_requis = sum(compte(u) for u in unites)
    if total_requis > len(codes):
        raise NotEnoughTranspondeursException(total_requis, len(codes))

    self.transpondeurs.all().delete()
    self.transpondeur_mode = mode
    self.save(update_fields=['transpondeur_mode'])

    i = 0
    objs = []
    for u in unites:
        for _ in range(compte(u)):
            objs.append(Transpondeur(
                course=self, ordre=i + 1, numero=codes[i],
                equipe=u if mode == Course.TRANSPONDEUR_MODE_EQUIPE else None,
                equipier=u if mode == Course.TRANSPONDEUR_MODE_EQUIPIER else None,
            ))
            i += 1
    for code in codes[i:]:            # transpondeurs excédentaires : non assignés
        i += 1
        objs.append(Transpondeur(course=self, ordre=i, numero=code))
    Transpondeur.objects.bulk_create(objs)
```

`NotEnoughTranspondeursException` et `DuplicateTranspondeurException` : nouvelles exceptions (même famille que `NoPlaceLeftException` déjà utilisée pour la numérotation des dossards), remontées jusqu'à la vue pour afficher un message d'erreur et ré-afficher le formulaire sans rien avoir modifié. La détection de doublon se fait avant toute écriture, donc pas de rollback nécessaire dans ce cas — le `transaction.atomic()` reste utile pour la partie suppression+recréation elle-même.

## 5. Interface organisateur

### 5.1 Dashboard — nouvelle icône

Dans `templates/admin/dashboard.html`, section `Imports` (à côté de "Résultats") :

```html
<td>
    <a href="{% url "admin:inscriptions_transpondeur_changelist" %}">
        <i class="fa fa-microchip"></i><br />
        <label>{% blocktrans %}Transpondeurs{% endblocktrans %}</label>
    </a>
</td>
```

Le lien pointe directement vers la **changelist admin standard** du modèle `Transpondeur` (pas de vue custom de listing) : c'est cette changelist qui décide, selon qu'il existe ou non déjà des transpondeurs pour la course, d'afficher la liste standard ou de rediriger vers le formulaire d'upload (§5.2).

### 5.2 `TranspondeurAdmin` — liste, édition, ajout (admin standard)

Enregistré sur `admin_course.site`, base `CourseFilteredObjectAdmin` (filtrage automatique par course courante + accréditation, comme `EquipeAdmin`) :

```python
class TranspondeurAdmin(CourseFilteredObjectAdmin):
    list_display = ('ordre', 'numero', 'assigne_a')
    ordering = ('ordre',)
    search_fields = ('numero',)
    form = TranspondeurForm   # filtre equipe/equipier sur la course courante + valide l'exclusivité equipe/equipier selon course.transpondeur_mode

    def assigne_a(self, obj):
        ...  # "Équipe 12 (Nom capitaine)" / "Équipier — dossard 121 (Nom Prénom)" / "— non assigné —"

    def changelist_view(self, request, extra_context=None):
        course = getCourse(request)
        if not course.transpondeurs.exists():
            return redirect('admin:course_transpondeurs')   # vue d'upload, cf. §5.4
        return super().changelist_view(request, extra_context)

    def get_urls(self):
        return [
            url(r'^reset/$', self.admin_site.admin_view(self.reset_view), name='course_transpondeurs_reset'),
        ] + super().get_urls()

    def reset_view(self, request):
        # POST uniquement (confirmation côté template) : supprime tous les Transpondeur
        # de la course courante + remet course.transpondeur_mode à None, puis redirige
        # vers la changelist (qui re-redirigera elle-même vers le formulaire d'upload).
        ...

    def save_model(self, request, obj, form, change):
        if not change and not obj.ordre:
            course = getCourse(request)
            obj.ordre = (course.transpondeurs.aggregate(Max('ordre'))['ordre__max'] or 0) + 1
        super().save_model(request, obj, form, change)
```

`save_model` attribue automatiquement l'`ordre` suivant lors d'un ajout manuel via le bouton "Ajouter" (le champ `ordre` n'est donc pas présenté à la saisie, ou en lecture seule à l'ajout).

- **Édition manuelle standard** : `numero`, `equipe`, `equipier` restent des champs de formulaire admin classiques (dropdown/`raw_id_fields` filtrés sur la course courante) — l'organisateur peut changer le numéro et/ou l'équipe/équipier associé directement depuis la fiche de changement, avec les fonctions standard de l'admin (historique, validation, permissions).
- **Ajout manuel standard** : le bouton "Ajouter transpondeur" habituel de l'admin (`object-tools`) fonctionne tel quel.
- **Redirection vers le formulaire si vide** : `changelist_view` redirige vers la vue d'upload (§5.4) tant qu'aucun `Transpondeur` n'existe pour la course — couvre le cas "jamais uploadé" et le cas "réinitialisé".
- **Réinitialisation** : bouton ajouté dans le bloc `object-tools` de la changelist (à côté de "Ajouter"), via une **surcharge de template** `templates/admin/inscriptions/transpondeur/change_list.html` (extension standard du template d'admin, bloc `object-tools-items`), pointant vers la nouvelle route `course_transpondeurs_reset` définie ci-dessus. C'est une extension standard de l'admin (même mécanisme que d'autres pages custom du projet ajoutées via `get_urls()`), mais si la surcharge de template s'avère trop fragile en pratique (conflits avec le thème `pinax`/bootstrap déjà en place), **solution de repli** : une **action groupée** standard `"Réinitialiser la liste des transpondeurs"` dans le menu d'actions de la changelist, déclenchable après un "tout sélectionner" (fonctionnalité native de l'admin Django pour sélectionner toutes les lignes, y compris au-delà de la page courante) — ne nécessite aucune surcharge de template.

### 5.3 Formulaire de mapping equipe/equipier (`TranspondeurForm`, `forms.py`)

```python
class TranspondeurForm(forms.ModelForm):
    class Meta:
        model = Transpondeur
        fields = ('numero', 'equipe', 'equipier')

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['equipe'].queryset = course.equipes.all()
        self.fields['equipier'].queryset = Equipier.objects.filter(equipe__course=course)
        # le champ non pertinent pour course.transpondeur_mode est masqué/désactivé

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('equipe') and cleaned.get('equipier'):
            raise ValidationError(_(u"Un transpondeur ne peut être assigné qu'à une équipe OU un équipier, pas les deux."))
        return cleaned
```

### 5.4 Formulaire d'upload (état "aucun transpondeur")

Reste une vue custom sur `CourseAdminSite` (comme prévu initialement), car l'upload de fichier + configuration du mode/comptage par catégorie ne rentre pas dans le moule d'un `ModelAdmin` standard :

- `url(r'^transpondeurs/$', self.admin_view(self.transpondeurs), name='course_transpondeurs')`.
- GET : affiche `admin/transpondeurs_form.html` — sélecteur de mode (radio), tableau des catégories de la course avec un champ numérique `nombre_transpondeurs` par ligne (pré-rempli, éditable), champ fichier texte.
- POST : appelle `parse_transpondeurs_file()` (§4.1, décodage ASCII strict + rejet des caractères non affichables), sauvegarde les compteurs par catégorie, appelle `course.assign_transpondeurs(mode, codes)` ; en cas de `InvalidTranspondeurFileException`/`DuplicateTranspondeurException`/`NotEnoughTranspondeursException`, message d'erreur explicite et ré-affichage du formulaire avec les valeurs saisies ; en cas de succès, redirige vers `admin:inscriptions_transpondeur_changelist` (qui affichera cette fois la liste standard, puisque non vide).
- Si des transpondeurs existent déjà pour la course, cette vue redirige directement vers la changelist (évite d'exposer le formulaire d'upload tant qu'il faut d'abord réinitialiser).

### 5.5 Affichage sur la fiche équipe (lecture seule pour l'instant)

Décision : sur la fiche équipe, les transpondeurs sont **affichés mais pas modifiables** pour l'instant (l'édition réelle passe par la changelist `Transpondeur` standard, §5.2). Simplifie l'implémentation initiale ; une édition inline pourra être ajoutée plus tard si besoin.

- **Mode "par équipe"** : `TranspondeurInline(admin.TabularInline)` sur `EquipeAdmin`, `model = Transpondeur`, `fk_name = 'equipe'`, `extra = 0`, avec tous les champs en `readonly_fields` (`ordre`, `numero`) et `has_add_permission`/`has_change_permission`/`has_delete_permission` renvoyant `False` — affichage seul, pas d'édition.
- **Mode "par équipier"** : les transpondeurs sont rattachés à `Equipier`, pas à `Equipe` — l'admin Django ne supportant pas les inlines imbriqués (un inline dans un inline), on ajoute un champ calculé en lecture seule (ex. `transpondeurs_display`, liste des `numero` séparés par virgule, triée par `ordre`) dans les `readonly_fields` de l'inline `Equipier` existant sur `EquipeAdmin`.
- Dans les deux cas, un lien vers la changelist `Transpondeur` (filtrée sur l'équipe ou l'équipier) peut accompagner l'affichage pour faciliter la navigation vers l'édition réelle.

## 6. Points ouverts / hypothèses à confirmer

1. **Équipes/équipiers ajoutés après l'assignation** (inscriptions tardives) : **hors scope** pour cette version (cf. §1) — ils n'auront pas de transpondeur tant qu'on n'a pas réinitialisé + ré-uploadé la liste complète. La détection d'anomalies (transpondeurs manquants, doublons, etc.) sera traitée dans une future itération, en même temps que le téléchargement de la liste assignée. Un ajout manuel ponctuel reste possible entre-temps via l'admin standard (§5.2) pour les cas isolés, mais aucun outil de détection n'est prévu ici.
2. **Robustesse de la surcharge de template pour le bouton de réinitialisation** (§5.2) : à valider en pratique avec le thème admin actuel (`pinax-theme-bootstrap`) ; l'action groupée de repli est prévue si le template s'avère trop fragile à maintenir.
3. **Affichage lecture seule sur la fiche équipe** (§5.5) : décision actée de ne pas rendre ça éditable pour l'instant ; à réévaluer plus tard si le besoin d'édition inline (notamment en mode "par équipier", où l'admin Django ne supporte de toute façon pas les inlines imbriqués) se confirme.

## 7. Plan d'action (étapes d'implémentation)

1. **Migration `0083`** : `Course.transpondeur_mode`, `Categorie.nombre_transpondeurs`, modèle `Transpondeur` (+ exceptions `NotEnoughTranspondeursException`/`DuplicateTranspondeurException`/`InvalidTranspondeurFileException` dans `models.py`, aux côtés de `NoPlaceLeftException`) + migration de données `grant_transpondeur_permissions` (§3.6) pour les utilisateurs existants.
2. **`receivers.py`** : ajouter les permissions `add_transpondeur`/`change_transpondeur`/`delete_transpondeur` à la liste accordée aux nouveaux utilisateurs (§3.6).
3. **`models.py`** : méthode `Course.assign_transpondeurs(mode, codes)`, fonction `parse_transpondeurs_file()` (décodage ASCII strict, §4.1), méthode d'affichage `Transpondeur.assigne_a()`/`__str__`.
4. **`forms.py`** : `TranspondeurUploadForm` (mode + fichier), `TranspondeurForm` (ModelForm d'édition, filtré par course, validation exclusivité equipe/equipier).
5. **`admin_course.py`** :
   - Vue custom `transpondeurs()` (upload, état "vide" uniquement) sur `CourseAdminSite`.
   - `TranspondeurAdmin(CourseFilteredObjectAdmin)` : `changelist_view` avec redirection si vide, `reset_view` + route dédiée, `list_display`/`search_fields`/`form`.
   - `TranspondeurInline` ajouté à `EquipeAdmin` (mode équipe, lecture seule) + champ lecture seule `transpondeurs_display` sur l'inline équipier existant (mode équipier).
   - `CourseAdmin.exclude` : ajouter `'transpondeur_mode'` (§3.5).
6. **`admin_main.py`** : `CourseAdmin` (superuser) — ajouter `exclude = ('transpondeur_mode', )` (§3.5).
7. **Templates** :
   - `admin/transpondeurs_form.html` (mode + tableau catégories + upload).
   - `admin/inscriptions/transpondeur/change_list.html` (surcharge minimale pour ajouter le bouton "Réinitialiser" à côté de "Ajouter") — ou action groupée de repli si ce point s'avère problématique (§6.2).
   - Tuile "Transpondeurs" dans `admin/dashboard.html`.
8. **Factories** : `inscriptions/factories.py` — `nombre_transpondeurs` par défaut sur `CategorieFactory` si besoin pour les tests, éventuellement une `TranspondeurFactory`.
9. **Tests** (`inscriptions/tests/test_transpondeurs.py`) :
   - Assignation mode "équipe", comptage par catégorie, transpondeurs consécutifs.
   - Assignation mode "équipier", en tenant compte de `numero <= equipe.nombre` (équipiers actifs seulement).
   - Catégorie avec `nombre_transpondeurs = 0`.
   - Fichier avec doublons → exception, rien n'est créé.
   - Fichier insuffisant → exception, rien n'est créé/modifié (`Course.transpondeur_mode` inchangé).
   - Fichier contenant un caractère non-ASCII ou non affichable → `InvalidTranspondeurFileException`, rien n'est créé.
   - Surplus de transpondeurs → lignes en fin de liste non assignées.
   - Réinitialisation (`reset_view`) puis re-upload (régénération complète).
   - `changelist_view` redirige vers le formulaire quand la liste est vide, affiche la liste standard sinon.
   - Édition manuelle d'un `Transpondeur` via l'admin (changement de `numero`/`equipe`/`equipier`), y compris le rejet si `equipe` et `equipier` sont tous les deux renseignés.
   - Accès restreint par accréditation (comme les autres pages/`ModelAdmin` de `CourseAdminSite`).
   - **Non-régression formulaires** : le formulaire de création/édition `Course` (organisateur et superuser) et `Categorie` n'exposent pas `transpondeur_mode`/`nombre_transpondeurs` (§3.5).
   - Utilisateur existant (créé avant la migration) dispose bien des permissions `Transpondeur` après application de `grant_transpondeur_permissions` (§3.6).
10. **Traductions** : ajouter les nouvelles chaînes aux fichiers `.po` (`inscriptions/locale`) si le workflow de traduction du projet l'exige.

Aucun fichier n'a été modifié pour produire ce document — seule une exploration en lecture seule du code existant (`models.py`, `admin_course.py`, templates du dashboard, migrations) a été faite.
