from datetime import date, timedelta
from decimal import Decimal

from inscriptions.factories import (
    CategorieFactory, CourseFactory, EquipeFactory, EquipierFactory,
    ExtraQuestionFactory, ExtraQuestionChoiceFactory,
)
from inscriptions.tests.base import BaseTestCase


class CategoriePrixTestCase(BaseTestCase):
    """`Categorie.prix/price_base/price_equipier` apply a price tier per
    `Course.dates_augmentation` threshold that's crossed."""

    def setUp(self):
        super().setUp()
        self.d1 = date.today() + timedelta(days=10)
        self.d2 = date.today() + timedelta(days=20)
        self.course = CourseFactory(dates_augmentation=[self.d1, self.d2])
        self.categorie = CategorieFactory(
            course=self.course,
            prices_base=[Decimal('100'), Decimal('120'), Decimal('150')],
            prices_equipier=[Decimal('10'), Decimal('15'), Decimal('20')],
        )

    def test_before_first_threshold(self):
        d = self.d1 - timedelta(days=1)
        self.assertEqual(self.categorie.price_base(d), Decimal('100'))
        self.assertEqual(self.categorie.price_equipier(d), Decimal('10'))
        self.assertEqual(self.categorie.prix(d, nombre=2), Decimal('120'))

    def test_on_first_threshold(self):
        self.assertEqual(self.categorie.price_base(self.d1), Decimal('120'))
        self.assertEqual(self.categorie.prix(self.d1, nombre=2), Decimal('150'))

    def test_after_last_threshold(self):
        d = self.d2 + timedelta(days=1)
        self.assertEqual(self.categorie.price_base(d), Decimal('150'))
        self.assertEqual(self.categorie.prix(d, nombre=2), Decimal('190'))

    def test_no_price_tiers_defined(self):
        categorie = CategorieFactory(course=self.course, prices_base=[], prices_equipier=[])
        self.assertEqual(categorie.prix(date.today(), nombre=3), 0)

    def test_prices_pads_missing_tiers_with_last_value(self):
        categorie = CategorieFactory(
            course=self.course,
            prices_base=[Decimal('100')],
            prices_equipier=[Decimal('10'), Decimal('15')],
        )
        # 2 dates_augmentation -> 3 tiers expected
        self.assertEqual(list(categorie.prices()), [
            (Decimal('100'), Decimal('10')),
            (Decimal('100'), Decimal('15')),
            (Decimal('100'), Decimal('15')),
        ])


class ExtraQuestionPrixTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.d1 = date.today() + timedelta(days=10)
        self.course = CourseFactory(dates_augmentation=[self.d1])

    def test_checkbox_price_before_and_after_threshold(self):
        question = ExtraQuestionFactory(course=self.course, type='checkbox', prices=[Decimal('5'), Decimal('8')])
        self.assertEqual(question.price(self.d1 - timedelta(days=1)), Decimal('5'))
        self.assertEqual(question.price(self.d1), Decimal('8'))

    def test_get_price_by_value_text_is_never_priced(self):
        question = ExtraQuestionFactory(course=self.course, type='text', prices=[Decimal('5')])
        self.assertIsNone(question.getPriceByValue(date.today(), 'anything'))

    def test_get_price_by_value_checkbox(self):
        question = ExtraQuestionFactory(course=self.course, type='checkbox', prices=[Decimal('5')])
        self.assertEqual(question.getPriceByValue(date.today(), True), Decimal('5'))
        self.assertIsNone(question.getPriceByValue(date.today(), False))

    def test_get_price_by_value_radio_uses_matching_choice(self):
        question = ExtraQuestionFactory(course=self.course, type='radio', prices=[])
        cheap = ExtraQuestionChoiceFactory(question=question, label='Cheap', prices=[Decimal('3')])
        expensive = ExtraQuestionChoiceFactory(question=question, label='Expensive', prices=[Decimal('12')])
        self.assertEqual(question.getPriceByValue(date.today(), 'Cheap'), Decimal('3'))
        self.assertEqual(question.getPriceByValue(date.today(), 'Expensive'), Decimal('12'))
        self.assertIsNone(question.getPriceByValue(date.today(), 'Unknown choice'))


class EquipeFactureTestCase(BaseTestCase):
    """`Equipe.facture()` assembles the invoice lines the server uses to
    recompute `prix` - this is what protects against a client sending a
    forged `prix` value."""

    def setUp(self):
        super().setUp()
        self.categorie = CategorieFactory(prices_base=[Decimal('50')], prices_equipier=[Decimal('10')])
        self.course = self.categorie.course

    def test_base_line_only(self):
        equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=2)
        lines = equipe.facture()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['prix'], Decimal('70'))  # 50 + 2*10

    def test_equipe_level_checkbox_extra_adds_a_line(self):
        extra = ExtraQuestionFactory(course=self.course, page='Equipe', type='checkbox', prices=[Decimal('5')])
        equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=1, extra={extra.getId(): True})
        lines = equipe.facture()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1]['prix'], Decimal('5'))
        self.assertEqual(lines[1]['quantite'], 1)

    def test_equipe_level_checkbox_extra_unchecked_adds_no_line(self):
        extra = ExtraQuestionFactory(course=self.course, page='Equipe', type='checkbox', prices=[Decimal('5')])
        equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=1, extra={extra.getId(): False})
        self.assertEqual(len(equipe.facture()), 1)

    def test_equipier_level_extra_is_aggregated_across_the_team(self):
        extra = ExtraQuestionFactory(course=self.course, page='Equipier', type='checkbox', prices=[Decimal('3')])
        equipe = EquipeFactory(course=self.course, categorie=self.categorie, nombre=2)
        EquipierFactory(equipe=equipe, numero=1, extra={extra.getId(): True})
        EquipierFactory(equipe=equipe, numero=2, extra={extra.getId(): True})
        lines = equipe.facture()
        extra_line = next(l for l in lines if l['label'] == extra.label)
        self.assertEqual(extra_line['quantite'], 2)
        self.assertEqual(extra_line['prix'], Decimal('6'))
