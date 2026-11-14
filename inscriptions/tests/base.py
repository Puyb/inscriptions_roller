import shutil
import tempfile

from django.test import TestCase, override_settings


class BaseTestCase(TestCase):
    """Common setup for tests that go through `Equipe.save()`/`Equipier.save()`.

    - `Equipe.save()` geocode la ville du gerant via `models.lookup_ville()`, qui ne lit que
      la table locale `CodePostal` (aucun appel reseau) : vide par defaut dans les tests, donc
      `gerant_ville2` reste nul sauf si le test cree des `CodePostal`.
    - Uploaded files (`Equipier.piece_jointe`/`autorisation`) are written under
      `MEDIA_ROOT`, which in dev is the bind-mounted `inscriptions/uploads/`.
      Redirect it to a throwaway directory so tests never leave files behind
      in the real upload folder.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp(prefix='enduroller-tests-media-')
        cls._media_root_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_root_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_root_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()


def equipier_formset_data(equipiers, total_forms=None):
    """Build the `form-N-*` POST fields for `EquipierFormset` from a list of dicts.

    Each dict may contain: nom, prenom, sexe, date_de_naissance (a `date`),
    justificatif, num_licence, id.
    """
    data = {
        'form-TOTAL_FORMS': str(total_forms if total_forms is not None else len(equipiers)),
        'form-INITIAL_FORMS': str(sum(1 for e in equipiers if e.get('id'))),
        'form-MIN_NUM_FORMS': '0',
        'form-MAX_NUM_FORMS': '1000',
    }
    for i, equipier in enumerate(equipiers):
        prefix = 'form-%d-' % i
        dob = equipier.get('date_de_naissance')
        data.update({
            prefix + 'id': equipier.get('id', ''),
            prefix + 'nom': equipier.get('nom', ''),
            prefix + 'prenom': equipier.get('prenom', ''),
            prefix + 'sexe': equipier.get('sexe', ''),
            prefix + 'date_de_naissance_day': str(dob.day) if dob else '1',
            prefix + 'date_de_naissance_month': str(dob.month) if dob else '1',
            prefix + 'date_de_naissance_year': str(dob.year) if dob else '1990',
            prefix + 'autorisation': '',
            prefix + 'justificatif': equipier.get('justificatif', 'certificat'),
            prefix + 'num_licence': equipier.get('num_licence', ''),
            prefix + 'piece_jointe': '',
        })
    return data


def equipe_form_data(**overrides):
    data = {
        'prix': '0',
        'nom': 'Equipe Test',
        'club': '',
        'gerant_nom': 'Dupont',
        'gerant_prenom': 'Jean',
        'gerant_adresse1': '',
        'gerant_adresse2': '',
        'gerant_ville': 'Paris',
        'gerant_code_postal': '75000',
        'gerant_pays': 'FR',
        'gerant_email': 'jean.dupont@example.com',
        'gerant_telephone': '0102030405',
        'nombre': '1',
        'categorie': '',
        'conditions': 'on',
    }
    data.update(overrides)
    return data
