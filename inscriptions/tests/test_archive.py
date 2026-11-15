from datetime import date, timedelta


from django.urls import reverse

from inscriptions.factories import CourseFactory
from inscriptions.models import Course, Edition
from inscriptions.tests.base import BaseTestCase


class ArchiveTestCase(BaseTestCase):
    def _edition(self, jours, **kwargs):
        return CourseFactory(date=date.today() + timedelta(days=jours), active=True,
                             course__active=True, **kwargs)

    def test_nouvelle_edition_desarchive_la_course(self):
        edition = self._edition(-1000)
        Course.objects.filter(pk=edition.course_id).update(archive=True)
        course = Course.objects.get(pk=edition.course_id)
        Edition.objects.create(
            course=course, nom='Nouvelle', date=date.today(), url_reglement='http://example.com',
            email_contact='a@example.com', date_ouverture=date.today(), date_fermeture=date.today(),
            limite_participants=10)
        self.assertFalse(Course.objects.get(pk=course.pk).archive)

    def test_modifier_edition_ne_desarchive_pas(self):
        edition = self._edition(-1000)
        Course.objects.filter(pk=edition.course_id).update(archive=True)
        edition = Edition.objects.get(pk=edition.pk)
        edition.nom = 'Autre'
        edition.save()
        self.assertTrue(Course.objects.get(pk=edition.course_id).archive)

    def test_accueil_separe_courses_et_archives(self):
        recente = self._edition(-30)
        vieille = self._edition(-1000)
        plus_recente = self._edition(-5)
        Course.objects.filter(pk=vieille.course_id).update(archive=True)
        reponse = self.client.get(reverse('home'))
        self.assertEqual([c.pk for c in reponse.context['courses']],
                         [plus_recente.course_id, recente.course_id])
        self.assertEqual([c.pk for c in reponse.context['anciennes_courses']], [vieille.course_id])
