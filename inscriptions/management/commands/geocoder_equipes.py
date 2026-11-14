"""Renseigne `Equipe.gerant_ville2` pour les equipes sans ville (rattrapage).

    ./manage.py geocoder_equipes --toutes --dry-run
    ./manage.py geocoder_equipes --course 6hdeparis2026 --course 3htroyes2026
    ./manage.py geocoder_equipes --toutes --force      # recalcule aussi les equipes deja localisees

Utilise `lookup_ville()` (referentiel local `CodePostal`, voir
`import_codes_postaux`). N'appelle pas `Equipe.save()` (pas de numerotation ni de mail).
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from django.db.models import Q

from inscriptions.models import Course, Equipe, lookup_ville


class Command(BaseCommand):
    help = "Geocode (hors-ligne) les equipes sans ville."

    def add_arguments(self, parser):
        parser.add_argument('--course', action='append', default=[], help='uid de course (repetable)')
        parser.add_argument('--toutes', action='store_true', help='toutes les courses')
        parser.add_argument('--force', action='store_true', help='recalcule aussi les equipes deja localisees')
        parser.add_argument('--dry-run', action='store_true', help="n'ecrit rien")

    def handle(self, *args, **options):
        if not options['course'] and not options['toutes']:
            raise CommandError('Preciser --course <uid> ou --toutes.')
        equipes = Equipe.objects.select_related('course').order_by('course_id', 'numero')
        if options['course']:
            equipes = equipes.filter(course__uid__in=options['course'])
        if not options['force']:
            equipes = equipes.filter(gerant_ville2__isnull=True)

        courses = Course.objects.all()
        if options['course']:
            courses = courses.filter(Q(uid__in=options['course']) | Q(editions__uid__in=options['course'])).distinct()
        if not options['force']:
            courses = courses.filter(ville2__isnull=True)

        cache = {}
        a_ecrire, non_resolues, total = [], [], 0
        courses_ecrire = []
        with transaction.atomic():
            for course in courses:
                ville = lookup_ville(course.ville, '', 'FR')
                if ville and course.ville2_id != ville.id:
                    course.ville2 = ville
                    courses_ecrire.append(course)
            for equipe in equipes:
                total += 1
                cle = (equipe.gerant_ville, equipe.gerant_code_postal, equipe.gerant_pays)
                if cle not in cache:
                    cache[cle] = lookup_ville(*cle)
                ville = cache[cle]
                if ville is None:
                    non_resolues.append(equipe)
                elif equipe.gerant_ville2_id != ville.id:
                    equipe.gerant_ville2 = ville
                    a_ecrire.append(equipe)
            if not options['dry_run']:
                Equipe.objects.bulk_update(a_ecrire, ['gerant_ville2'], batch_size=500)
                Course.objects.bulk_update(courses_ecrire, ['ville2'])
            else:
                transaction.set_rollback(True)  # annule aussi les Ville creees

        self.stdout.write('%s%d equipes traitees, %d localisees, %d non resolues.' % (
            '[dry-run] ' if options['dry_run'] else '', total, total - len(non_resolues), len(non_resolues)))
        self.stdout.write('%d courses localisees.' % len(courses_ecrire))
        for e in non_resolues:
            self.stdout.write('  non resolue : %s #%s %s | %s | %s | %s' % (
                e.course.key, e.numero, e.nom, e.gerant_ville, e.gerant_code_postal, e.gerant_pays))
