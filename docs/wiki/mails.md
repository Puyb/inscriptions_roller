---
title: Mails
modified: 2019-03-06
---

Mails


Pour faciliter la gestion des inscriptions, enduroller est aussi un serveur d’envois de mails ( attention, aucune réception n’y est possible ). L’adresse dite de réponse ( l’adresse de destination des mails que vous enverront en retour les participants ) est votre adresse renseignée dans les paramètres de votre course. 
Certains mails envoyés par enduroller sont automatiques ( et modifiables par vos soins ) mais vous pouvez aussi générer vos propres mails ( envoi d’infos complémentaires aux participants, demandes particulières, etc ... ). 

Informations importantes :
- l’adresse mail figurant dans les règlages de la course recevra tous les mails liés à enduroller ; que ce soit les mails envoyés par les participants en réponse à ceux envoyés au départ par enduroller ou que ce soit les mails envoyés par enduroller à l’organisateur.


Mails par défaut :

- mails inscriptions : mails générés à la fin de la procédure d’inscription envoyés d’une part au gérant d’équipe et d’autre part à l’organisateur. Il contient aussi les pièces manquantes.
- mail de paiement : mails générés après un paiement d’une inscription au gérant d’équipe et à l’organisateur. Si le paiement de l’équipe est complet, il comprendra un lien vers une facture.
- mail changement d’équipe : mails envoyés si l’équipe subit un changement de catégorie au gérant d’équipe et à l’organisateur.
- mail changement inscription : mail sur le même format que le mail inscription reprenant également les liens de modification et de paiement.

Important à savoir : une modification du corps du message d’un mail impactera seulement le mail actuellement en cours de modification/en cours d’envoi. Si la modification voulue concerne plusieurs mails, il faudra modifier le template dans le menu «modèles de mails».



La suite de l’article va se découper comme suit :
Création d’un modèle de mail ou template mail
Envoi d’un message type à plusieurs personnes
Modification d’un mail avant envoi à une seule personne

Création et modification d’un modèle mail ou «template mail»
Sur la page de gestion de votre course, tous les modèles de mails sont accessibles via le menu «modèles de mail».
Les mails présents sont ceux générés automatiquement lors des procédures d’inscriptions, de modification d’équipe et de paiements. Ils sont consultables ici.  https://github.com/Puyb/inscriptions_roller/tree/master/inscriptions/templates/mails

Dans créer un nouveau mail, vous avez :
Le nom : nom par lequel sera identifié le modèle
Destinataire : le destinataire «générique» auquel sera envoyé le mail lors d’un envoi multiple ou via le menu d’envoi de la fiche de chaque équipe. Vous avez le choix entre l’organisateur, le gérant d’équipe, chaque équipier de ladite équipe ou tout le monde.
Le sujet : le sujet du mail est l’objet du mail
Message : le corps du message est à compléter selon vos besoins sachant que certaines formules et insertions sont possibles pour personnaliser les mails comme suit :

La formule suivante sera automatiquement remplacé par le renseignement équivalant concernant l’équipe concerné :

{{ instance.course.nom }} : nom de la course

{{ instance.gerant_prenom }} : prénom gérant équipe

{{ instance.gerant_nom }} : nom gérant équipe

{{ instance.nom }} : nom de l’équipe

{{ instance.categorie }} : catégorie de l’équipe

{{ instance.numero }} : numéro de l’équipe

{{ instance.nom }} : nom de l’équipe

{{ instance.club }} : nom du club

{{ instance.prix }} : prix à payer pour l’équipe

{{ instance.nom }} : nom de l’équipier

{{ instance.prenom }} : prénom de l’équipier

{{ instance.num_licence }} : numémro de licence

D’autres sont disponible, vous pouvez les trouvez sur les autres modèles existants ou contacter un administrateur d’enduroller.

Pour envoyer un mail à plusieures équipes :
Cette procédure ne peut se faire qu’à l’aide d’un template existant.
* aller dans «équipes inscrites» ou le listing des équipes concernées 
* sélectionner les équipes concernées
* dans «actions» : sélectionner «envoyer un mail groupé» puis sélectionner le template voulu et cliquer sur valider
Personnaliser un mail avant de l’envoyer

Pour personnaliser un mail avant de l’envoyer à une seule personne, vous pouvez utiliser la même procédure que pour un envoi multiple en modifiant le texte avant envoi ou passer par la fiche d’équipe.
Dans la fiche d’équipe, dans la partie gérant, vous trouverez un menu avec l’historique des mails envoyés à ladite équipe et chacun des templates disponibles.
En cliquant sur le template désiré, vous pouvez modifié le mail avant envoi.


Historique des mails envoyés par enduroller

Dans le menu de la partie gérant de la fiche d’équipe, vous trouverez les mails envoyés pour l’équipe concernée.
