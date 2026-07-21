from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile

from inscriptions.factories import CourseFactory, EquipeFactory, EquipierFactory
from inscriptions.tests.base import BaseTestCase

MAJEUR = date(1990, 1, 1)
MINEUR = date.today().replace(year=date.today().year - 15)


def make_file():
    return SimpleUploadedFile('certificat.pdf', b'%PDF-1.4 fake content')


class EquipierAgeTestCase(BaseTestCase):
    def test_age_uses_course_date_by_default(self):
        course = CourseFactory(date=date(2030, 6, 15), date_age=None)
        equipier = EquipierFactory(equipe__course=course, date_de_naissance=date(2000, 6, 16))
        # turns 30 the day after the course -> still 29 on course day
        self.assertEqual(equipier.age(), 29)

    def test_age_uses_date_age_override_when_set(self):
        course = CourseFactory(date=date(2030, 6, 15), date_age=date(2029, 1, 1))
        equipier = EquipierFactory(equipe__course=course, date_de_naissance=date(2000, 6, 16))
        self.assertEqual(equipier.age(), 28)

    def test_leap_year_birthday_does_not_crash(self):
        course = CourseFactory(date=date(2031, 3, 1))  # non-leap year
        equipier = EquipierFactory(equipe__course=course, date_de_naissance=date(2000, 2, 29))
        self.assertEqual(equipier.age(), 31)


class EquipierDossierStateMachineTestCase(BaseTestCase):
    """`Equipier.save()` recomputes verifier/valide/erreur/*_manquant(e) from
    the raw piece_jointe/autorisation state on every save - this pins down
    each branch of that logic."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory(date=date.today().replace(year=date.today().year + 1))

    def _equipier(self, **kwargs):
        kwargs.setdefault('equipe__course', self.course)
        return EquipierFactory(**kwargs)

    def test_no_document_and_not_marked_valid_is_missing(self):
        e = self._equipier(date_de_naissance=MAJEUR, justificatif='certificat', piece_jointe_valide=None)
        self.assertTrue(e.certificat_manquant)
        self.assertFalse(e.licence_manquante)
        self.assertFalse(e.valide)
        self.assertFalse(e.erreur)
        self.assertFalse(e.verifier)

    def test_no_document_but_organizer_marked_it_valid_manually(self):
        # e.g. certificate received by mail and validated without an upload
        e = self._equipier(date_de_naissance=MAJEUR, justificatif='certificat', piece_jointe_valide=True)
        self.assertFalse(e.certificat_manquant)
        self.assertTrue(e.valide)

    def test_uploaded_document_pending_review_needs_verification(self):
        e = self._equipier(date_de_naissance=MAJEUR, justificatif='licence', piece_jointe_valide=None)
        e.piece_jointe = make_file()
        e.save()
        self.assertTrue(e.verifier)
        self.assertFalse(e.erreur)
        self.assertFalse(e.valide)
        self.assertFalse(e.licence_manquante)

    def test_uploaded_document_rejected_is_an_error_and_still_missing(self):
        e = self._equipier(date_de_naissance=MAJEUR, justificatif='licence', piece_jointe_valide=None)
        e.piece_jointe = make_file()
        e.save()
        e.piece_jointe_valide = False
        e.save()
        self.assertTrue(e.erreur)
        self.assertTrue(e.licence_manquante)
        self.assertFalse(e.valide)
        self.assertFalse(e.verifier)

    def test_uploaded_document_approved_is_valid(self):
        # Uploading and approving in the same save() doesn't work: any change
        # to piece_jointe forces piece_jointe_valide back to None (see
        # test_editing_name_resets_document_validation) - approval has to be
        # a separate save, as it would be from the organizer backoffice.
        e = self._equipier(date_de_naissance=MAJEUR, justificatif='licence', piece_jointe_valide=None)
        e.piece_jointe = make_file()
        e.save()
        e.piece_jointe_valide = True
        e.save()
        self.assertTrue(e.valide)
        self.assertFalse(e.erreur)
        self.assertFalse(e.verifier)

    def test_editing_name_resets_document_validation(self):
        e = self._equipier(date_de_naissance=MAJEUR, justificatif='certificat', piece_jointe_valide=True)
        self.assertTrue(e.valide)
        e.nom = 'AutreNom'
        e.save()
        self.assertIsNone(e.piece_jointe_valide)
        self.assertFalse(e.valide)

    def test_minor_without_autorisation_is_not_valid_even_with_valid_certificate(self):
        e = self._equipier(date_de_naissance=MINEUR, justificatif='certificat', piece_jointe_valide=True)
        self.assertTrue(e.autorisation_manquante)
        self.assertFalse(e.valide)

    def test_minor_with_valid_autorisation_and_certificate_is_valid(self):
        e = self._equipier(date_de_naissance=MINEUR, justificatif='certificat', piece_jointe_valide=True)
        e.autorisation = make_file()
        e.save()  # uploading resets autorisation_valide to None, see above
        e.autorisation_valide = True
        e.save()
        self.assertFalse(e.autorisation_manquante)
        self.assertTrue(e.valide)

    def test_major_ignores_autorisation_entirely(self):
        e = self._equipier(date_de_naissance=MAJEUR, justificatif='certificat', piece_jointe_valide=True)
        self.assertFalse(e.autorisation_manquante)
        self.assertTrue(e.valide)


class EquipeDossierAggregationTestCase(BaseTestCase):
    """`Equipe.dossier_complet_auto()`/`verifier()` aggregate over the team's
    equipiers, but only up to `equipe.nombre` (extra rows are ignored)."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.equipe = EquipeFactory(course=self.course, nombre=2)

    def test_complete_when_all_members_valid(self):
        EquipierFactory(equipe=self.equipe, numero=1, date_de_naissance=MAJEUR, piece_jointe_valide=True)
        EquipierFactory(equipe=self.equipe, numero=2, date_de_naissance=MAJEUR, piece_jointe_valide=True)
        self.assertTrue(self.equipe.dossier_complet_auto())
        self.assertFalse(self.equipe.verifier())

    def test_pending_when_one_member_not_yet_validated(self):
        EquipierFactory(equipe=self.equipe, numero=1, date_de_naissance=MAJEUR, piece_jointe_valide=True)
        EquipierFactory(equipe=self.equipe, numero=2, date_de_naissance=MAJEUR, piece_jointe_valide=None)
        self.assertIsNone(self.equipe.dossier_complet_auto())

    def test_error_when_one_member_rejected(self):
        EquipierFactory(equipe=self.equipe, numero=1, date_de_naissance=MAJEUR, piece_jointe_valide=True)
        e2 = EquipierFactory(equipe=self.equipe, numero=2, date_de_naissance=MAJEUR, piece_jointe_valide=None)
        e2.piece_jointe = make_file()
        e2.piece_jointe_valide = False
        e2.save()
        self.assertFalse(self.equipe.dossier_complet_auto())

    def test_member_beyond_nombre_is_ignored(self):
        EquipierFactory(equipe=self.equipe, numero=1, date_de_naissance=MAJEUR, piece_jointe_valide=True)
        EquipierFactory(equipe=self.equipe, numero=2, date_de_naissance=MAJEUR, piece_jointe_valide=True)
        # leftover row from a previous, larger version of the team
        EquipierFactory(equipe=self.equipe, numero=3, date_de_naissance=MAJEUR, piece_jointe_valide=None)
        self.assertTrue(self.equipe.dossier_complet_auto())
