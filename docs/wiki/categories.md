---
title: Categories
modified: 2019-12-21
---

Les catégories reflètent les catégories du règlement. Il est possible d'y définir le prix et la plage de numérotation des dossards. Il est aussi possible de définir des règles pour accepter une équipe dans une catégorie. Pour participer, une équipe doit forcément correspondre à une catégorie, donc il est important que les règles soient correctement définies.

Il est possible de limiter le nombre d'inscriptions dans une ou plusieurs catégories en limitant le nombre de dossards. Par exemple, si vous voulez limiter les solos hommes et femmes à 12 participants, il suffit que le différence entre le numéro de début de fin des dossards soit de 12. 


Règles simples :
----------------
- nombre minimum et maximum d'équipiers
- âge minimum
- sexe
    - Homme (femme): uniquement des hommes (femmes)
    - Mixte : au moins un homme et une femme
    - Homme ou mixte (femme ou mixte) : équipe composé uniquement d'homme, ou d'hommes et de femmes, mais pas uniquement de femmes (et l'inverse pour femme ou mixte)
    - Sans critère : toutes les compositions sont possibles

Règles complexes :
------------------ 
Il est possible de compléter les règles ci dessus avec une fonction javascript de validation. Cette fonction prend un objet "data" décrivant l'équipe et les équipiers et doit retourner vrai ou faux.

L'objet data contient les clefs suivantes :

- nombre - nombre d'équipiers
- nombre_h - nombre d'hommes
- nombre_f - nombre de femmes
- age_moyen - moyenne d'âges le jour de la course
- equipiers - tableau contenant un objet décrivant chaque équipier avec les clefs suivantes :
    - sexe - H ou F
    - age - âge le jour de la course
    - date_de_naissance_year, date_de_naissance_month, date_de_naissance_day
    - justificatif - 'certificat' ou 'licence'


Exemple de règles :
------------------- 

Age moyen entre 18 et 36

    data => data.age_moyen >= 18 && data.age_moyen < 36

Au moins un adulte

    data => data.some(equipier => equipier.age >= 18)

Au moins un adulte avec le raccourci age()

    data => data.some(age(18))

Au moins un adulte et au moins un de moins de 35

    data => data.equipiers.filter(age(18)).length > 0 && data.equipiers.filter(age(35)).length < data.nombre

Au moins 50% de femmes :

    data => data.nombre_f >= data.nombre_h

Aucun adulte, un age moyen d'au moins 14 ans et au moins 5 équipier si l'age moyen est de moins de 16 ans

    data =>  !data.equipiers.some(age(19)) && (data.age_moyen > 15 || (data.equipiers.length > 4 && data.age_moyen >= 14)

Note : les fonctions peuvent aussi s'écrire de cette façon :

    function (data) { return data.age_moyen < 19; }

Une fois les règles écrites, vous pouvez les tester dans la rubrique test des catégories



Dossards
--------
Ces limites peuvent être mises pour plusieurs catégories sur une même course.

Par exemple, sur une même course, nous mettons des solos homme avec numéros de dossards de 1 à 60 et des  solos femme de 1 à 60 : les inscriptions solos se feront au nombre de 60 au total hommes et femmes confondues pour la course ( donc 60 personnes sur deux catégories différentes ) et la 61ème personne qui souhaitera s’inscrire ne pourra le faire quelque soit son sexe.

Sur le dossard imprimé, le chiffre des unités correspondra au énième équipier de l’équipe dans l’ordre d’inscription ( le dossard 824 correspondra donc au quatrième équipier de l’équipe 82 )
Donc pour reprendre l’exemple des solos de 1 à 60, les dossards seront en fait dans l’ordre 11,21,31,41,51,61,71,81,91,101,111,121,131, etc jusqu’au 601

Les dossards peuvent ainsi servir à différencier les catégories ayant certaines particularités comme les mineurs ou les handi; quadeurs; long boards; etc

Sur les 6 Heures de Paris les précédentes années par exemple, les catégories avaient leurs limites de dossards comme ceci :
- 1 à 200 pour les équipes séniors hommes/mixte et séniors femmes
- 201 à 300 pour les vétérans
- 301 à 400 pour les solos ( la limite haute changeant chaque année)
- 401 à 500 pour les duos hommes/mixtes et femmes
- 501 à 600 pour les équipes Quads
- 600 à 700 pour les Juniors
- 800 à 900 pour les Handi


Ce qui permettait de savoir que le numéro 4062 était le deuxième membre du duo 406 par exemple ou le 5843 le troisième membre de l’équipe Quads 584.
