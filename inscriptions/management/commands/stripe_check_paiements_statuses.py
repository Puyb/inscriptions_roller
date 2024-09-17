from django.core.management.base import BaseCommand, CommandError
from inscriptions.models import Paiement, Course
from decimal import Decimal
import requests
from datetime import datetime

class Command(BaseCommand):
    help = 'Check the statuses of the stripe paiements for the given Course'

    def add_arguments(self, parser):
        parser.add_argument('course_uid', type=str)

    def handle(self, *args, **options):
        course = Course.objects.get(uid=options['course_uid'])

        if not course.stripe_secret:
            self.stdout.write(self.style.ERROR('Stripe is not configured for this course'))
            return

        paiements = Paiement.objects.filter(equipes__equipe__course=course, montant__isnull=True, stripe_intent__isnull=False)
        for paiement in paiements:
            response = requests.get('https://api.stripe.com/v1/payment_intents/%s' % (paiement.stripe_intent, ), auth=(course.stripe_secret, ''))
            intent = response.json()
            self.stdout.write('Intent %s: %s' % (paiement.stripe_intent, intent['status']))
            if intent['status'] == 'succeeded':
                paiement.montant = Decimal(intent['amount']) / 100
                paiement.detail = '\nConfirmed on %s by command line' % datetime.now()
                paiement.save()
                paiement.send_equipes_mail()
                paiement.send_admin_mail()
            if intent['status'] == 'payement_failed':
                error_message = intent['last_payment_error']['message'] if intent.get('last_payment_error') else None
                paiement.detail = '\nRejected on %s by command line\n%s' % (datetime.now(), error_message)
                paiement.save()

        self.stdout.write(self.style.SUCCESS('Successfully check stripe paiements'))
