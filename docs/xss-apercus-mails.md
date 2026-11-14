# Spec : sécuriser l'affichage des aperçus de mails (XSS)

Statut : à faire (rien n'est implémenté).

## Contexte

L'admin course affiche du HTML de mail à deux endroits :

| Page | Fichier | Données affichées |
|---|---|---|
| Aperçu du mail groupé (`/course/inscriptions/equipe/` → action « Envoyer un mail groupé ») | `inscriptions/templates/admin/equipe/send_mails.html` | `data.subject`, `data.mail`, `data.message` insérés avec `$('#preview').html(...)` |
| Détail d'un mail envoyé (`/course/inscriptions/mail/<id>/change/`) | `inscriptions/static/custom_admin/mail.js` | message complet : `.html($('.field-message .readonly').text())` |

Afficher le HTML du message est **voulu** (c'est du HTML de mail). Ce HTML ne doit
cependant contenir ni JS, ni formulaire, ni ressource externe active.

La vue d'aperçu est `EquipeAdmin.preview_mail` (`inscriptions/admin_course.py`).

## Problèmes

### 1. XSS depuis les inscrits (prioritaire)

`data.mail` est `instance.gerant_email`, saisi par les inscrits. Le validateur d'email de
Django accepte une partie locale entre guillemets contenant `<` et `>` :

```
"<img src=x onerror=alert(1)>"@example.com
```

Insérée en `.html()` dans le `<h2>` de l'aperçu, elle s'exécute chez l'organisateur qui
prévisualise. Si l'organisateur est superuser : élévation de privilèges.

`data.subject` passe par le moteur de template Django (variables échappées), donc il
arrive déjà échappé ; l'insérer en `.html()` est correct **seulement** parce qu'il est
déjà du HTML échappé. À traiter comme du texte pour ne pas dépendre de ça.

### 2. HTML du message écrit par l'organisateur

Les variables du template (`{{ instance.nom }}`…) sont échappées par `Template(...).render`,
donc les saisies des inscrits ne sont pas un risque dans le message. Reste le HTML écrit
par l'organisateur dans le `TemplateMail` (confiance partielle : un organisateur non
superuser peut viser un superuser) et le `Mail.message` stocké.

### 3. Pixel de suivi (à vérifier)

`middleware.tracking_middleware` marque un `Mail` comme lu quand le pixel (paramètre
`message_id`) est chargé. Si `MailConsumer` stocke le pixel dans `Mail.message` (à vérifier
dans `inscriptions/consumers.py`), afficher le détail d'un mail dans l'admin le marquerait
comme lu. Sans chargement d'images distantes dans l'aperçu, le problème disparaît.

## Solution

### A. Texte brut pour les champs hors message

Dans `send_mails.html`, utiliser `.text()` pour `data.subject` et `data.mail` ; seul
`data.message` est affiché comme HTML (voir B).

### B. Message dans une iframe sandbox

Remplacer l'insertion en `.html()` par une iframe sandbox :

```html
<iframe id="preview-frame" sandbox style="width: 100%; height: 600px; border: 1px solid #ccc"></iframe>
```

```js
frame.srcdoc =
  '<meta http-equiv="Content-Security-Policy" ' +
  'content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:">' +
  '<base target="_blank">' +
  data.message;
```

- `sandbox` sans valeur : pas de scripts, pas de soumission de formulaires, pas de
  navigation du parent, origine opaque (pas d'accès aux cookies ni au DOM de l'admin).
  **Ne jamais** combiner `allow-scripts` et `allow-same-origin`.
- La CSP dans le `srcdoc` bloque en plus les `<form action>`, `<link>`, les images et
  polices distantes (donc le pixel de suivi, voir problème 3).
- `<base target="_blank">` : les liens s'ouvrent dans un nouvel onglet (sans `allow-popups`
  ils ne feraient rien ; ajouter `allow-popups` si on veut les ouvrir).
- Hauteur : pas d'auto-ajustement possible sans `allow-same-origin` → hauteur fixe avec
  défilement.
- Si on veut voir les images distantes dans l'aperçu : ajouter `https:` à `img-src`, mais
  uniquement après avoir vérifié le point 3.

Appliquer la même approche à `mail.js` : à la place de
`$('fieldset').after($('<div>').html(...))`, créer une iframe sandbox avec `srcdoc` (même CSP)
à partir du texte du champ readonly, et conserver la suppression de `.field-message`.

### C. Robustesse côté serveur de l'aperçu

`preview_mail` fait `request.GET['id']` : un `id` vide donne une 500. Renvoyer une 400 si
`id` ou `template` sont absents ou non numériques.

### D. Nettoyage du HTML à l'enregistrement (optionnel, défense en profondeur)

Ne remplace pas l'iframe. À faire si on veut aussi protéger les destinataires et le HTML
stocké.

- Python : `nh3` (binding de ammonia, maintenu) ; `bleach` est déprécié. Le conteneur est en
  Python 3.7 avec un Django ancien : vérifier la disponibilité des wheels avant de choisir.
- Navigateur : DOMPurify (la chaîne webpack existe déjà).
- Liste blanche de balises de mail (`table`, `tr`, `td`, `img`, `a`, `style`, `p`, `b`…).
  Exclure `script`, `form`, `iframe`, `object`, `embed`, et les attributs `on*`. Filtrer les
  schémas d'URL (`javascript:`).
- Où : `TemplateMail.save()` (ou clean du formulaire) et dans `TemplateMailAdmin`.
  L'éditeur TinyMCE de `send_mail.html` reste tel quel (édition, pas affichage).

## Tests e2e à ajouter (Playwright, `e2e/`)

Seed (dans `setup_e2e_data`) :
- une équipe dont `gerant_email` vaut `"<img src=x onerror=window.__xss=1>"@example.com` ;
- un `TemplateMail` dont le message contient `<script>window.__xss=1</script>`,
  `<form action="/x"><input name="a"><button>ok</button></form>` et une
  `<img src="https://exemple.invalid/pixel.gif">` ;
- un `Mail` avec ce même message (pour `mail.js`).

Cas à vérifier :
1. Aperçu mail groupé avec l'équipe piégée : `window.__xss` reste `undefined`, le `<h2>`
   affiche l'email comme texte (le texte `<img` apparaît littéralement).
2. Le message est rendu dans `iframe#preview-frame[sandbox]` ; l'attribut `sandbox` ne contient
   ni `allow-scripts` ni `allow-same-origin`.
3. Le script du message ne s'exécute pas (`window.__xss` indéfini dans la page et dans
   l'iframe) ; le formulaire ne peut pas être soumis (aucune requête vers `/x`, via
   `page.on('request')`).
4. Aucune requête vers `exemple.invalid` n'est émise (CSP `img-src`).
5. Détail d'un mail (`mail.js`) : même contrôle (iframe sandbox, pas de script, pas de
   requête externe), et le champ `.field-message` est supprimé.
6. `preview_mail` sans `id` : réponse 400 (test via `page.request.get`).
7. Les tests existants à adapter : `test_admin_equipe_actions.py::test_mail_preview_…`
   (les sélecteurs `#preview div` deviennent `iframe#preview-frame` + `frame_locator`) et
   `test_admin_mail.py` (`#mail-body` est maintenant dans l'iframe).

## Critères d'acceptation

- Aucun HTML d'inscrit ou d'organisateur ne s'exécute dans l'admin course lors d'un aperçu.
- Le rendu des mails reste fidèle (tables, styles inline) dans l'aperçu.
- Aucune requête externe n'est émise à l'ouverture d'un aperçu (le suivi de lecture n'est
  pas déclenché).
- Les tests e2e ci-dessus passent.
