"""Tests de caracterisation du flux d'authentification (`django-user-accounts`).

Contrairement aux autres tests, aucun `force_login` ici : on passe par les vraies
vues `account.*` (signup, confirmation d'e-mail, login, logout, reset de mot de
passe). Ces tests servent de filet de securite pour la migration Django
(cf. docs/django-upgrade-plan.md) : si `django-user-accounts` est remplace (allauth,
vues Django natives...), ils decrivent le comportement a preserver. Les URLs sont
resolues par nom ; seul le *comportement observable* est verifie.

Le captcha Turnstile fait un appel HTTP : on remplace `TurnstileField.clean`.
"""
import re
from unittest import mock

from account.models import EmailAddress
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from turnstile.fields import TurnstileField

from inscriptions.factories import CourseFactory
from inscriptions.models import Accreditation

PASSWORD = 'Sup3rSecret!'


def captcha_ok():
    return mock.patch.object(TurnstileField, 'clean', return_value='ok')


def make_user(username='alice', email='alice@example.com', password=PASSWORD, verified=True):
    user = User.objects.create_user(username, email, password)
    # un signal de `account` cree deja l'EmailAddress a la creation du User
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={'primary': True, 'verified': verified})
    return user


def link_in(message, path_part):
    match = re.search(r'https?://[^\s"<>]+' + re.escape(path_part) + r'[^\s"<>]*', message.body)
    assert match, 'no %r link in mail body:\n%s' % (path_part, message.body)
    return re.sub(r'^https?://[^/]+', '', match.group(0))


class SignupFlowTestCase(TestCase):
    def signup(self, **kw):
        data = {
            'username': 'nouveau', 'email': 'nouveau@example.com',
            'password': PASSWORD, 'password_confirm': PASSWORD,
        }
        data.update(kw)
        with captcha_ok():
            return self.client.post(reverse('account_signup'), data)

    def test_signup_creates_user_and_unverified_email(self):
        self.signup()
        user = User.objects.get(username='nouveau')
        address = EmailAddress.objects.get(user=user)
        self.assertEqual(address.email, 'nouveau@example.com')
        self.assertTrue(address.primary)
        self.assertFalse(address.verified)

    def test_signup_does_not_log_in_while_confirmation_required(self):
        self.signup()
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_signup_sends_one_confirmation_mail(self):
        self.signup()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['nouveau@example.com'])
        link_in(mail.outbox[0], '/account/confirm_email/')

    def test_signup_gives_default_organizer_permissions(self):
        # receivers.py : post_save sur User -> permissions de gestion de course
        self.signup()
        self.assertTrue(User.objects.get(username='nouveau').user_permissions.exists())

    def test_signup_rejects_duplicate_email(self):
        make_user(username='alice', email='dup@example.com')
        response = self.signup(email='dup@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='nouveau').exists())

    def test_signup_rejects_duplicate_username(self):
        make_user(username='nouveau', email='other@example.com')
        response = self.signup()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username='nouveau').count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_signup_rejects_password_mismatch(self):
        response = self.signup(password_confirm='autre-chose')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='nouveau').exists())

    def test_confirmation_link_verifies_email(self):
        self.signup()
        url = link_in(mail.outbox[0], '/account/confirm_email/')
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.client.post(url)
        self.assertTrue(EmailAddress.objects.get(user__username='nouveau').verified)

    def test_confirmation_with_bad_key_does_not_verify(self):
        self.signup()
        response = self.client.post(reverse('account_confirm_email', kwargs={'key': 'nimportequoi'}))
        self.assertIn(response.status_code, (404, 200))
        self.assertFalse(EmailAddress.objects.get(user__username='nouveau').verified)

    def test_full_flow_signup_confirm_login(self):
        self.signup()
        self.client.post(link_in(mail.outbox[0], '/account/confirm_email/'))
        response = self.client.post(reverse('account_login'), {
            'username': 'nouveau', 'password': PASSWORD,
        })
        self.assertRedirects(response, '/course/choose/', fetch_redirect_response=False)
        self.assertIn('_auth_user_id', self.client.session)


class LoginLogoutTestCase(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_login_page(self):
        response = self.client.get(reverse('account_login'))
        self.assertEqual(response.status_code, 200)

    def test_login_ok_redirects_to_course_choose(self):
        response = self.client.post(reverse('account_login'), {
            'username': 'alice', 'password': PASSWORD,
        })
        self.assertRedirects(response, '/course/choose/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_login_honours_next(self):
        response = self.client.post(reverse('account_login') + '?next=/course/', {
            'username': 'alice', 'password': PASSWORD,
        })
        self.assertRedirects(response, '/course/', fetch_redirect_response=False)

    def test_login_wrong_password(self):
        response = self.client.post(reverse('account_login'), {
            'username': 'alice', 'password': 'mauvais',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_unknown_user(self):
        response = self.client.post(reverse('account_login'), {
            'username': 'personne', 'password': PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_is_by_username_not_email(self):
        # AUTHENTICATION_BACKENDS = UsernameAuthenticationBackend uniquement
        self.client.post(reverse('account_login'), {
            'username': 'alice@example.com', 'password': PASSWORD,
        })
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        self.client.post(reverse('account_login'), {'username': 'alice', 'password': PASSWORD})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_account_logout_post_logs_out(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('account_logout'))
        self.assertIn(response.status_code, (200, 302))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_account_logout_anonymous_does_not_crash(self):
        response = self.client.post(reverse('account_logout'))
        self.assertIn(response.status_code, (200, 302))

    def test_course_admin_logout_logs_out(self):
        # /course/logout/ : le CourseAdminSite l'autorise meme sans accreditation
        self.client.force_login(self.user)
        # Django >= 5 : la deconnexion de l'admin n'accepte plus que POST
        response = self.client.post('/course/logout/')
        self.assertIn(response.status_code, (200, 302))
        self.assertNotIn('_auth_user_id', self.client.session)


class LoginProtectsBackofficeTestCase(TestCase):
    """Le vrai login ouvre bien le back-office, via la vraie session."""

    def setUp(self):
        self.course = CourseFactory(uid='authc')
        self.user = make_user()
        Accreditation.objects.create(user=self.user, course=self.course, role='admin')

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get('/course/choose/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/course/login/', response.url)

    def test_login_then_choose_page(self):
        self.client.post(reverse('account_login'), {'username': 'alice', 'password': PASSWORD})
        response = self.client.get('/course/choose/')
        self.assertEqual(response.status_code, 200)

    def test_login_then_course_scoped_page(self):
        self.client.post(reverse('account_login'), {'username': 'alice', 'password': PASSWORD})
        self.client.cookies['course_uid'] = 'authc'
        response = self.client.get('/course/')
        self.assertEqual(response.status_code, 200)

    def test_logout_closes_backoffice(self):
        self.client.post(reverse('account_login'), {'username': 'alice', 'password': PASSWORD})
        self.client.post(reverse('account_logout'))
        self.client.cookies['course_uid'] = 'authc'
        response = self.client.get('/course/')
        self.assertEqual(response.status_code, 302)


class PasswordResetTestCase(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_reset_unknown_email_sends_nothing(self):
        self.client.post(reverse('account_password_reset'), {'email': 'inconnu@example.com'})
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_known_email_sends_mail(self):
        self.client.post(reverse('account_password_reset'), {'email': 'alice@example.com'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['alice@example.com'])
        link_in(mail.outbox[0], '/account/password/reset/')

    def test_full_reset_flow_changes_password(self):
        self.client.post(reverse('account_password_reset'), {'email': 'alice@example.com'})
        url = link_in(mail.outbox[0], '/account/password/reset/')
        # GET : redirection vers l'URL "session" ou affichage direct du formulaire
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        form_url = response.redirect_chain[-1][0] if response.redirect_chain else url
        new_password = 'N0uveauMotDePasse!'
        self.client.post(form_url, {'password': new_password, 'password_confirm': new_password})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password(PASSWORD))

    def test_reset_with_bad_token_does_not_change_password(self):
        url = reverse('account_password_reset_token', kwargs={'uidb36': 'zz', 'token': 'abc-123'})
        self.client.post(url, {'password': 'Autre1234!', 'password_confirm': 'Autre1234!'})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))


class PasswordChangeTestCase(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_anonymous_is_redirected_to_password_reset(self):
        # comportement de django-user-accounts : un anonyme est envoye vers le reset
        response = self.client.get(reverse('account_password'))
        self.assertRedirects(response, reverse('account_password_reset'), fetch_redirect_response=False)

    def test_change_password(self):
        self.client.force_login(self.user)
        new_password = 'Chang3Moi!!'
        self.client.post(reverse('account_password'), {
            'password_current': PASSWORD,
            'password_new': new_password,
            'password_new_confirm': new_password,
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_change_password_wrong_current(self):
        self.client.force_login(self.user)
        self.client.post(reverse('account_password'), {
            'password_current': 'faux',
            'password_new': 'Chang3Moi!!',
            'password_new_confirm': 'Chang3Moi!!',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))
