from decimal import Decimal

from inscriptions.factories import CategorieFactory, EquipeFactory
from inscriptions.models import Paiement
from inscriptions.tests.base import BaseTestCase
from inscriptions.utils import repartition_frais


class RepartitionFraisTestCase(BaseTestCase):
    """Pure function: splits a total fee across several amounts, pro-rata,
    rounding down to the cent and redistributing the leftover cents so the
    parts always sum back to exactly `frais` - this handles real money, it
    deserves unit coverage independent of any view/model."""

    def test_single_amount_gets_all_the_fees(self):
        result = list(repartition_frais([Decimal('50.00')], Decimal('2.00')))
        self.assertEqual(result, [Decimal('2.00')])

    def test_no_fees_splits_to_zero(self):
        result = list(repartition_frais([Decimal('50.00'), Decimal('30.00')], Decimal('0.00')))
        self.assertEqual(result, [Decimal('0.00'), Decimal('0.00')])

    def test_prorata_split_sums_back_to_the_total_fee(self):
        montants = [Decimal('10.00'), Decimal('20.00'), Decimal('30.00')]
        frais = Decimal('1.00')
        result = list(repartition_frais(montants, frais))
        self.assertEqual(sum(result), frais)

    def test_rounding_remainder_is_redistributed_and_still_sums_exactly(self):
        # 1/3, 1/3, 1/3 of 1.00 does not divide evenly into cents
        montants = [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')]
        frais = Decimal('1.00')
        result = list(repartition_frais(montants, frais))
        self.assertEqual(sum(result), frais)
        self.assertEqual(len(result), 3)


class PaiementRepartitionTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        categorie = CategorieFactory(prices_base=[Decimal('100.00')], prices_equipier=[])
        self.equipe = EquipeFactory(categorie=categorie, prix=Decimal('100.00'))

    def test_reste_before_any_payment_is_full_price(self):
        repartition = self.equipe.paiements.create(
            paiement=Paiement.objects.create(type='chèque', montant=Decimal('40.00')),
            montant=Decimal('40.00'),
        )
        self.assertEqual(repartition.paye(), Decimal('0.00'))
        self.assertEqual(repartition.reste(), Decimal('100.00'))

    def test_reste_accounts_for_other_payments_on_the_same_team(self):
        # reste() is "balance due not counting this payment" - i.e. the
        # amount this payment itself is expected to settle.
        self.equipe.paiements.create(
            paiement=Paiement.objects.create(type='chèque', montant=Decimal('40.00')),
            montant=Decimal('40.00'),
        )
        second = self.equipe.paiements.create(
            paiement=Paiement.objects.create(type='espèce', montant=Decimal('60.00')),
            montant=Decimal('60.00'),
        )
        self.assertEqual(second.paye(), Decimal('40.00'))
        self.assertEqual(second.reste(), Decimal('60.00'))

    def test_equipe_paiement_complet(self):
        self.assertFalse(self.equipe.paiement_complet())
        self.equipe.paiements.create(
            paiement=Paiement.objects.create(type='chèque', montant=Decimal('100.00')),
            montant=Decimal('100.00'),
        )
        self.assertTrue(self.equipe.paiement_complet())
