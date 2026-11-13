import json
import unittest
from decimal import Decimal

from django.contrib.auth.models import User

from inscriptions.admin_course import EquipeAdmin, PaiementAdmin, site as course_site
from inscriptions.factories import CourseFactory, EquipeFactory
from inscriptions.models import Accreditation, Paiement, PaiementRepartition
from inscriptions.tests.base import BaseTestCase

ADD_URL = '/course/inscriptions/paiement/add/'
LIST_URL = '/course/inscriptions/paiement/'
SEARCH_URL = '/course/inscriptions/paiement/search/equipe/'


def change_url(paiement):
    return '/course/inscriptions/paiement/%d/change/' % paiement.id


def login_as_organizer(client, course, role='admin', username=None):
    user = User.objects.create_user(
        username or 'organizer%d' % course.id, 'o%d@example.com' % course.id, 'pass1234',
    )
    Accreditation.objects.create(user=user, course=course, role=role)
    client.force_login(user)
    set_course_cookie(client, course)
    return user


def set_course_cookie(client, course):
    client.cookies['course_uid'] = course.uid
    client.cookies['course_id'] = str(course.id)


def make_paiement(equipes_montants, type='chèque', montant=None, **kwargs):
    """Crée un Paiement + ses répartitions. equipes_montants : [(equipe, montant)]."""
    if montant is None:
        montant = sum((Decimal(m) for _, m in equipes_montants), Decimal(0))
    paiement = Paiement.objects.create(type=type, montant=montant, **kwargs)
    for equipe, m in equipes_montants:
        PaiementRepartition.objects.create(paiement=paiement, equipe=equipe, montant=Decimal(m))
    return paiement


def post_tolerant(client, url, data):
    """POST qui avale une éventuelle exception serveur (HTTP 500) : renvoie None dans ce cas."""
    try:
        return client.post(url, data)
    except Exception:
        return None


def post_data(montant, repartitions, type='chèque', **extra):
    """repartitions : [(equipe, montant_str)]"""
    data = {
        'type': type,
        'montant': montant,
        'detail': '',
        'equipe_id': [str(e.id) for e, _ in repartitions],
        'repartition': [m for _, m in repartitions],
    }
    data.update(extra)
    return data


class PaiementModelTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.equipe = EquipeFactory(course=self.course, prix=Decimal('50.00'))

    def test_equipe_without_payment(self):
        self.assertEqual(self.equipe.montant_paiements, Decimal(0))
        self.assertEqual(self.equipe.reste_a_payer, Decimal('50.00'))
        self.assertFalse(self.equipe.paiement_complet())

    def test_partial_then_complete_payment(self):
        make_paiement([(self.equipe, '20.00')])
        self.assertEqual(self.equipe.montant_paiements, Decimal('20.00'))
        self.assertEqual(self.equipe.reste_a_payer, Decimal('30.00'))
        self.assertFalse(self.equipe.paiement_complet())
        make_paiement([(self.equipe, '30.00')], type='virement')
        self.assertEqual(self.equipe.montant_paiements, Decimal('50.00'))
        self.assertTrue(self.equipe.paiement_complet())

    def test_overpayment_counts_as_complete(self):
        make_paiement([(self.equipe, '60.00')])
        self.assertTrue(self.equipe.paiement_complet())
        self.assertEqual(self.equipe.reste_a_payer, Decimal('-10.00'))

    def test_offert_makes_price_zero(self):
        make_paiement([(self.equipe, '0.00')], type='offert')
        self.assertTrue(self.equipe.offert)
        self.assertEqual(self.equipe.prix_reel, Decimal(0))
        self.assertTrue(self.equipe.paiement_complet())

    def test_montant_frais_summed_per_team(self):
        p = make_paiement([(self.equipe, '50.00')])
        PaiementRepartition.objects.filter(paiement=p).update(montant_frais=Decimal('1.50'))
        self.assertEqual(self.equipe.montant_frais, Decimal('1.50'))

    def test_payment_with_null_amount_ignored_in_total(self):
        p = Paiement.objects.create(type='stripe', montant=None)
        PaiementRepartition.objects.create(paiement=p, equipe=self.equipe, montant=Decimal('10.00'))
        self.assertEqual(self.equipe.montant_paiements, Decimal(0))

    def test_cascade_delete_paiement_removes_repartitions(self):
        p = make_paiement([(self.equipe, '10.00')])
        p.delete()
        self.assertFalse(PaiementRepartition.objects.exists())
        self.assertEqual(self.equipe.montant_paiements, Decimal(0))

    def test_repartition_paye_and_reste(self):
        p1 = make_paiement([(self.equipe, '20.00')])
        make_paiement([(self.equipe, '10.00')])
        rep = p1.equipes.get()
        # paye() exclut `self.id`, mais filtre des Paiement par id de répartition
        # (comportement existant) : on vérifie seulement que reste = prix - paye.
        self.assertEqual(rep.reste(), self.equipe.prix_reel - rep.paye())


class PaiementChangeBaseTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.user = login_as_organizer(self.client, self.course)
        self.e1 = EquipeFactory(course=self.course, prix=Decimal('50.00'))
        self.e2 = EquipeFactory(course=self.course, prix=Decimal('30.00'))


class PaiementAddTestCase(PaiementChangeBaseTestCase):
    def test_add_form_displays(self):
        r = self.client.get(ADD_URL)
        self.assertEqual(r.status_code, 200)

    def test_add_form_prefilled_from_equipe_ids(self):
        make_paiement([(self.e1, '10.00')])
        r = self.client.get(ADD_URL + '?equipe_id=%d&equipe_id=%d' % (self.e1.id, self.e2.id))
        self.assertEqual(r.status_code, 200)
        reps = r.context['repartitions']
        self.assertEqual({x['equipe'].id for x in reps}, {self.e1.id, self.e2.id})
        by_id = {x['equipe'].id: x for x in reps}
        self.assertEqual(by_id[self.e1.id]['reste'], Decimal('40.00'))
        self.assertEqual(by_id[self.e1.id]['paiement'], Decimal('10.00'))
        # montant initial = somme des restes à payer
        self.assertEqual(r.context['paiement_form'].initial['montant'], Decimal('70.00'))

    def test_add_form_prefill_ignores_equipe_of_unrelated_course(self):
        other = EquipeFactory(prix=Decimal('20.00'))
        r = self.client.get(ADD_URL + '?equipe_id=%d' % other.id)
        self.assertEqual(r.context['repartitions'], [])

    def test_create_cheque_single_team_redirects_to_list(self):
        r = self.client.post(ADD_URL, post_data('50.00', [(self.e1, '50.00')]))
        self.assertRedirects(r, LIST_URL, fetch_redirect_response=False)
        p = Paiement.objects.get()
        self.assertEqual(p.type, 'chèque')
        self.assertEqual(p.montant, Decimal('50.00'))
        self.assertEqual(p.equipes.get().equipe_id, self.e1.id)
        self.assertTrue(self.e1.paiement_complet())

    def test_create_virement_split_across_two_teams(self):
        r = self.client.post(ADD_URL, post_data('80.00', [(self.e1, '50.00'), (self.e2, '30.00')],
                                                type='virement'))
        self.assertEqual(r.status_code, 302)
        p = Paiement.objects.get()
        self.assertEqual(p.type, 'virement')
        self.assertEqual(
            {x.equipe_id: x.montant for x in p.equipes.all()},
            {self.e1.id: Decimal('50.00'), self.e2.id: Decimal('30.00')},
        )

    def test_partial_payment_split_leaves_remainder(self):
        self.client.post(ADD_URL, post_data('20.00', [(self.e1, '15.00'), (self.e2, '5.00')], type='espèce'))
        self.assertEqual(self.e1.reste_a_payer, Decimal('35.00'))
        self.assertEqual(self.e2.reste_a_payer, Decimal('25.00'))

    def test_comma_decimal_separator_accepted_in_repartition(self):
        r = self.client.post(ADD_URL, post_data('12.50', [(self.e1, '12,50')]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(PaiementRepartition.objects.get().montant, Decimal('12.50'))

    def test_mismatching_total_rejected_and_nothing_saved(self):
        r = self.client.post(ADD_URL, post_data('50.00', [(self.e1, '40.00')]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Paiement.objects.exists())
        self.assertFalse(PaiementRepartition.objects.exists())
        msgs = [str(m) for m in r.context['messages']]
        self.assertTrue(any('incorrectes' in m for m in msgs))

    def test_total_below_sum_of_repartitions_rejected(self):
        r = self.client.post(ADD_URL, post_data('10.00', [(self.e1, '40.00')]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Paiement.objects.exists())

    def test_offert_does_not_require_matching_amounts(self):
        r = self.client.post(ADD_URL, post_data('0', [(self.e1, '0')], type='offert'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.e1.offert)
        self.e1.refresh_from_db()
        self.assertTrue(self.e1.paiement_complet())

    def test_offert_with_mismatching_amounts_is_accepted(self):
        r = self.client.post(ADD_URL, post_data('99.00', [(self.e1, '0')], type='offert'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Paiement.objects.get().type, 'offert')

    def test_invalid_type_rejected(self):
        r = post_tolerant(self.client, ADD_URL, post_data('50.00', [(self.e1, '50.00')], type=''))
        if r is not None:
            self.assertNotEqual(r.status_code, 302)
        self.assertFalse(Paiement.objects.exists())

    def test_invalid_type_rejected_cleanly(self):
        # BUG suspecté : paiement_change appelle paiement_form.save() sans
        # is_valid() -> ValueError (HTTP 500) au lieu de réafficher le formulaire.
        r = post_tolerant(self.client, ADD_URL, post_data('50.00', [(self.e1, '50.00')], type=''))
        self.assertIsNotNone(r)
        self.assertEqual(r.status_code, 200)

    def test_invalid_montant_rejected(self):
        r = post_tolerant(self.client, ADD_URL, post_data('abc', [(self.e1, '50.00')]))
        if r is not None:
            self.assertNotEqual(r.status_code, 302)
        self.assertFalse(Paiement.objects.exists())

    def test_invalid_montant_rejected_cleanly(self):
        # BUG suspecté : paiement_change appelle paiement_form.save() sans
        # is_valid() -> ValueError (HTTP 500) au lieu de réafficher le formulaire.
        r = post_tolerant(self.client, ADD_URL, post_data('abc', [(self.e1, '50.00')]))
        self.assertIsNotNone(r)
        self.assertEqual(r.status_code, 200)

    def test_montant_too_many_digits_rejected(self):
        r = post_tolerant(self.client, ADD_URL, post_data('12345678.00', [(self.e1, '12345678.00')]))
        if r is not None:
            self.assertNotEqual(r.status_code, 302)
        self.assertFalse(Paiement.objects.exists())

    def test_montant_too_many_digits_rejected_cleanly(self):
        # BUG suspecté : paiement_change appelle paiement_form.save() sans
        # is_valid() -> ValueError (HTTP 500) au lieu de réafficher le formulaire.
        r = post_tolerant(self.client, ADD_URL, post_data('12345678.00', [(self.e1, '12345678.00')]))
        self.assertIsNotNone(r)
        self.assertEqual(r.status_code, 200)

    def test_frais_and_detail_saved(self):
        self.client.post(ADD_URL, post_data('50.00', [(self.e1, '50.00')], montant_frais='1.20',
                                            detail='chèque n°1234'))
        p = Paiement.objects.get()
        self.assertEqual(p.montant_frais, Decimal('1.20'))
        self.assertEqual(p.detail, 'chèque n°1234')

    def test_single_equipe_id_in_query_redirects_to_team_page(self):
        r = self.client.post(ADD_URL + '?equipe_id=%d' % self.e1.id,
                             post_data('50.00', [(self.e1, '50.00')]))
        self.assertRedirects(r, '/course/inscriptions/equipe/%d/change/' % self.e1.id,
                             fetch_redirect_response=False)

    def test_several_equipe_ids_in_query_redirect_to_team_list(self):
        r = self.client.post(ADD_URL + '?equipe_id=%d&equipe_id=%d' % (self.e1.id, self.e2.id),
                             post_data('80.00', [(self.e1, '50.00'), (self.e2, '30.00')]))
        self.assertRedirects(r, '/course/inscriptions/equipe/', fetch_redirect_response=False)

    def test_equipe_of_other_course_is_refused_and_nothing_saved(self):
        other = EquipeFactory(prix=Decimal('20.00'))
        r = post_tolerant(self.client, ADD_URL, post_data('20.00', [(other, '20.00')]))
        if r is not None:
            self.assertNotEqual(r.status_code, 302)
        self.assertFalse(Paiement.objects.exists())
        self.assertFalse(PaiementRepartition.objects.exists())

    def test_equipe_of_other_course_gives_clean_error_not_a_crash(self):
        # BUG suspecté : `equipes[equipe_id]` lève KeyError (HTTP 500) au lieu
        # d'un message d'erreur de validation.
        other = EquipeFactory(prix=Decimal('20.00'))
        r = self.client.post(ADD_URL, post_data('20.00', [(other, '20.00')]))
        self.assertEqual(r.status_code, 200)

    def test_organizer_can_pay_team_of_another_accredited_recent_course(self):
        course2 = CourseFactory()
        Accreditation.objects.create(user=self.user, course=course2, role='admin')
        e = EquipeFactory(course=course2, prix=Decimal('20.00'))
        r = self.client.post(ADD_URL, post_data('70.00', [(self.e1, '50.00'), (e, '20.00')]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Paiement.objects.get().equipes.count(), 2)

    def test_payment_mail_failure_does_not_break_creation(self):
        # pas de TemplateMail 'paiement' : l'exception est avalée par send_equipes_mail
        r = self.client.post(ADD_URL, post_data('50.00', [(self.e1, '50.00')]))
        self.assertEqual(r.status_code, 302)


class PaiementEditDeleteTestCase(PaiementChangeBaseTestCase):
    def setUp(self):
        super().setUp()
        self.p = make_paiement([(self.e1, '20.00'), (self.e2, '10.00')])

    def test_change_form_displays_existing_repartitions(self):
        r = self.client.get(change_url(self.p))
        self.assertEqual(r.status_code, 200)
        reps = {x['equipe'].id: x for x in r.context['repartitions']}
        self.assertEqual(reps[self.e1.id]['montant'], Decimal('20.00'))
        # "déjà payé" exclut ce paiement, "reste" l'inclut
        self.assertEqual(reps[self.e1.id]['paiement'], Decimal(0))
        self.assertEqual(reps[self.e1.id]['reste'], Decimal('50.00'))
        self.assertFalse(r.context['readonly'])

    def test_change_replaces_repartitions(self):
        r = self.client.post(change_url(self.p), post_data('40.00', [(self.e1, '40.00')], type='virement'))
        self.assertRedirects(r, LIST_URL, fetch_redirect_response=False)
        self.p.refresh_from_db()
        self.assertEqual(self.p.montant, Decimal('40.00'))
        self.assertEqual(self.p.type, 'virement')
        self.assertEqual([(x.equipe_id, x.montant) for x in self.p.equipes.all()],
                         [(self.e1.id, Decimal('40.00'))])
        self.assertEqual(Paiement.objects.count(), 1)
        self.assertEqual(self.e2.montant_paiements, Decimal(0))

    def test_change_with_bad_total_is_rolled_back(self):
        r = self.client.post(change_url(self.p), post_data('99.00', [(self.e1, '40.00')]))
        self.assertEqual(r.status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(self.p.montant, Decimal('30.00'))
        self.assertEqual(self.p.equipes.count(), 2)

    def test_change_unknown_paiement_is_404(self):
        r = self.client.get('/course/inscriptions/paiement/999999/change/')
        self.assertEqual(r.status_code, 404)

    def test_stripe_payment_is_readonly_in_form(self):
        p = make_paiement([(self.e1, '5.00')], type='stripe')
        r = self.client.get(change_url(p))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['readonly'])

    def test_paypal_payment_is_readonly_in_form(self):
        p = make_paiement([(self.e1, '5.00')], type='paypal')
        r = self.client.get(change_url(p))
        self.assertTrue(r.context['readonly'])

    def test_cannot_edit_paiement_of_a_course_user_has_no_access_to(self):
        # BUG suspecté : paiement_change fait get_object_or_404(Paiement, id=id)
        # sans filtrer par course/accréditation -> un organisateur peut lire et
        # modifier le paiement d'une autre course par son id.
        other_course = CourseFactory()
        other = EquipeFactory(course=other_course, prix=Decimal('20.00'))
        p = make_paiement([(other, '20.00')])
        r = self.client.get(change_url(p))
        self.assertIn(r.status_code, (403, 404))

    def test_delete_via_admin(self):
        r = self.client.post('/course/inscriptions/paiement/%d/delete/' % self.p.id, {'post': 'yes'})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Paiement.objects.filter(id=self.p.id).exists())
        self.assertFalse(PaiementRepartition.objects.exists())
        self.assertEqual(self.e1.montant_paiements, Decimal(0))

    def test_delete_confirmation_page(self):
        r = self.client.get('/course/inscriptions/paiement/%d/delete/' % self.p.id)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Paiement.objects.filter(id=self.p.id).exists())


class PaiementSearchEquipeTestCase(PaiementChangeBaseTestCase):
    def search(self, text, **params):
        url = SEARCH_URL + ('?' + '&'.join('%s=%s' % kv for kv in params.items()) if params else '')
        return self.client.post(url, {'search': text})

    def test_search_by_name_returns_json(self):
        e = EquipeFactory(course=self.course, nom='Rapides Rollers', prix=Decimal('45.00'))
        r = self.search('rapides')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual([x['id'] for x in data['equipes']], [e.id])
        x = data['equipes'][0]
        self.assertEqual(x['nom'], 'Rapides Rollers')
        self.assertEqual(x['course'], self.course.nom)
        self.assertEqual(Decimal(x['prix']), Decimal('45.00'))
        self.assertEqual(Decimal(x['paiement']), Decimal(0))
        self.assertEqual(x['numero'], e.numero)

    def test_search_reports_already_paid_amount(self):
        make_paiement([(self.e1, '12.00')])
        data = json.loads(self.search(self.e1.nom).content)
        self.assertEqual(Decimal(data['equipes'][0]['paiement']), Decimal('12.00'))

    def test_search_every_word_must_match(self):
        EquipeFactory(course=self.course, nom='Alpha Beta')
        EquipeFactory(course=self.course, nom='Alpha Gamma')
        data = json.loads(self.search('alpha gamma').content)
        self.assertEqual([x['nom'] for x in data['equipes']], ['Alpha Gamma'])

    def test_search_no_match(self):
        data = json.loads(self.search('zzzzzz').content)
        self.assertEqual(data['equipes'], [])

    def test_search_excludes_courses_without_accreditation(self):
        EquipeFactory(nom='Secrete Autre Course')
        data = json.loads(self.search('secrete').content)
        self.assertEqual(data['equipes'], [])

    def test_search_includes_other_accredited_recent_course(self):
        course2 = CourseFactory()
        Accreditation.objects.create(user=self.user, course=course2, role='admin')
        e = EquipeFactory(course=course2, nom='Voisine Rapide')
        data = json.loads(self.search('voisine').content)
        self.assertEqual([x['id'] for x in data['equipes']], [e.id])

    def test_search_requires_login(self):
        self.client.logout()
        r = self.search('equipe')
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r['Location'])

    def test_search_without_search_param_fails_cleanly(self):
        # BUG suspecté : request.POST['search'] -> MultiValueDictKeyError (500).
        r = post_tolerant(self.client, SEARCH_URL, {})
        self.assertIsNotNone(r)
        self.assertEqual(r.status_code, 400)

    def test_search_with_paiement_id_returns_existing_montants(self):
        # BUG suspecté : `PaiementRepartition.object` (faute de frappe pour
        # `.objects`) -> AttributeError dès que ?id=<paiement> est passé
        # (utilisé en modification d'un paiement).
        p = make_paiement([(self.e1, '20.00')])
        r = self.search(self.e1.nom, id=p.id)
        data = json.loads(r.content)
        self.assertEqual(Decimal(data['equipes'][0]['montant']), Decimal('20.00'))


class PaiementAdminListTestCase(PaiementChangeBaseTestCase):
    def test_list_shows_only_payments_of_current_course(self):
        make_paiement([(self.e1, '50.00')], detail='ici')
        other_course = CourseFactory()
        other = EquipeFactory(course=other_course)
        make_paiement([(other, '40.00')])
        r = self.client.get(LIST_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['cl'].result_count, 1)
        self.assertEqual(r.context['cl'].result_list[0].montant, Decimal('50.00'))

    def test_list_without_duplicates_for_multi_team_payment(self):
        make_paiement([(self.e1, '50.00'), (self.e2, '30.00')])
        r = self.client.get(LIST_URL)
        self.assertEqual(r.context['cl'].result_count, 1)

    def test_payment_spanning_two_courses_visible_from_both(self):
        course2 = CourseFactory()
        Accreditation.objects.create(user=self.user, course=course2, role='admin')
        e = EquipeFactory(course=course2)
        make_paiement([(self.e1, '50.00'), (e, '10.00')])
        self.assertEqual(self.client.get(LIST_URL).context['cl'].result_count, 1)
        set_course_cookie(self.client, course2)
        self.assertEqual(self.client.get(LIST_URL).context['cl'].result_count, 1)

    def test_user_without_accreditation_on_cookie_course_is_denied(self):
        other_course = CourseFactory()
        other = EquipeFactory(course=other_course)
        make_paiement([(other, '40.00')])
        set_course_cookie(self.client, other_course)
        r = self.client.get(LIST_URL)
        self.assertNotEqual(r.status_code, 200)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        r = self.client.get(LIST_URL)
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r['Location'])
        r = self.client.get(ADD_URL)
        self.assertEqual(r.status_code, 302)

    def test_missing_course_cookie_is_denied(self):
        self.client.cookies.clear()
        r = self.client.get(LIST_URL)
        self.assertNotEqual(r.status_code, 200)

    def test_superuser_sees_payments_of_cookie_course(self):
        make_paiement([(self.e1, '50.00')])
        su = User.objects.create_superuser('root', 'root@example.com', 'pass1234')
        self.client.force_login(su)
        set_course_cookie(self.client, self.course)
        r = self.client.get(LIST_URL)
        self.assertEqual(r.context['cl'].result_count, 1)

    def test_filter_by_type(self):
        make_paiement([(self.e1, '50.00')], type='chèque')
        make_paiement([(self.e2, '30.00')], type='virement')
        r = self.client.get(LIST_URL + '?type=virement')
        self.assertEqual([p.type for p in r.context['cl'].result_list], ['virement'])

    def test_equipe_filter_restricts_to_team(self):
        make_paiement([(self.e1, '50.00')])
        make_paiement([(self.e2, '30.00')])
        r = self.client.get(LIST_URL + '?equipe_id=%d' % self.e2.id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p.montant for p in r.context['cl'].result_list], [Decimal('30.00')])

    def test_equipe_filter_without_value_keeps_everything(self):
        make_paiement([(self.e1, '50.00')])
        make_paiement([(self.e2, '30.00')])
        r = self.client.get(LIST_URL)
        self.assertEqual(r.context['cl'].result_count, 2)

    def test_equipe_filter_lookups_empty_without_value(self):
        from inscriptions.admin_course import PaiementEquipeFilter
        from django.test import RequestFactory
        f = PaiementEquipeFilter(RequestFactory().get('/'), {}, Paiement, course_site._registry[Paiement])
        self.assertEqual(f.lookups(None, None), ())

    def test_equipe_filter_lookups_with_value_shows_team(self):
        from inscriptions.admin_course import PaiementEquipeFilter
        from django.test import RequestFactory
        params = {'equipe_id': str(self.e1.id)}
        f = PaiementEquipeFilter(RequestFactory().get('/'), params, Paiement, course_site._registry[Paiement])
        lookups = f.lookups(None, None)
        self.assertEqual(lookups[0][0], str(self.e1.id))

    def test_equipes_column_single_team(self):
        p = make_paiement([(self.e1, '50.00')])
        admin = course_site._registry[Paiement]
        self.assertEqual(admin.equipes(p), str(self.e1))

    def test_equipes_column_several_teams_grouped_by_course(self):
        p = make_paiement([(self.e1, '50.00'), (self.e2, '30.00')])
        out = course_site._registry[Paiement].equipes(p)
        self.assertIn(self.course.uid, out)
        self.assertIn(str(self.e1.numero), out)
        self.assertIn(str(self.e2.numero), out)

    def test_equipes_column_many_teams_shows_count(self):
        eq = [EquipeFactory(course=self.course, prix=Decimal('1.00')) for _ in range(4)]
        p = make_paiement([(e, '1.00') for e in eq])
        self.assertEqual(course_site._registry[Paiement].equipes(p), '4')

    def test_montant_frais2_explicit_value_wins(self):
        admin = course_site._registry[Paiement]
        p = Paiement(type='stripe', montant=Decimal('100'), montant_frais=Decimal('2.00'))
        self.assertEqual(admin.montant_frais2(p), Decimal('2.00'))

    def test_montant_frais2_computed_by_type(self):
        admin = course_site._registry[Paiement]
        self.assertEqual(admin.montant_frais2(Paiement(type='paypal', montant=Decimal('100'))),
                         Decimal('3.65'))
        self.assertEqual(admin.montant_frais2(Paiement(type='stripe', montant=Decimal('100'))),
                         Decimal('1.65'))
        self.assertEqual(admin.montant_frais2(Paiement(type='chèque', montant=Decimal('100'))),
                         Decimal(0))
        self.assertEqual(admin.montant_frais2(Paiement(type='stripe', montant=None)), Decimal(0))

    def test_inline_readonly_columns(self):
        p = make_paiement([(self.e1, '50.00')])
        from inscriptions.admin_course import PaiementRepartitionInline
        inline = PaiementRepartitionInline(Paiement, course_site)
        rep = p.equipes.get()
        self.assertEqual(inline.course(rep), self.course.nom)
        self.assertEqual(inline.equipe_numero(rep), self.e1.numero)
        self.assertEqual(inline.equipe_nom(rep), self.e1.nom)
        self.assertEqual(inline.prix(rep), self.e1.prix)

    def test_total_view_returns_json_totals(self):
        # BUG suspecté : PaiementAdmin.total utilise `course.paiements` (inexistant
        # sur Course), `filter(**request.GET)` (listes), la clé 'monntant_frais'
        # (faute de frappe) et passe `obj.montant_frais` à montant_frais2 (qui
        # attend l'objet). La vue ne peut pas fonctionner.
        make_paiement([(self.e1, '50.00')])
        make_paiement([(self.e2, '30.00')], type='virement')
        r = self.client.get('/course/inscriptions/paiement/total/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decimal(str(json.loads(r.content)['montant'])), Decimal('80.00'))


class EquipeDoPaiementActionTestCase(PaiementChangeBaseTestCase):
    def test_action_redirects_to_add_with_selected_teams(self):
        admin = course_site._registry[self.e1.__class__]
        from inscriptions.models import Equipe
        qs = Equipe.objects.filter(id__in=[self.e1.id, self.e2.id]).order_by('id')
        r = admin.do_paiement(None, qs)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            r['Location'],
            '../paiement/add/?equipe_id=%d&equipe_id=%d' % (self.e1.id, self.e2.id),
        )

    def test_action_through_changelist(self):
        r = self.client.post('/course/inscriptions/equipe/', {
            'action': 'do_paiement',
            '_selected_action': [self.e1.id],
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn('paiement/add/?equipe_id=%d' % self.e1.id, r['Location'])

    def test_action_registered(self):
        self.assertIn('do_paiement', EquipeAdmin.actions)
