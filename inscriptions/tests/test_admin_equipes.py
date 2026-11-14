"""Tests du backoffice équipes (`EquipeAdmin`), des mails (`TemplateMail`, `Mail`,
`utils.send_mail`, `MailConsumer`, `tracking_middleware`) et de l'isolation par
course / accréditations (`CourseFilteredObjectAdmin`, `course_choose`,
`course_ask_accreditation`, cookie `course_uid`).

Aucun envoi réel : `inscriptions.models.send_mail` / `admin_course.send_mail` sont
mockés, et le consumer utilise le backend mail `locmem` de Django (`mail.outbox`).
"""
import json
import unittest
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail as django_mail
from django.test import RequestFactory
from django.urls import reverse

from inscriptions import utils
from inscriptions.admin_course import (
    CategorieFilter, EquipeAdmin, MineurFilter, PaiementCompletFilter, StatusFilter,
    site as course_site,
)
from inscriptions.consumers import MailConsumer
from inscriptions.factories import CategorieFactory, CourseFactory, EquipeFactory, EquipierFactory
from inscriptions.middleware import tracking_middleware
from inscriptions.models import (
    Accreditation, Equipe, Equipier, Mail, Paiement, PaiementRepartition, TemplateMail,
)
from inscriptions.tests.base import BaseTestCase

CHANGELIST = '/course/inscriptions/equipe/'


def login_organizer(client, course, role='admin', username=None):
    user = User.objects.create_user(
        username or 'org%d' % course.id, '%s@example.com' % (username or course.id), 'pass1234',
    )
    Accreditation.objects.create(user=user, course=course.course, role=role)
    client.force_login(user)
    set_course_cookie(client, course)
    return user


def set_course_cookie(client, course):
    client.cookies['course_uid'] = course.key
    client.cookies['course_id'] = str(course.id)


def make_superuser(client, course):
    user = User.objects.create_superuser('root', 'root@example.com', 'pass1234')
    client.force_login(user)
    set_course_cookie(client, course)
    return user


def pay(equipe, montant, type='chèque'):
    p = Paiement.objects.create(type=type, montant=Decimal(montant))
    PaiementRepartition.objects.create(paiement=p, equipe=equipe, montant=Decimal(montant))
    return p


def set_flags(equipe, **flags):
    """Force les drapeaux calculés des équipiers (verifier/valide/erreur)."""
    Equipier.objects.filter(equipe=equipe).update(**flags)


class FakeLayer:
    """Faux channel layer : enregistre les messages envoyés (pas de redis)."""
    def __init__(self):
        self.sent = []

    async def send(self, channel, message):
        self.sent.append((channel, message))


def changelist_ids(response):
    return {e.id for e in response.context['cl'].queryset}


class AdminTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.cat = CategorieFactory(course=self.course, code='SOLO')
        self.other_course = CourseFactory()
        self.other_cat = CategorieFactory(course=self.other_course, code='OTHER')
        self.user = login_organizer(self.client, self.course)

    def equipe(self, **kw):
        kw.setdefault('course', self.course)
        kw.setdefault('categorie', self.cat)
        e = EquipeFactory(**kw)
        if not e.equipier_set.exists():
            EquipierFactory(equipe=e, numero=1)
        return e

    def ids_for(self, **params):
        r = self.client.get(CHANGELIST, params)
        self.assertEqual(r.status_code, 200)
        return changelist_ids(r)


class IsolationTestCase(AdminTestCase):
    def test_changelist_only_shows_teams_of_cookie_course(self):
        mine = self.equipe()
        theirs = self.equipe(course=self.other_course, categorie=self.other_cat)
        ids = self.ids_for()
        self.assertIn(mine.id, ids)
        self.assertNotIn(theirs.id, ids)

    def test_cookie_for_unaccredited_course_is_denied(self):
        theirs = self.equipe(course=self.other_course, categorie=self.other_cat)
        set_course_cookie(self.client, self.other_course)
        r = self.client.get(CHANGELIST)
        # has_permission refuse : redirection vers le login admin, pas de liste
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('cl', getattr(r, 'context_data', None) or {})
        self.assertIsNotNone(theirs)

    def test_no_course_cookie_is_denied(self):
        self.client.cookies.pop('course_uid')
        r = self.client.get(CHANGELIST)
        self.assertEqual(r.status_code, 302)

    def test_pending_accreditation_without_role_is_denied(self):
        Accreditation.objects.filter(user=self.user).update(role='')
        r = self.client.get(CHANGELIST)
        self.assertEqual(r.status_code, 302)

    def test_anonymous_is_redirected(self):
        self.client.logout()
        r = self.client.get(CHANGELIST)
        self.assertEqual(r.status_code, 302)

    def test_superuser_sees_cookie_course_even_without_accreditation(self):
        e = self.equipe(course=self.other_course, categorie=self.other_cat)
        make_superuser(self.client, self.other_course)
        self.assertIn(e.id, self.ids_for())

    def test_two_accreditations_switching_cookie_switches_scope(self):
        Accreditation.objects.create(user=self.user, course=self.other_course.course, role='admin')
        mine = self.equipe()
        theirs = self.equipe(course=self.other_course, categorie=self.other_cat)
        self.assertEqual(self.ids_for() & {mine.id, theirs.id}, {mine.id})
        set_course_cookie(self.client, self.other_course)
        self.assertEqual(self.ids_for() & {mine.id, theirs.id}, {theirs.id})

    def test_get_queryset_filters_by_accreditation_for_non_superuser(self):
        # Même avec un cookie valide, un utilisateur sans accréditation n'obtient rien.
        stranger = User.objects.create_user('stranger', 's@example.com', 'x')
        e = self.equipe()
        request = RequestFactory().get(CHANGELIST)
        request.COOKIES['course_uid'] = self.course.key
        request.user = stranger
        qs = EquipeAdmin(Equipe, course_site).get_queryset(request)
        self.assertNotIn(e.id, [x.id for x in qs])
        request.user = self.user
        qs = EquipeAdmin(Equipe, course_site).get_queryset(request)
        self.assertIn(e.id, [x.id for x in qs])

    def test_has_add_permission_is_false(self):
        request = RequestFactory().get(CHANGELIST)
        request.user = self.user
        self.assertFalse(EquipeAdmin(Equipe, course_site).has_add_permission(request))
        self.assertEqual(self.client.get(CHANGELIST + 'add/').status_code, 403)

    def test_change_page_of_other_course_team_is_not_found(self):
        theirs = self.equipe(course=self.other_course, categorie=self.other_cat)
        r = self.client.get('%s%d/change/' % (CHANGELIST, theirs.id))
        self.assertIn(r.status_code, (302, 404))

    def test_change_page_of_own_team_ok(self):
        mine = self.equipe()
        r = self.client.get('%s%d/change/' % (CHANGELIST, mine.id))
        self.assertEqual(r.status_code, 200)

    def test_send_mail_view_refuses_team_of_other_course(self):
        """Un organisateur ne doit pas pouvoir préparer un mail pour une équipe d'une autre course."""
        theirs = self.equipe(course=self.other_course, categorie=self.other_cat)
        t = TemplateMail.objects.create(course=self.course, nom='x', sujet='s', message='m')
        r = self.client.get('%s%d/send/%d/' % (CHANGELIST, theirs.id, t.id))
        self.assertIn(r.status_code, (302, 403, 404))

    def test_preview_mail_refuses_team_of_other_course(self):
        theirs = self.equipe(course=self.other_course, categorie=self.other_cat)
        t = TemplateMail.objects.create(course=self.course, nom='x', sujet='s', message='m')
        r = self.client.get(CHANGELIST + 'send/preview/', {'id': theirs.id, 'template': t.id})
        self.assertIn(r.status_code, (302, 403, 404))

    def test_send_mails_does_not_mail_teams_of_other_course(self):
        t = TemplateMail.objects.create(course=self.course, nom='x', sujet='s', message='m')
        theirs = self.equipe(course=self.other_course, categorie=self.other_cat)
        with mock.patch('inscriptions.models.send_mail') as sm:
            self.client.post(CHANGELIST + 'send/', {'template': t.id, 'ids': json.dumps([theirs.id])})
        self.assertEqual(sm.call_count, 0)

    def test_template_mail_of_other_course_cannot_be_used(self):
        mine = self.equipe()
        foreign = TemplateMail.objects.create(course=self.other_course, nom='f',
                                              sujet='s', message='m')
        with mock.patch('inscriptions.models.send_mail') as sm:
            self.client.post(CHANGELIST + 'send/', {'template': foreign.id, 'ids': json.dumps([mine.id])})
        self.assertEqual(sm.call_count, 0)


class CourseChooseAskTestCase(AdminTestCase):
    def test_course_choose_lists_only_accredited_courses(self):
        r = self.client.get('/course/choose/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(r.context['courses']), [self.course])
        self.assertIsNone(r.context['courses_admin'])

    def test_course_choose_superuser_sees_other_courses_as_admin(self):
        make_superuser(self.client, self.course)
        r = self.client.get('/course/choose/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.other_course, list(r.context['courses_admin']))

    def test_course_choose_hides_old_courses_unless_old(self):
        old = CourseFactory(date=date(2000, 1, 1))
        Accreditation.objects.create(user=self.user, course=old.course, role='admin')
        r = self.client.get('/course/choose/')
        self.assertNotIn(old, list(r.context['courses']))
        r = self.client.get('/course/choose/', {'old': ''})
        self.assertIn(old, list(r.context['courses']))

    def test_course_setter_sets_cookies(self):
        self.client.cookies.clear()
        r = self.client.get('/%s/admin/' % self.course.key)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.cookies['course_uid'].value, self.course.key)
        self.assertEqual(r.cookies['course_id'].value, str(self.course.id))

    def test_ask_list_excludes_already_requested_courses(self):
        r = self.client.get('/course/ask/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.course, list(r.context['courses']))
        self.assertIn(self.other_course, list(r.context['courses']))

    def test_ask_creates_pending_accreditation_and_notifies_organizer(self):
        with mock.patch('inscriptions.admin_course.send_mail') as sm:
            r = self.client.get('/course/ask/%s/' % self.other_course.key)
        self.assertEqual(r.status_code, 302)
        acc = Accreditation.objects.get(user=self.user, course=self.other_course.course)
        self.assertEqual(acc.role, '')
        sm.assert_called_once()
        self.assertEqual(sm.call_args[1]['to'], [self.other_course.email_contact])

    def test_pending_accreditation_still_does_not_grant_access(self):
        with mock.patch('inscriptions.admin_course.send_mail'):
            self.client.get('/course/ask/%s/' % self.other_course.key)
        e = self.equipe(course=self.other_course, categorie=self.other_cat)
        set_course_cookie(self.client, self.other_course)
        r = self.client.get(CHANGELIST)
        self.assertEqual(r.status_code, 302)
        self.assertIsNotNone(e)

    def test_ask_unknown_course_is_404(self):
        r = self.client.get('/course/ask/nope/')
        self.assertEqual(r.status_code, 404)

    def test_demandes_listed_in_ask_page(self):
        with mock.patch('inscriptions.admin_course.send_mail'):
            self.client.get('/course/ask/%s/' % self.other_course.key)
        r = self.client.get('/course/ask/')
        self.assertIn(self.other_course, list(r.context['demandes']))

    def test_ask_twice_for_same_course_is_handled(self):
        """unique_together(user, course) : une seconde demande ne doit pas provoquer de 500."""
        with mock.patch('inscriptions.admin_course.send_mail'):
            self.client.get('/course/ask/%s/' % self.other_course.key)
            r = self.client.get('/course/ask/%s/' % self.other_course.key)
        self.assertLess(r.status_code, 500)

    def test_accreditation_granted_sends_mail_to_user(self):
        with mock.patch('inscriptions.admin_course.send_mail'):
            self.client.get('/course/ask/%s/' % self.other_course.key)
        acc = Accreditation.objects.get(user=self.user, course=self.other_course.course)
        with mock.patch('inscriptions.models.send_mail') as sm:
            acc.role = 'admin'
            acc.save()
        sm.assert_called_once()
        self.assertEqual(sm.call_args[1]['to'], [self.user.email])
        # une seconde sauvegarde ne renvoie pas de mail
        with mock.patch('inscriptions.models.send_mail') as sm:
            acc.save()
        self.assertEqual(sm.call_count, 0)


class FiltersTestCase(AdminTestCase):
    def test_status_filter(self):
        a_verifier = self.equipe()
        set_flags(a_verifier, verifier=True)
        erreur = self.equipe()
        set_flags(erreur, erreur=True)
        complet = self.equipe()
        set_flags(complet, valide=True)
        incomplet = self.equipe()
        set_flags(incomplet, valide=False, verifier=False, erreur=False)
        mine = {a_verifier.id, erreur.id, complet.id, incomplet.id}
        self.assertEqual(self.ids_for(status='verifier') & mine, {a_verifier.id})
        self.assertEqual(self.ids_for(status='erreur') & mine, {erreur.id})
        self.assertEqual(self.ids_for(status='complet') & mine, {complet.id})
        self.assertEqual(self.ids_for(status='incomplet') & mine, {incomplet.id})
        self.assertEqual(self.ids_for() & mine, mine)

    def test_status_verifier_takes_precedence_over_erreur(self):
        e = self.equipe()
        set_flags(e, verifier=True, erreur=True)
        self.assertIn(e.id, self.ids_for(status='verifier'))
        self.assertNotIn(e.id, self.ids_for(status='erreur'))

    def test_lock_filter(self):
        locked = self.equipe(verrou=True)
        free = self.equipe(verrou=False)
        ids = self.ids_for(verrou__exact='1')
        self.assertIn(locked.id, ids)
        self.assertNotIn(free.id, ids)

    def test_categorie_filter_and_lookups_are_scoped_to_course(self):
        solo = self.equipe()
        other_cat = CategorieFactory(course=self.course, code='DUO')
        duo = self.equipe(categorie=other_cat)
        self.assertEqual(self.ids_for(categorie='DUO') & {solo.id, duo.id}, {duo.id})
        request = RequestFactory().get(CHANGELIST)
        request.COOKIES['course_uid'] = self.course.key
        f = CategorieFilter(request, {}, Equipe, EquipeAdmin(Equipe, course_site))
        codes = [code for code, label in f.lookup_choices]
        self.assertIn('SOLO', codes)
        self.assertIn('DUO', codes)
        self.assertNotIn('OTHER', codes)

    def test_mineur_filter(self):
        # date de course = aujourd'hui + 60j ; mineur = né après (date - 18 ans)
        year = self.course.date.year
        minor_team = self.equipe()
        Equipier.objects.filter(equipe=minor_team).update(date_de_naissance=date(year - 10, 1, 1))
        adult_team = self.equipe()
        Equipier.objects.filter(equipe=adult_team).update(date_de_naissance=date(year - 40, 1, 1))
        both = {minor_team.id, adult_team.id}
        self.assertEqual(self.ids_for(mineurs='1') & both, {minor_team.id})
        self.assertEqual(self.ids_for(mineurs='0') & both, {adult_team.id})
        self.assertEqual(self.ids_for() & both, both)

    def test_mineur_filter_class_directly(self):
        self.assertEqual({v for v, _l in MineurFilter(
            RequestFactory().get('/'), {}, Equipe, EquipeAdmin(Equipe, course_site)).lookup_choices},
            {'0', '1'})

    def test_paiement_filters(self):
        impaye = self.equipe(prix=Decimal('40.00'))
        partiel = self.equipe(prix=Decimal('40.00'))
        pay(partiel, '10.00')
        exact = self.equipe(prix=Decimal('40.00'))
        pay(exact, '40.00')
        trop = self.equipe(prix=Decimal('40.00'))
        pay(trop, '50.00')
        offert = self.equipe(prix=Decimal('40.00'))
        pay(offert, '0.00', type='offert')
        mine = {impaye.id, partiel.id, exact.id, trop.id, offert.id}

        def f(v):
            return self.ids_for(paiement=v) & mine
        self.assertEqual(f('impaye'), {impaye.id})
        self.assertEqual(f('partiel'), {partiel.id})
        self.assertEqual(f('exact'), {exact.id, offert.id})  # offert : 0 payé == 0 dû
        self.assertEqual(f('trop'), {trop.id})
        self.assertEqual(f('offert'), {offert.id})
        self.assertEqual(f('complet'), {exact.id, trop.id, offert.id})
        self.assertEqual(f('incomplet'), {impaye.id, partiel.id})

    def test_paiement_filter_does_not_leak_other_course(self):
        theirs = self.equipe(course=self.other_course, categorie=self.other_cat)
        self.assertNotIn(theirs.id, self.ids_for(paiement='impaye'))

    def test_filter_classes_expose_expected_parameters(self):
        self.assertEqual(StatusFilter.parameter_name, 'status')
        self.assertEqual(PaiementCompletFilter.parameter_name, 'paiement')


class ActionsTestCase(AdminTestCase):
    def action(self, name, equipes, **extra):
        data = {'action': name, '_selected_action': [e.id for e in equipes]}
        data.update(extra)
        return self.client.post(CHANGELIST, data, **extra.pop('headers', {}))

    def test_lock_and_unlock(self):
        e1, e2 = self.equipe(), self.equipe()
        r = self.client.post(CHANGELIST, {'action': 'lock', '_selected_action': [e1.id]},
                             HTTP_REFERER=CHANGELIST)
        self.assertEqual(r.status_code, 302)
        e1.refresh_from_db(); e2.refresh_from_db()
        self.assertTrue(e1.verrou)
        self.assertFalse(e2.verrou)
        self.client.post(CHANGELIST, {'action': 'unlock', '_selected_action': [e1.id]},
                         HTTP_REFERER=CHANGELIST)
        e1.refresh_from_db()
        self.assertFalse(e1.verrou)

    def test_lock_cannot_touch_other_course(self):
        theirs = self.equipe(course=self.other_course, categorie=self.other_cat)
        self.client.post(CHANGELIST, {'action': 'lock', '_selected_action': [theirs.id]},
                         HTTP_REFERER=CHANGELIST)
        theirs.refresh_from_db()
        self.assertFalse(theirs.verrou)

    def test_do_paiement_redirects_with_equipe_ids(self):
        e1, e2 = self.equipe(), self.equipe()
        r = self.client.post(CHANGELIST, {'action': 'do_paiement',
                                          '_selected_action': [e1.id, e2.id]})
        self.assertEqual(r.status_code, 302)
        self.assertIn('../paiement/add/?', r['Location'])
        self.assertIn('equipe_id=%d' % e1.id, r['Location'])
        self.assertIn('equipe_id=%d' % e2.id, r['Location'])

    def test_send_mails_action_shows_form_with_course_templates_only(self):
        e = self.equipe()
        mine = TemplateMail.objects.create(course=self.course, nom='a', sujet='s', message='m')
        TemplateMail.objects.create(course=self.other_course, nom='b', sujet='s', message='m')
        r = self.client.post(CHANGELIST, {'action': 'send_mails', '_selected_action': [e.id]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(r.context['templates']), [mine])

    def test_send_mails_post_creates_mails_and_redirects(self):
        e1, e2 = self.equipe(), self.equipe()
        t = TemplateMail.objects.create(course=self.course, nom='a', sujet='Bonjour {{ instance.nom }}', message='<p>msg</p>')
        with mock.patch('inscriptions.models.send_mail') as sm:
            r = self.client.post(CHANGELIST + 'send/', {'template': t.id,
                                                        'ids': json.dumps([e1.id, e2.id])})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Mail.objects.filter(template=t).count(), 2)
        self.assertEqual(sm.call_count, 2)

    def test_send_mails_unknown_template_is_404(self):
        e = self.equipe()
        r = self.client.post(CHANGELIST + 'send/', {'template': 99999, 'ids': json.dumps([e.id])})
        self.assertEqual(r.status_code, 404)

    def test_export_form_then_csv(self):
        e = self.equipe(nom='Les Rapides')
        r = self.client.post(CHANGELIST, {'action': 'export', '_selected_action': [e.id]})
        self.assertEqual(r.status_code, 200)
        self.assertIn('equipe.nom', r.context['fields'])
        r = self.client.post(CHANGELIST + 'export/', {
            'ids': json.dumps([e.id]), 'objet': 'equipes', 'name': 'out',
            'colonnes': ['equipe.nom', 'categorie.code'],
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'].split(';')[0], 'text/csv')
        lines = r.content.decode('utf-8').strip().splitlines()
        self.assertEqual(lines[1], 'Les Rapides;SOLO')

    def test_export_csv_never_contains_other_course_teams(self):
        mine = self.equipe(nom='Mine')
        self.equipe(nom='Theirs', course=self.other_course, categorie=self.other_cat)
        r = self.client.post(CHANGELIST + 'export/', {
            'ids': json.dumps([]), 'objet': 'equipes', 'colonnes': ['equipe.nom'],
        })
        body = r.content.decode('utf-8')
        self.assertIn(mine.nom, body)
        self.assertNotIn('Theirs', body)

    def test_export_equipiers_csv(self):
        e = self.equipe()
        r = self.client.post(CHANGELIST + 'export/', {
            'ids': json.dumps([e.id]), 'objet': 'equipiers', 'colonnes': ['equipier.prenom', 'equipe.nom'],
        })
        lines = r.content.decode('utf-8').strip().splitlines()
        self.assertEqual(lines[1], 'Jean;%s' % e.nom)

    def test_export_equipiers_ignores_other_course_ids(self):
        theirs = self.equipe(nom='Theirs', course=self.other_course, categorie=self.other_cat)
        r = self.client.post(CHANGELIST + 'export/', {
            'ids': json.dumps([theirs.id]), 'objet': 'equipes', 'colonnes': ['equipe.nom'],
        })
        self.assertNotIn('Theirs', r.content.decode('utf-8'))

    def test_download_zip_contains_only_own_course_files(self):
        import tempfile, os
        from django.core.files.uploadedfile import SimpleUploadedFile
        mine = self.equipe()
        Equipier.objects.filter(equipe=mine).delete()
        eq = EquipierFactory(equipe=mine, numero=1,
                             piece_jointe=SimpleUploadedFile('c.pdf', b'PDFDATA'))
        theirs = self.equipe(course=self.other_course, categorie=self.other_cat)
        Equipier.objects.filter(equipe=theirs).delete()
        EquipierFactory(equipe=theirs, numero=1,
                        piece_jointe=SimpleUploadedFile('d.pdf', b'SECRET'))
        r = self.client.post(CHANGELIST, {'action': 'download',
                                          '_selected_action': [mine.id, theirs.id]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/zip')
        self.assertIn('.zip', r['Content-Disposition'])
        data = b''.join(r.streaming_content)
        import io, zipfile
        names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        self.assertEqual(len(names), 1)
        self.assertIn(mine.nom, names[0])
        self.assertIsNotNone(eq)
        self.assertIsNotNone(os)
        self.assertIsNotNone(tempfile)


class SendMailViewTestCase(AdminTestCase):
    def setUp(self):
        super().setUp()
        self.e = self.equipe(nom='Les Rapides', gerant_email='chef@example.com')
        self.t = TemplateMail.objects.create(
            course=self.course, nom='bienvenue', sujet='Salut {{ instance.nom }}', message='<p>Equipe {{ instance.nom }} {{ ROOT_URL }}</p>',
        )

    def test_get_renders_template_in_form(self):
        r = self.client.get('%s%d/send/%d/' % (CHANGELIST, self.e.id, self.t.id))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['subject'], 'Salut Les Rapides')
        self.assertIn('Equipe Les Rapides', r.context['message'])
        self.assertIn('https://', r.context['message'])
        self.assertEqual(r.context['mail'], 'chef@example.com')
        self.assertEqual(r.context['sender'], self.course.email_contact)

    def test_get_with_broken_template_shows_error_instead_of_crashing(self):
        self.t.message = '{% nonexistenttag %}'
        self.t.save()
        r = self.client.get('%s%d/send/%d/' % (CHANGELIST, self.e.id, self.t.id))
        self.assertEqual(r.status_code, 200)
        self.assertIn('Error in template', r.context['message'])

    def test_get_unknown_template_is_404(self):
        r = self.client.get('%s%d/send/99999/' % (CHANGELIST, self.e.id))
        self.assertEqual(r.status_code, 404)

    def test_post_creates_mail_and_dispatches(self):
        with mock.patch('inscriptions.models.send_mail') as sm:
            r = self.client.post('%s%d/send/%d/' % (CHANGELIST, self.e.id, self.t.id), {
                'sender': 'orga@example.com', 'mail': 'dest@example.com',
                'subject': 'Sujet', 'message': 'Corps',
            })
        self.assertEqual(r.status_code, 302)
        m = Mail.objects.get(equipe=self.e)
        self.assertEqual(m.destinataires, ['dest@example.com'])
        self.assertEqual(m.emetteur, 'orga@example.com')
        self.assertEqual(m.sujet, 'Sujet')
        self.assertEqual(m.course, self.course)
        self.assertIsNone(m.template)
        self.assertTrue(m.uid)
        sm.assert_called_once()
        kw = sm.call_args[1]
        self.assertEqual(kw['to'], ['dest@example.com'])
        self.assertEqual(kw['reply_to'], ['orga@example.com'])
        self.assertEqual(kw['message_id'], m.uid)
        self.assertEqual(kw['name'], self.course.nom)

    def test_preview_mail_returns_json(self):
        r = self.client.get(CHANGELIST + 'send/preview/', {'id': self.e.id, 'template': self.t.id})
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data['mail'], 'chef@example.com')
        self.assertEqual(data['subject'], 'Salut Les Rapides')
        self.assertIn('Les Rapides', data['message'])

    def test_preview_mail_with_broken_template(self):
        self.t.sujet = '{% if %}'
        self.t.save()
        r = self.client.get(CHANGELIST + 'send/preview/', {'id': self.e.id, 'template': self.t.id})
        self.assertIn('Error in template', json.loads(r.content)['message'])

    def test_preview_mail_unknown_ids_404(self):
        r = self.client.get(CHANGELIST + 'send/preview/', {'id': 99999, 'template': self.t.id})
        self.assertEqual(r.status_code, 404)
        r = self.client.get(CHANGELIST + 'send/preview/', {'id': self.e.id, 'template': 99999})
        self.assertEqual(r.status_code, 404)

    def test_autre_page_lists_course_templates_and_mail_errors(self):
        Mail.objects.create(course=self.course, equipe=self.e, emetteur='a@example.com',
                            destinataires=['b@example.com'], bcc=[], sujet='x', message='y',
                            uid='u1', error='boom')
        r = self.client.get('%s%d/autre/' % (CHANGELIST, self.e.id))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['mail_error'], 1)
        self.assertEqual(list(r.context['templates']), [self.t])


class TemplateMailTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory(email_contact='orga@example.com')
        self.cat = CategorieFactory(course=self.course, max_equipiers=2)
        self.equipe = EquipeFactory(course=self.course, categorie=self.cat, nombre=2,
                                    nom='Les Rapides', gerant_email='chef@example.com')
        EquipierFactory(equipe=self.equipe, numero=1)
        EquipierFactory(equipe=self.equipe, numero=2)

    def make(self, nom, **kw):
        kw.setdefault('sujet', 'Bonjour {{ instance.nom }}')
        kw.setdefault('message', '<p>{{ instance.nom }} {{ ROOT_URL }}</p>')
        return TemplateMail.objects.create(course=self.course, nom='t-' + nom, **kw)

    def test_send_to_equipe_creates_mail_and_dispatches(self):
        t = self.make('Equipe', bcc='a@example.com, b@example.com;c@example.com')
        with mock.patch('inscriptions.models.send_mail') as sm:
            t.send([self.equipe])
        m = Mail.objects.get()
        self.assertEqual(m.destinataires, ['chef@example.com'])
        self.assertEqual(m.bcc, ['a@example.com', 'b@example.com', 'c@example.com'])
        self.assertEqual(m.sujet, 'Bonjour Les Rapides')
        self.assertIn('Les Rapides', m.message)
        self.assertIn('https://', m.message)
        self.assertEqual(m.emetteur, 'orga@example.com')
        self.assertEqual(m.template, t)
        self.assertEqual(m.equipe, self.equipe)
        self.assertTrue(m.uid.endswith('@' + 'example.com'))
        sm.assert_called_once()
        self.assertEqual(sm.call_args[1]['message_id'], m.uid)
        self.assertEqual(sm.call_args[1]['bcc'], m.bcc)

    def test_send_accepts_queryset(self):
        t = self.make('Equipe')
        e2 = EquipeFactory(course=self.course, categorie=self.cat, gerant_email='autre@example.com')
        with mock.patch('inscriptions.models.send_mail'):
            t.send(Equipe.objects.filter(course=self.course))
        self.assertEqual(Mail.objects.count(), 2)
        self.assertEqual({m.equipe_id for m in Mail.objects.all()}, {self.equipe.id, e2.id})

    def test_one_mail_row_but_one_dispatch_per_recipient(self):
        t = self.make('Equipe')
        with mock.patch('inscriptions.models.send_mail') as sm:
            t.send([self.equipe])
            m = Mail.objects.get()
            m.destinataires = ['x@example.com', 'y@example.com']
            m.send()
        self.assertEqual(sm.call_count, 3)

    def test_mail_send_generates_uid_only_once(self):
        m = Mail.objects.create(course=self.course, emetteur='a@example.com',
                                destinataires=['b@example.com'], bcc=[], sujet='s', message='m')
        with mock.patch('inscriptions.models.send_mail'):
            m.send()
            uid = m.uid
            m.send()
        self.assertTrue(uid)
        self.assertEqual(m.uid, uid)
        self.assertEqual(Mail.objects.get().uid, uid)

    def test_template_unique_per_course(self):
        from django.db import IntegrityError, transaction
        self.make('Equipe')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make('Equipe')

    def test_str(self):
        self.assertEqual(str(self.make('Equipe')), 't-Equipe')

    def test_course_models_only_use_existing_templatemail_fields(self):
        """course_models.json alimente TemplateMail(**item) a la creation d'une course."""
        from django.conf import settings
        fields = {f.name for f in TemplateMail._meta.get_fields()}
        for uid, model in settings.MODELS_COURSES.items():
            names = [t['nom'] for t in model['templatemail_set']]
            self.assertFalse([n for n in names if n.endswith('_admin')], uid)
            for item in model['templatemail_set']:
                self.assertLessEqual(set(item), fields, uid)


class EquipeSendAdminMailTestCase(BaseTestCase):
    """Notifications organisateur : template HTML rendu directement, sans TemplateMail."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory(uid='adm', email_contact='orga@example.com')
        self.cat = CategorieFactory(course=self.course, code='SOLO')
        self.equipe = EquipeFactory(course=self.course, categorie=self.cat, nom='Les Rapides',
                                    gerant_email='chef@example.com')
        EquipierFactory(equipe=self.equipe, numero=1)

    def test_inscription_admin_goes_to_the_organizer_without_any_templatemail(self):
        self.assertFalse(TemplateMail.objects.exists())
        with mock.patch('inscriptions.models.send_mail') as sm:
            self.equipe.send_admin_mail('inscription_admin')
        m = Mail.objects.get()
        self.assertEqual(m.destinataires, ['orga@example.com'])
        self.assertEqual(m.emetteur, 'orga@example.com')
        self.assertIsNone(m.template)
        self.assertEqual(m.equipe, self.equipe)
        self.assertEqual(m.sujet, '[adm] %s - %s - Les Rapides' % (self.cat, self.equipe.numero))
        self.assertIn('Les Rapides', m.message)
        self.assertEqual(sm.call_args[1]['to'], ['orga@example.com'])

    def test_subject_is_not_html_escaped(self):
        self.equipe.nom = 'Dupont & Fils'
        with mock.patch('inscriptions.models.send_mail'):
            self.equipe.send_admin_mail('inscription_admin')
        self.assertTrue(Mail.objects.get().sujet.endswith('Dupont & Fils'))

    def test_changement_numero_admin_template_is_rendered(self):
        with mock.patch('inscriptions.models.send_mail'):
            self.equipe.send_admin_mail('changement_numero_admin')
        self.assertIn('Changement de num', Mail.objects.get().message)

    def test_public_registration_notifies_the_organizer(self):
        from inscriptions.tests.base import equipe_form_data, equipier_formset_data
        course = CourseFactory(uid='reg', email_contact='orga2@example.com')
        categorie = CategorieFactory(course=course, min_equipiers=1, max_equipiers=1, min_age=0,
                                     numero_debut=1, numero_fin=99)
        data = equipe_form_data(categorie=categorie.id, nombre='1')
        data.update(equipier_formset_data([{
            'nom': 'Martin', 'prenom': 'Luc', 'sexe': 'H', 'justificatif': 'certificat',
            'date_de_naissance': date(1990, 1, 1)}]))
        with mock.patch('inscriptions.models.send_mail'):
            self.client.post('/reg/reg/', data)
        self.assertEqual(Mail.objects.filter(destinataires=['orga2@example.com']).count(), 1)


class UtilsSendMailTestCase(BaseTestCase):
    def test_send_mail_posts_on_mail_channel_with_generated_message_id(self):
        layer = FakeLayer()
        with mock.patch('inscriptions.utils.get_channel_layer', return_value=layer):
            utils.send_mail(subject='S', body='B', to=['a@example.com'])
        self.assertEqual(len(layer.sent), 1)
        channel, message = layer.sent[0]
        self.assertEqual(channel, 'mail')
        self.assertEqual(message['type'], 'send.mail')
        self.assertEqual(message['subject'], 'S')
        self.assertEqual(message['to'], ['a@example.com'])
        self.assertRegex(message['message_id'], r'^[0-9a-f]{32}@example\.com$')

    def test_send_mail_keeps_explicit_message_id(self):
        layer = FakeLayer()
        with mock.patch('inscriptions.utils.get_channel_layer', return_value=layer):
            utils.send_mail(subject='S', body='B', to=['a@example.com'], message_id='fixed@x')
        self.assertEqual(layer.sent[-1][1]['message_id'], 'fixed@x')

    def test_send_mail_unique_ids(self):
        layer = FakeLayer()
        with mock.patch('inscriptions.utils.get_channel_layer', return_value=layer):
            utils.send_mail(subject='S', body='B', to=['a@example.com'])
            utils.send_mail(subject='S', body='B', to=['a@example.com'])
        ids = [c[1]['message_id'] for c in layer.sent]
        self.assertEqual(len(set(ids)), 2)


class MailConsumerTestCase(BaseTestCase):
    def payload(self, **kw):
        msg = {
            'type': 'send.mail', 'subject': 'Sujet', 'body': '<p>Salut</p>',
            'to': ['dest@example.com'], 'message_id': 'abc123@example.com',
            'name': 'Ma Course', 'reply_to': ['orga@example.com'], 'bcc': ['c@example.com'],
        }
        msg.update(kw)
        return msg

    def consume(self, message):
        MailConsumer().send_mail(message)

    def setUp(self):
        super().setUp()
        django_mail.outbox = []

    def test_html_mail_is_sent_with_headers_and_tracking_pixel(self):
        self.consume(self.payload())
        self.assertEqual(len(django_mail.outbox), 1)
        m = django_mail.outbox[0]
        self.assertEqual(m.subject, 'Sujet')
        self.assertEqual(m.to, ['dest@example.com'])
        self.assertEqual(m.bcc, ['c@example.com'])
        self.assertEqual(m.reply_to, ['orga@example.com'])
        self.assertEqual(m.content_subtype, 'html')
        self.assertTrue(m.from_email.startswith('Ma Course <'))
        self.assertEqual(m.extra_headers['Message-ID'], 'abc123@example.com')
        self.assertIn('<img src="https://example.com/blank.gif?message_id=abc123@example.com"', m.body)

    def test_internal_links_get_message_id_appended(self):
        body = '<a href="https://example.com/course1/12/abc/">x</a> <a href="https://other.org/p">y</a>'
        self.consume(self.payload(body=body))
        sent = django_mail.outbox[0].body
        self.assertIn('https://example.com/course1/12/abc/?&message_id=abc123@example.com', sent)
        self.assertIn('https://other.org/p"', sent)
        self.assertNotIn('other.org/p?', sent)

    def test_link_with_query_and_fragment_is_preserved(self):
        body = '<a href="https://example.com/p?a=1#frag">x</a>'
        self.consume(self.payload(body=body))
        self.assertIn('https://example.com/p?a=1&message_id=abc123@example.com#frag',
                      django_mail.outbox[0].body)

    def test_text_mail_has_no_tracking(self):
        self.consume(self.payload(content_type='text', body='Bonjour https://example.com/x'))
        m = django_mail.outbox[0]
        self.assertEqual(m.content_subtype, 'text')
        self.assertNotIn('blank.gif', m.body)
        self.assertNotIn('message_id=', m.body)

    def test_default_sender_name(self):
        msg = self.payload()
        msg.pop('name')
        self.consume(msg)
        self.assertTrue(django_mail.outbox[0].from_email.startswith('Enduroller <'))

    def test_smtp_recipients_refused_stores_error_on_mail(self):
        import smtplib
        course = CourseFactory()
        Mail.objects.create(course=course, emetteur='a@example.com',
                            destinataires=['dest@example.com'], bcc=[], sujet='s', message='m',
                            uid='abc123@example.com')
        err = smtplib.SMTPRecipientsRefused({'dest@example.com': (550, b'mailbox unknown')})
        with mock.patch('django.core.mail.EmailMessage.send', side_effect=err), \
                mock.patch('inscriptions.consumers.logger'):
            self.consume(self.payload())
        self.assertIn('mailbox unknown', Mail.objects.get().error)

    def test_unexpected_error_is_swallowed(self):
        with mock.patch('django.core.mail.EmailMessage.send', side_effect=RuntimeError('x')), \
                mock.patch('inscriptions.consumers.logger'):
            self.consume(self.payload())  # ne doit pas lever

    def test_missing_message_id_is_swallowed(self):
        msg = self.payload()
        msg.pop('message_id')
        self.consume(msg)
        self.assertEqual(django_mail.outbox, [])

    def test_end_to_end_mail_model_to_consumer(self):
        """Mail.send() -> utils.send_mail -> canal ; on rejoue le message dans le consumer."""
        course = CourseFactory()
        m = Mail.objects.create(course=course, emetteur='orga@example.com',
                                destinataires=['dest@example.com'], bcc=[],
                                sujet='Sujet', message='<p>x</p>')
        layer = FakeLayer()
        with mock.patch('inscriptions.utils.get_channel_layer', return_value=layer):
            m.send()
        message = layer.sent[-1][1]
        self.consume(dict(message))
        self.assertEqual(len(django_mail.outbox), 1)
        self.assertEqual(django_mail.outbox[0].extra_headers['Message-ID'], m.uid)


class TrackingTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.course = CourseFactory()
        self.mail = Mail.objects.create(course=self.course, emetteur='a@example.com',
                                        destinataires=['b@example.com'], bcc=[], sujet='s',
                                        message='m', uid='trk1@example.com')

    def test_blank_gif_with_message_id_marks_mail_read(self):
        self.assertIsNone(self.mail.read)
        with mock.patch('inscriptions.views.blank', return_value=__import__('django.http', fromlist=['x']).HttpResponse(b'GIF')):
            r = self.client.get('/blank.gif', {'message_id': 'trk1@example.com'})
        self.assertEqual(r.status_code, 200)
        self.mail.refresh_from_db()
        self.assertIsNotNone(self.mail.read)

    def test_any_page_with_message_id_marks_read(self):
        r = self.client.get('/%s/' % self.course.key, {'message_id': 'trk1@example.com'})
        self.assertLess(r.status_code, 500)
        self.mail.refresh_from_db()
        self.assertIsNotNone(self.mail.read)

    def test_first_read_timestamp_is_kept(self):
        get = mock.Mock(return_value='resp')
        mw = tracking_middleware(get)
        req = RequestFactory().get('/x', {'message_id': 'trk1@example.com'})
        self.assertEqual(mw(req), 'resp')
        self.mail.refresh_from_db()
        first = self.mail.read
        self.assertIsNotNone(first)
        mw(req)
        self.mail.refresh_from_db()
        self.assertEqual(self.mail.read, first)

    def test_unknown_message_id_is_harmless_and_other_mails_untouched(self):
        mw = tracking_middleware(lambda r: 'ok')
        self.assertEqual(mw(RequestFactory().get('/x', {'message_id': 'nope'})), 'ok')
        self.mail.refresh_from_db()
        self.assertIsNone(self.mail.read)

    def test_request_without_message_id_does_not_touch_mails(self):
        mw = tracking_middleware(lambda r: 'ok')
        mw(RequestFactory().get('/x'))
        self.mail.refresh_from_db()
        self.assertIsNone(self.mail.read)

    def test_message_id_injected_by_consumer_matches_tracking_lookup(self):
        """Le pixel produit par le consumer porte l'uid que le middleware recherche."""
        django_mail.outbox = []
        MailConsumer().send_mail({
            'type': 'send.mail', 'subject': 's', 'body': '<p>x</p>', 'to': ['b@example.com'],
            'message_id': self.mail.uid,
        })
        body = django_mail.outbox[0].body
        self.assertIn('message_id=%s' % self.mail.uid, body)
        mw = tracking_middleware(lambda r: 'ok')
        mw(RequestFactory().get('/blank.gif', {'message_id': self.mail.uid}))
        self.mail.refresh_from_db()
        self.assertIsNotNone(self.mail.read)
