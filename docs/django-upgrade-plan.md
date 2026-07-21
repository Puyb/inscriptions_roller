# Plan de migration Django 2.0 → 5.2 LTS

Document de travail, aucune ligne de code applicatif n'a été modifiée pour produire cette analyse.

## 1. Résumé des trouvailles

- **Version actuelle** : Django 2.0 (sorti fin 2017, EOL depuis avril 2019). Cible réaliste : **Django 5.2 LTS** (support jusqu'en 2028).
- **Python** : `Dockerfile` pin `python:3.7`. Django 5.x exige Python ≥ 3.10 → montée obligatoire en parallèle de Django.
- **`admin_course.py` n'est pas le facteur limitant.** Les points d'extension utilisés (`AdminSite` sous-classé, `ModelAdmin.get_queryset`/`get_urls`, `SimpleListFilter`, `Media`, `admin_view()`, `each_context()`) sont des API stables, toujours supportées en Django 5.x. Le travail y est mécanique : `url()` → `re_path()`, `ugettext_lazy` → `gettext_lazy`.
- **Dette de code mécanique** (faible risque, volume élevé) :
  - `django.conf.urls.url` (≈15 occurrences dans `admin_course.py`, `admin_main.py`, `urls.py`) — supprimé en Django 4.0.
  - `ugettext`/`ugettext_lazy` (quasi tous les fichiers) — supprimé en Django 4.0.
  - `models.NullBooleanField` (`dossier_complet`, `autorisation_valide`, `piece_jointe_valide`) — supprimé en Django 4.0, nécessite migration.
  - `django.contrib.postgres.fields.JSONField` (`Equipe.extra`, `Equipier.extra`) — supprimé en Django 4.0, nécessite migration vers `django.db.models.JSONField`.
  - `render_to_response` importé (non utilisé) dans `admin_views.py` — supprimé en Django 3.0.
  - `default_app_config` dans `inscriptions/__init__.py` — no-op depuis 3.2, supprimé en 4.x.
  - `USE_L10N` dans `settings/default.py` — n'a plus d'effet, setting retiré en Django 5.0.
  - `allow_tags` (7 occurrences) — déjà mort depuis Django 2.0 lui-même (no-op silencieux, le rendu sûr passe déjà par `mark_safe()`), à nettoyer par hygiène seulement.
  - DB functions custom (`Unaccent`, `RegexpReplace`, `CompareNames`, `DayOfWeek`, `Hour` dans `models.py`/`functions.py`) : API `Func`/`as_sql` stable, à retester à chaque palier plutôt qu'à réécrire.
- **Le vrai risque, ce sont les dépendances tierces quasi abandonnées** :
  - `django-user-accounts` (`account==2.0.3`) — colonne vertébrale de l'auth (`SignupView`/`LogoutView`), maintenance **inactive**, dernière release oct. 2023, support Django 4/5 non garanti.
  - `pinax-theme-bootstrap==7.1.1` — thème visuel, projet Pinax abandonné dès 2018 pour cette approche.
  - `wiki==0.4.4` (django-wiki) — figé ~2015-2016 alors que la version actuelle (0.12.x) supporte Django 5.0 ; écart énorme (modèles/migrations/plugins ont changé).
  - `channels==2.1.7` / `channels-redis==2.3.3` / `daphne==2.2.5` / `asgiref==2.3.2` — la stack 4.x actuelle supporte Django 5.2, mais c'est un saut de 2 versions majeures, à faire monter en lockstep avec Django.
  - `django-mptt`, `django-nyt`, `django-sekizai`, `django-classy-tags`, `sorl-thumbnail` — tirés par `django-wiki`/`pinax`, à faire évoluer en bloc avec elles.
  - `django-form-admin` / `django-bootstrap-form` — apps installées, jamais importées en Python (utilisées via templates), à auditer.
  - `stripe==2.12.1` — SDK très ancien (actuel ~v10+), API conceptuellement stable côté Stripe mais signatures d'appel à revoir.
  - `zipstream==1.1.4` — peu actif, fork mieux maintenu `zipstream-ng` disponible, indépendant de Django.
- **Filet de sécurité existant** : suite de tests `inscriptions/tests/` (~940 lignes : pricing, paiements, webhooks, challenges, numérotation, dossiers) + e2e Playwright (`e2e/`). C'est ce qui rend une migration incrémentale réaliste plutôt que risquée.

---

## 2. Stratégie générale

Monter **LTS par LTS** plutôt que verrouiller sur les versions intermédiaires : `2.0 → 2.2 → 3.2 → 4.2 → 5.2`. Chaque palier LTS est un point de test stable ; les versions intermédiaires (2.1, 3.0, 3.1, 4.0, 4.1, 5.0, 5.1) ne sont traversées que pour lire leurs *release notes / deprecation warnings*, pas pour y rester.

Règle à chaque palier :
1. Bump Django vers la version cible.
2. `PYTHONWARNINGS=error::DeprecationWarning` (ou `-W error::DeprecationWarning`) en lançant la suite de tests, pour transformer les warnings en échecs et les corriger un par un **avant** de passer au palier suivant.
3. `./manage.py makemigrations --check --dry-run` pour détecter les migrations manquantes (champs de type modifié, etc.).
4. Suite de tests complète + e2e verts avant de continuer.
5. Vérification manuelle du back-office (voir checklist §5).

---

## 3. Étapes détaillées

### Étape 0 — Préparation (avant tout changement de version)
- Vérifier que `scripts/test.sh` et `scripts/test-e2e.sh` passent en l'état actuel (baseline verte, seule référence fiable de non-régression).
- Nettoyage à risque nul, à faire en premier pour réduire le bruit des étapes suivantes :
  - Supprimer l'import mort `render_to_response` dans `admin_views.py`.
  - Supprimer `default_app_config` (l'auto-détection d'`AppConfig` fonctionne sans).
  - Nettoyer les `allow_tags` (déjà no-op).
- Spike de compatibilité (branche jetable, en parallèle du reste) : installer `django-user-accounts` et `pinax-theme-bootstrap` dans un venv avec Django 3.2 puis 4.2, voir où ça casse concrètement. C'est la découverte qui conditionne le plus le budget temps global — à faire tôt, pas à la fin.
- Geler/versionner un tag ou une branche de référence pour pouvoir revenir en arrière à tout moment.

### Étape 1 — Django 2.0 → 2.2 LTS
- Python : rester sur 3.7 (Django 2.2 supporte Python 3.5–3.7), pas de bump nécessaire ici.
- Peu de ruptures à ce saut : c'est surtout l'occasion de lire les *release notes* 2.1/2.2 et de laisser les deprecation warnings s'afficher.
- Paquets à bumper en même temps (versions compatibles Django 2.2) : `psycopg2`/`psycopg2-binary` si nécessaire, `django-countries`, `django-resized`, `django-turnstile` — vérifier compat mineure.
- **Tests** : suite complète + e2e. Pas de checklist manuelle étendue nécessaire (peu de surface de rupture).

### Étape 2 — Django 2.2 → 3.2 LTS
- Python : viser 3.8 ou 3.9 (Django 3.2 supporte 3.6–3.9).
- Corriger dès maintenant (deviennent des warnings bruyants à partir d'ici, mieux vaut ne pas attendre 4.2) :
  - `ugettext`/`ugettext_lazy` → `gettext`/`gettext_lazy` (partout).
  - Vérifier `django.contrib.postgres.fields.JSONField` : encore utilisable mais déprécié depuis 3.1, laisser passer un warning pour l'instant, migration réelle prévue à l'étape 3.
- **Channels** : bump `channels` 2.1.7 → 3.x, `channels-redis`, `daphne`, `asgiref` en conséquence. Revalidation de `routing.py`/`consumers.py` (le `SyncConsumer` change peu, mais tester l'envoi de mail via `runworker mail`).
- **Point de décision critique** : confirmer ici si `django-user-accounts` et `pinax-theme-bootstrap` tournent sous Django 3.2 (résultat du spike de l'étape 0). Si ça casse déjà, la suite du plan doit intégrer leur remplacement avant de continuer vers 4.2.
- **Tests** : suite complète + e2e + smoke test manuel de l'auth (signup/login/logout/confirmation email) car c'est la zone la plus exposée par `django-user-accounts`.

### Étape 3 — Django 3.2 → 4.2 LTS (le palier le plus lourd)
C'est ici que tombent la plupart des suppressions d'API :
- `django.conf.urls.url` → remplacer partout par `re_path()`/`path()` (`admin_course.py`, `admin_main.py`, `urls.py`). C'est mécanique mais volumineux — faire un passage dédié, fichier par fichier, avec relance des tests après chaque fichier plutôt qu'en un seul gros commit.
- `models.NullBooleanField` → `BooleanField(null=True)` + `makemigrations` pour les 3 champs concernés (`Equipe.dossier_complet`, `Equipier.autorisation_valide`, `Equipier.piece_jointe_valide`).
- `django.contrib.postgres.fields.JSONField` → `django.db.models.JSONField` + migration pour `Equipe.extra`/`Equipier.extra`. Vérifier que les migrations existantes (`0029_auto_20171222_0212.py` et suivantes) restent cohérentes ou ajouter une migration de conversion de type.
- `ugettext`/`ugettext_lazy` : si pas déjà fait à l'étape 2, c'est le point de non-retour, la suppression est effective.
- Python : viser 3.10 ou 3.11.
- **Dépendances tierces à trancher ici, pas après** :
  - `django-user-accounts` : si le spike montre une incompatibilité, migrer vers `django-allauth` (ou vues d'auth Django natives) — impact sur `views.SignupView`, `forms.SignupForm`, `admin_course.py` (import `LogoutView`), et les templates d'auth. C'est le chantier le plus incertain en taille : à isoler dans son propre lot de commits/PR.
  - `pinax-theme-bootstrap` : remplacer par des templates Bootstrap 5 maison (le thème n'apporte plus de valeur, autant s'en débarrasser plutôt que le maintenir sous respirateur artificiel).
  - `wiki==0.4.4` : décision produit à prendre — soit upgrade vers la branche actuelle de django-wiki (réintégration quasi complète des modèles/migrations/plugins), soit abandon de la fonctionnalité wiki intégrée. À trancher avec le métier avant d'investir du temps dessus.
  - `channels` → 4.x, aligné avec Django 4.2.
- **Tests** : suite complète + e2e après *chaque* sous-lot (url→re_path, puis NullBooleanField, puis JSONField, puis auth, puis wiki/thème) plutôt qu'à la fin du palier. Ajouter une passe manuelle complète (voir checklist §5) car c'est le palier qui touche le plus de surface fonctionnelle.

### Étape 4 — Django 4.2 → 5.2 LTS
- Python : 3.10–3.13.
- Peu de suppressions nouvelles pour ce projet : surtout retirer `USE_L10N` des settings (déjà sans effet).
- Revalider les DB functions custom (`Unaccent`, `RegexpReplace`, `CompareNames`, `DayOfWeek`, `Hour`) — API stable mais à retester formellement (elles touchent le calcul des doublons et des challenges, zone sensible et peu couverte visuellement par les tests unitaires).
- Dernier bump `channels`/`stripe`/`sorl-thumbnail`/`django-mptt`/`django-nyt` vers leurs dernières versions compatibles Django 5.2.
- **Tests** : suite complète + e2e + checklist manuelle complète (§5) + un passage de charge léger sur les pages de classement/challenges (requêtes lourdes avec `annotate`/`Subquery`).

### Étape 5 — Nettoyage final
- Retirer les dépendances devenues inutiles (`django-jsonfield` semble déjà orpheline dans le code, à confirmer et supprimer du `requirements.txt`).
- Auditer `formadmin`/`django-bootstrap-form` : gardés seulement si un template les utilise réellement, sinon retirer.
- `zipstream` → `zipstream-ng` si le premier montre des signes de rupture avec la version Python cible.
- Mettre à jour `Dockerfile`/`docker-compose.yml` sur les versions finales (Python, Postgres si pertinent).
- Documenter dans `CLAUDE.md` la version Django finale.

---

## 4. Priorisation des paquets

| Priorité | Paquet | Action | Raison |
|---|---|---|---|
| 1 (urgent, à investiguer avant de s'engager) | `django-user-accounts` (`account`) | Spike de compat, puis migrer vers `django-allauth` si nécessaire | Maintenance inactive, cœur de l'auth, conditionne le budget temps du projet |
| 1 | `pinax-theme-bootstrap` | Remplacer par templates Bootstrap 5 maison | Abandonné depuis 2018, aucune garantie de compat future |
| 2 | `wiki` (django-wiki) | Décision produit : upgrade complet ou suppression de la fonctionnalité | Écart de ~8 ans de version, upgrade = quasi-réécriture |
| 2 | `channels` / `channels-redis` / `daphne` / `asgiref` | Bump en lockstep avec chaque palier Django | Nécessaire pour l'envoi de mail async, mais API stable donc risque modéré |
| 3 | `django-mptt`, `django-nyt`, `django-sekizai`, `django-classy-tags`, `sorl-thumbnail` | Bump groupé avec django-wiki | Dépendances transitives, pas de décision indépendante |
| 3 | `stripe` | Bump SDK, retester `stripe_webhook`/`intent_paiement` | Ancien mais API Stripe stable conceptuellement, bonne couverture de tests existante (`test_payment_webhooks.py`) |
| 4 | `zipstream`, `django-jsonfield`, `django-form-admin`, `django-bootstrap-form` | Auditer usage réel, supprimer ou remplacer | Faible risque, faible urgence, à traiter en fin de projet |

---

## 5. Checklist de tests à chaque étape

**Automatisé, à chaque palier (non négociable avant de passer au suivant) :**
- `scripts/test.sh` (suite complète unitaire/fonctionnelle/intégration).
- `scripts/test-e2e.sh` (au moins à la fin de chaque palier LTS, pas nécessairement à chaque sous-commit).
- `./manage.py makemigrations --check --dry-run` (détecter les migrations manquantes après changement de type de champ).
- `./manage.py check --deploy`.
- Lancer les tests avec les deprecation warnings promus en erreurs (`PYTHONWARNINGS=error::DeprecationWarning`) **avant** de bumper vers le palier suivant, pour ne pas découvrir les ruptures après coup.

**Smoke test manuel (zones non couvertes ou mal couvertes par les tests automatisés), à faire au minimum à la fin des étapes 2, 3 et 4 :**
- Inscription complète : formulaire équipe + équipiers + questions extra (`ExtraQuestion`).
- Paiement : IPN Paypal, intent + webhook Stripe, webhook HelloAsso.
- Back-office (`/course/`) : login, choix de course (cookie `course_uid`), validation de dossiers (`document_review`), envoi de mail groupé, export CSV, listing dossards, listing anomalies/anniversaires, import de résultats CSV, stats.
- Envoi de mail asynchrone (`runworker mail`) + pixel de tracking (`middleware.tracking_middleware`).
- Challenges : calcul de classement (`compute_challenge`), fusion/déplacement de participations entre courses.
- Wiki (si conservé après la décision de l'étape 3).
- Rendu visuel des templates admin custom (`admin/dashboard.html`, `admin/course_choose.html`, `admin/equipe/*.html`, etc.) — l'UI Django admin change d'apparence entre 2.x, 3.x/4.x et 5.x.
- `npm run build` (webpack) — pas lié à Django mais à vérifier que la collecte de statiques fonctionne toujours après chaque palier.
