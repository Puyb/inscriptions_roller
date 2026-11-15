# Spec : protection des pièces jointes des équipiers

> **Statut : à faire** (audit du 2026-11-14). Décision retenue : **servir les pièces jointes via une vue Django avec contrôle d'accès** (option 1 de l'audit), pas seulement un jeton plus long dans l'URL.

## 1. Contexte et constats

Les équipiers déposent des documents sensibles (données de santé au sens RGPD) :

| Champ | Contenu | Upload dans |
|---|---|---|
| `Equipier.piece_jointe` | certificat médical ou licence FFRS | `equipier_piece_jointe_filename` (`models.py`) |
| `Equipier.autorisation` | autorisation parentale (mineurs) | `equipier_autorisation_filename` (`models.py`) |

Constats :

1. **Aucun contrôle d'accès.** Les fichiers sont dans `MEDIA_ROOT` (`inscriptions/uploads`) et servis directement par uwsgi (`--static-map /uploads=/app/inscriptions/uploads`, `docker-start.sh`). Django n'est pas appelé : ni session, ni `Accreditation`, ni droit. Toute personne qui connaît l'URL télécharge le fichier, y compris un organisateur sans droit sur la course.
2. **Chemin** : `course_<edition.id>/equipe_<equipe.id>_<password>/<certificat|licence|autorisation>_<numero>.<ext>`. L'uid de la course n'y figure pas. Les deux ids sont des entiers séquentiels, le nom de fichier est prévisible, il reste comme seul secret le `Equipe.password`.
3. **`Equipe.password`** = 6 caractères hexadécimaux, `random.randrange(0x100000, 0xffffff)` (`views.py:87`), soit ~15,7 M de valeurs (~24 bits), générateur non cryptographique. Aucun rate limiting : à 1 000 req/s, environ 4 à 5 h pour retrouver une URL d'équipe ciblée.
4. **Ce même `password` est le code du lien d'édition** (`inscriptions_edit`), envoyé par mail et présent dans les URL, l'historique et le cookie. Quiconque a ce lien peut reconstruire les URLs de tous les fichiers de l'équipe.
5. **Autres consommateurs du chemin brut** :
   - `templates/admin/document_review.html` : `<iframe src="{{ equipier.piece_jointe.url }}">` et `autorisation.url`.
   - `static/custom_admin/equipe.js:8` : construit `'/uploads/' + texte` à la main pour le champ en lecture seule de l'admin équipe.
   - `admin_course.py` (`download`, ~l.1117) : lit `Path(settings.MEDIA_ROOT) / piece_jointe.name` pour l'export ZIP.
   - `management/commands/setup_e2e_data.py:96` : `piece_jointe.save(...)`.
6. Les logos de course et `fond_dossard` sont publics par nature et **restent** dans `MEDIA_ROOT` / `/uploads/`.

## 2. Objectif et règles d'accès

Un fichier n'est lisible que par :

- un **superuser** ;
- un utilisateur ayant une `Accreditation` sur la `Course` de l'édition de l'équipe (mêmes règles que `CourseAdminSite`) ;
- la **personne qui détient le code de l'équipe** (même contrôle que la vue d'édition : `instance.password == code`, ou le cookie `equipe.cookie_key()` s'il existe). Cela permet à l'équipe de revoir ce qu'elle a envoyé.

Tout autre cas : **404** (pas 403, pour ne pas confirmer l'existence). Réponse avec `Cache-Control: private, no-store`, `Content-Disposition: inline` avec un nom neutre, `X-Content-Type-Options: nosniff`.

Hors périmètre : chiffrement au repos, antivirus à l'upload, durée de conservation / purge RGPD (à ouvrir séparément, voir §7).

## 3. Conception

### 3.1 Stockage privé

- Nouveau réglage `PRIVATE_MEDIA_ROOT` (défaut `inscriptions/private_uploads`, surchargeable par variable d'environnement dans `settings/docker.py`), **non servi** par uwsgi ni par `static()`.
- Nouvelle classe `PrivateFileSystemStorage(FileSystemStorage)` (`storage.py`) avec `location=PRIVATE_MEDIA_ROOT` et `base_url=None`. `.url` doit lever une erreur claire pour qu'aucun template ne fabrique par erreur un lien direct.
- `Equipier.piece_jointe` et `Equipier.autorisation` : `storage=PrivateFileSystemStorage()` (callable pour rester testable avec `override_settings`).
- Nouveau chemin, sans secret : `edition_<id>/equipier_<equipier.id>/<type>_<numero><ext>`. La sécurité vient du contrôle d'accès, plus du chemin. Le `password` disparaît du nom de fichier.
  - `upload_to` appelé avant l'insertion : pour un `Equipier` neuf, `instance.id` est `None`. Utiliser `equipe_<equipe.id>` (id déjà connu) à la place de `equipier.id`.
  - Conserver les anciens fichiers au remplacement ? Aujourd'hui un nouvel upload du même nom laisse Django ajouter un suffixe aléatoire ; garder ce comportement, ne rien supprimer silencieusement.

### 3.2 Vue de téléchargement

- Route (avant la route un-segment `/<course_uid>/` qui doit rester la dernière, cf. `urls.py`) :
  `<edition:course_uid>/fichier/<int:equipier_id>/<str:champ>/` avec `champ ∈ {piece_jointe, autorisation}` ; `?code=<password>` optionnel pour le lien équipe.
- `views.fichier_equipier(request, course_uid, equipier_id, champ, code=None)` :
  1. `get_edition(course_uid)` ; `Equipier` filtré sur `equipe__course=edition` (un id d'une autre édition donne 404).
  2. Contrôle d'accès du §2 via une fonction réutilisable `peut_voir_pieces(request, equipe, code)` (`utils.py`), testable isolément.
  3. `FileResponse(storage.open(...))` ; en-têtes du §2 ; 404 si le champ est vide ou si le fichier manque sur disque.
- Mise à l'échelle : `FileResponse` en streaming suffit (quelques milliers de petits PDF/JPEG). `X-Sendfile` / `X-Accel-Redirect` serait une optimisation ultérieure.
- `Equipier.piece_jointe_url()` / `autorisation_url()` (méthodes du modèle) fabriquent l'URL de la vue ; plus aucun code n'utilise `.url` du champ.

### 3.3 Adaptations des consommateurs

- `document_review.html` : remplacer `.url` par les URL de la vue.
- `equipe.js` : utiliser l'URL de la vue (la rendre disponible côté serveur, par exemple dans un `data-url` du widget en lecture seule) au lieu de `'/uploads/' + texte`. Le widget lecture seule de l'admin équipe doit être regardé pour savoir ce qu'il rend aujourd'hui.
- `admin_course.download` : `equipier.piece_jointe.path` / `storage.exists()` au lieu de `MEDIA_ROOT`.
- `setup_e2e_data` : inchangé en principe (`FieldFile.save` passe par le storage) ; vérifier.
- Formulaire public d'édition : le widget `ClearableFileInput` affiche normalement « Actuellement : <lien `.url`> ». Avec `base_url=None` cela lèverait une exception : prévoir un widget qui affiche le nom ou le lien de la vue, avec le code d'équipe. Aucune surcharge de ce widget n'existe aujourd'hui dans le code (`grep` de `FileInput` : seul `templatetags/bootstrap.py`), donc **à vérifier en rendant le formulaire d'édition**.

## 4. Migration des fichiers existants

Commande `./manage.py deplacer_pieces_jointes` (idempotente, `--dry-run` obligatoire avant la vraie exécution) :

1. Pour chaque `Equipier` avec `piece_jointe` ou `autorisation` non vide : calcule le nouveau chemin, copie le fichier de `MEDIA_ROOT` vers `PRIVATE_MEDIA_ROOT`, vérifie la taille, met à jour le champ en base.
2. Ne supprime **rien** de l'ancien emplacement pendant la commande. Les anciens fichiers sont supprimés dans une seconde étape (`--purger-anciens`), après contrôle par l'équipe (un `find` de comparaison de tailles suffit).
3. Rapport : nombre déplacé, déjà fait, fichier manquant sur disque (références orphelines en base, à lister, pas à corriger).
4. Déploiement :
   1. Déployer le code + créer le volume `PRIVATE_MEDIA_ROOT` (le bind-mount `./:/app` couvre le dev ; **en production, vérifier que ce dossier est sur un volume persistant et inclus dans les sauvegardes**, comme l'actuel `uploads`).
   2. `deplacer_pieces_jointes --dry-run`, puis exécution réelle.
   3. Vérifier à la main : un certificat dans l'admin, un côté équipe, le ZIP d'export.
   4. `--purger-anciens`, puis retirer toute exposition résiduelle : la `static-map /uploads` ne doit plus pointer sur des dossiers `course_*`.
5. Les anciennes URLs `/uploads/course_*/…` répondent 404 une fois purgées. Aucun mail envoyé par l'application ne contient de lien direct vers un fichier (vérifié dans `templates/mails/`), donc pas de lien à rediriger.

## 5. Lots

| Lot | Contenu | Livrable |
|---|---|---|
| 1 | `PrivateFileSystemStorage`, réglage, `upload_to`, migration Django du champ (storage seul, pas de changement de colonne) | tests unitaires du chemin |
| 2 | Vue `fichier_equipier` + `peut_voir_pieces` + route | tests d'accès (§6) |
| 3 | Adaptation admin (`document_review.html`, `equipe.js`, `download`) et formulaire public | e2e de relecture de document |
| 4 | Commande `deplacer_pieces_jointes` + doc de déploiement | test de la commande sur une base de test |
| 5 | Déploiement prod, purge, retrait de l'exposition `/uploads` pour ces dossiers | checklist de §4 |
| 6 (optionnel) | `password` d'équipe généré avec `secrets` | voir §7 |

## 6. Tests

Dans `inscriptions/tests/` (module `test_pieces_jointes.py`, héritant de `BaseTestCase` qui redirige déjà `MEDIA_ROOT` ; y ajouter `PRIVATE_MEDIA_ROOT`) :

- anonyme sans code → 404 ;
- anonyme avec mauvais code → 404 ; avec bon code → 200 + contenu exact ;
- organisateur accrédité sur la course → 200 ; accrédité sur **une autre** course → 404 ; utilisateur connecté sans accréditation → 404 ; superuser → 200 ;
- `equipier_id` d'une autre édition que celle de l'URL → 404 ;
- `champ` invalide, champ vide, fichier absent du disque → 404 ;
- en-têtes `Cache-Control`, `nosniff` ;
- `GET /uploads/<ancien chemin>` → 404 (non servi) ;
- `upload_to` : un nouvel équipier sans `id` obtient un chemin valide ; le `password` n'apparaît pas dans le chemin ;
- commande de migration : idempotente, `--dry-run` ne modifie rien, orphelins listés ;
- e2e (Playwright) : l'écran de relecture `document_review.html` affiche l'iframe avec un fichier réellement lisible.

## 7. Questions ouvertes / suites

- **Conservation RGPD** : les certificats médicaux sont conservés indéfiniment. Définir une durée (par exemple purge N mois après l'édition) et une commande de purge. Hors périmètre de cette spec, à décider avec le responsable des données.
- **`Equipe.password`** : tant qu'il sert de secret d'accès, le générer avec `secrets` (lot 6). Impact limité : seules les nouvelles équipes sont concernées, les liens existants restent valides. Allonger le code changerait le format des URL d'édition, à ne faire que si on le décide explicitement.
- **Constat annexe** : `docker-compose.yml` contient en clair un `EMAIL_HOST_PASSWORD` (service `bounce`) versionné dans git. À sortir dans `docker-compose.override.yml` ou une variable d'environnement, et **à renouveler**.
- Journalisation des accès aux pièces (qui a ouvert quel certificat) : utile pour le RGPD, non prévue ici.
