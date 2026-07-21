from datetime import date

from inscriptions.factories import CategorieFactory, CourseFactory, EquipeFactory, EquipierFactory
from inscriptions.models import Challenge, ChallengeCategorie
from inscriptions.tests.base import BaseTestCase


class ChallengeMatchingTestCase(BaseTestCase):
    """`Challenge` matches the same runner/team across different `Course`s
    using fuzzy name comparison (`CompareNames`, built on Postgres'
    `levenshtein`/`unaccent`). Those SQL functions have no SQLite fallback
    (see `functions.py` vs `models.py`), so this suite only makes sense
    against a real PostgreSQL database - which is what `docker-compose run
    test` provides."""

    def setUp(self):
        super().setUp()
        self.course_a = CourseFactory()
        self.course_b = CourseFactory()
        self.categorie_a = CategorieFactory(course=self.course_a, sexe='H', min_age=18)
        self.categorie_b = CategorieFactory(course=self.course_b, sexe='H', min_age=18)

        self.challenge = Challenge.objects.create(nom='Challenge Test', uid='chaltest', mode='nord2018')
        self.challenge.courses.add(self.course_a, self.course_b)
        self.challenge_categorie = ChallengeCategorie.objects.create(
            challenge=self.challenge, nom='Solo Homme', code='SOLOH',
            min_equipiers=1, max_equipiers=1, min_age=18, sexe='H', validation='',
        )
        self.challenge_categorie.categories.add(self.categorie_a, self.categorie_b)

    def _solo_equipe(self, course, categorie, nom, prenom='Jean'):
        equipe = EquipeFactory(course=course, categorie=categorie, nombre=1, nom='Equipe %s' % nom)
        EquipierFactory(equipe=equipe, numero=1, nom=nom, prenom=prenom, sexe='H', date_de_naissance=date(1990, 1, 1))
        return equipe

    def test_first_inscription_creates_a_new_participation(self):
        equipe = self._solo_equipe(self.course_a, self.categorie_a, 'Dupont')
        participation = self.challenge.inscription_equipe(equipe)
        self.assertIsNotNone(participation)
        self.assertEqual(self.challenge.participations.count(), 1)
        self.assertEqual(participation.equipes.get().equipe, equipe)

    def test_same_runner_in_a_second_course_joins_the_same_participation(self):
        equipe_a = self._solo_equipe(self.course_a, self.categorie_a, 'Dupont')
        equipe_b = self._solo_equipe(self.course_b, self.categorie_b, 'Dupont')
        self.challenge.inscription_equipe(equipe_a)
        participation = self.challenge.inscription_equipe(equipe_b)

        self.assertEqual(self.challenge.participations.count(), 1)
        self.assertEqual(
            set(participation.equipes.values_list('equipe', flat=True)),
            {equipe_a.id, equipe_b.id},
        )

    def test_slightly_misspelled_name_still_matches(self):
        equipe_a = self._solo_equipe(self.course_a, self.categorie_a, 'Dupont', prenom='Jean')
        equipe_b = self._solo_equipe(self.course_b, self.categorie_b, 'Dupon', prenom='Jean')  # 1 letter off
        self.challenge.inscription_equipe(equipe_a)
        self.challenge.inscription_equipe(equipe_b)
        self.assertEqual(self.challenge.participations.count(), 1)

    def test_different_runner_creates_a_separate_participation(self):
        equipe_a = self._solo_equipe(self.course_a, self.categorie_a, 'Dupont')
        equipe_b = self._solo_equipe(self.course_b, self.categorie_b, 'Martin', prenom='Alice')
        self.challenge.inscription_equipe(equipe_a)
        self.challenge.inscription_equipe(equipe_b)
        self.assertEqual(self.challenge.participations.count(), 2)

    def test_equipe_not_matching_any_challenge_category_is_skipped(self):
        # min_age=18 on the challenge category, equipier here is a minor
        equipe = EquipeFactory(course=self.course_a, categorie=self.categorie_a, nombre=1)
        EquipierFactory(
            equipe=equipe, numero=1, sexe='H',
            date_de_naissance=date.today().replace(year=date.today().year - 10),
        )
        result = self.challenge.inscription_equipe(equipe)
        self.assertIsNone(result)
        self.assertEqual(self.challenge.participations.count(), 0)

    def test_removing_a_course_from_the_challenge_removes_its_team(self):
        equipe_a = self._solo_equipe(self.course_a, self.categorie_a, 'Dupont')
        equipe_b = self._solo_equipe(self.course_b, self.categorie_b, 'Martin', prenom='Alice')
        self.challenge.inscription_equipe(equipe_a)
        self.challenge.inscription_equipe(equipe_b)

        self.challenge.del_course(self.course_a)

        self.assertEqual(self.challenge.participations.count(), 1)
        remaining = self.challenge.participations.get()
        self.assertEqual(remaining.equipes.get().equipe, equipe_b)


class ChallengeScoringTestCase(BaseTestCase):
    def test_compute_course_assigns_points_by_position(self):
        course = CourseFactory()
        categorie = CategorieFactory(course=course, sexe='H', min_age=18)
        challenge = Challenge.objects.create(nom='Scoring', uid='scoring1', mode='nord2018')
        challenge.courses.add(course)
        challenge_categorie = ChallengeCategorie.objects.create(
            challenge=challenge, nom='Solo Homme', code='SOLOH',
            min_equipiers=1, max_equipiers=1, min_age=18, sexe='H', validation='',
        )
        challenge_categorie.categories.add(categorie)

        first = EquipeFactory(course=course, categorie=categorie, nombre=1, position_generale=1)
        EquipierFactory(equipe=first, numero=1, nom='Premier', sexe='H', date_de_naissance=date(1990, 1, 1))
        second = EquipeFactory(course=course, categorie=categorie, nombre=1, position_generale=2)
        EquipierFactory(equipe=second, numero=1, nom='Second', sexe='H', date_de_naissance=date(1990, 1, 1))

        challenge.inscription_equipe(first)
        challenge.inscription_equipe(second)
        challenge.compute_course(course)

        first_challenge = first.challenges.get()
        second_challenge = second.challenges.get()
        self.assertGreater(first_challenge.points, second_challenge.points)
