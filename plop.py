s= """354;PAYSAN;J.LUC;315859;28/11/1949;IDH
355;BEDIAS;ELHADI;36918;;IDH
356;GUERIN;SAMUEL;;;IDH
357;REGUER-PETIT;LEA;;;IDF
358;EVRARD;JULIEN;;;IDH
359;ESNAULT;VINCENT;;;IDH
360;BARA;ADRIAN;;;IDH
361;LEROUX;RAYNALD;236099;31/01/1981;IDH
362;LAVACRY;SEBASTIEN;;;IDH
363;GALVAN;ARISTIDE;;;IDH
417;PIRODON/LABONNE;;;;DUX"""

from inscriptions.models import *
from datetime import date
from django.db import transaction

with transaction.atomic():

    course = Course.objects.get(uid='2hsa16')
    for l in s.split('\n'):
        l = l.split(';')

        e = Equipe(
            course=course,
            numero=int(l[0]),
            nom=l[1],
            gerant_nom=l[1],
            gerant_prenom=l[2],
            gerant_ville='Sainte-Adresse',
            gerant_code_postal='76310',
            gerant_email=course.email_contact,
            gerant_telephone='0123456789',
            categorie=Categorie.objects.get(course=course, code=l[5]),
            nombre=1 if l[5] != 'DUX' else 2,
            connu='Autre',
            prix=0,
            paiement=0,
            dossier_complet=True,
        )
        e.save()

        for i in range(e.nombre):
            e.equipier_set.create(
                numero=i+1,
                nom=l[1],
                prenom=l[2],
                ville='Sainte-Adresse',
                code_postal='76310',
                email=course.email_contact,
                sexe='H' if l[5] != 'IDF' else 'F',
                date_de_naissance=date(1900, 1, 1),
                justificatif='certificat',
                piece_jointe_valide=True,
            )






            




