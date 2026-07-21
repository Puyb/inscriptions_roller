from inscriptions.factories import CategorieFactory, CourseFactory, EquipeFactory
from inscriptions.models import NoPlaceLeftException
from inscriptions.tests.base import BaseTestCase


class GetNumeroTestCase(BaseTestCase):
    """`Equipe.getNumero()` assigns the first free bib number in the
    category's [numero_debut, numero_fin] range, raising once it's full."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.categorie = CategorieFactory(course=self.course, numero_debut=300, numero_fin=302)

    def test_first_team_gets_range_start(self):
        equipe = EquipeFactory(course=self.course, categorie=self.categorie)
        self.assertEqual(equipe.numero, 300)

    def test_numbers_are_assigned_sequentially(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie)
        e2 = EquipeFactory(course=self.course, categorie=self.categorie)
        e3 = EquipeFactory(course=self.course, categorie=self.categorie)
        self.assertEqual([e1.numero, e2.numero, e3.numero], [300, 301, 302])

    def test_a_hole_left_by_a_deleted_team_is_reused(self):
        e1 = EquipeFactory(course=self.course, categorie=self.categorie)
        e2 = EquipeFactory(course=self.course, categorie=self.categorie)
        EquipeFactory(course=self.course, categorie=self.categorie)  # fills the range (300-302)
        e2.delete()
        e4 = EquipeFactory(course=self.course, categorie=self.categorie)
        self.assertEqual(e4.numero, e2.numero)

    def test_raises_when_the_category_is_full(self):
        for _ in range(3):
            EquipeFactory(course=self.course, categorie=self.categorie)
        with self.assertRaises(NoPlaceLeftException):
            EquipeFactory(course=self.course, categorie=self.categorie)

    def test_categories_do_not_share_numbering_ranges(self):
        other_categorie = CategorieFactory(course=self.course, numero_debut=400, numero_fin=402)
        for _ in range(3):
            EquipeFactory(course=self.course, categorie=self.categorie)
        # the first category is full, but a different range is untouched
        equipe = EquipeFactory(course=self.course, categorie=other_categorie)
        self.assertEqual(equipe.numero, 400)


class GetPrefixTestCase(BaseTestCase):
    def test_no_prefix_when_ajouter_nombre_is_false(self):
        categorie = CategorieFactory(ajouter_nombre=False, numero_fin=99)
        self.assertEqual(categorie.get_prefix(nombre=3), 0)

    def test_prefix_is_team_size_padded_to_range_width(self):
        categorie = CategorieFactory(ajouter_nombre=True, numero_fin=99)  # 2-digit range
        self.assertEqual(categorie.get_prefix(nombre=3), 300)

    def test_numero_assignment_uses_the_prefixed_range(self):
        course = CourseFactory()
        categorie = CategorieFactory(course=course, ajouter_nombre=True, numero_debut=0, numero_fin=9)
        equipe = EquipeFactory(course=course, categorie=categorie, nombre=2)
        # prefix = 2 * 10^len('9') = 20, so the range becomes [20, 29]
        self.assertEqual(equipe.numero, 20)
