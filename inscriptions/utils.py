import logging
import re
import time
from urllib.parse import urlparse, urlunparse
from threading import Thread
from django.contrib import messages
#from django.template.loader import render_to_string
#from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)

def urlEncodeNonAscii(b):
    return re.sub(b'[\x80-\xFF]', lambda c: ('%%%02x' % ord(c.group(0))).encode('ascii'), b)

def iriToUri(iri):
    parts = urlparse(iri)
    return urlunparse([
        part.encode('idna') if parti==1 else urlEncodeNonAscii(part.encode('utf-8'))
        for parti, part in enumerate(parts)
    ])

class MailThread(Thread):
    def __init__ (self, messages):
        Thread.__init__(self)
        self.messages = messages

    def run(self):  
        for message in self.messages:
            message.send()

class ChallengeUpdateThread(Thread):
    def __init__(self, qs):
        Thread.__init__(self)
        self.qs = qs

    def run(self):
        for challenge in self.qs:
            challenge.compute_course()
            challenge.compute_challenge()
            messages.add_message(request, messages.INFO, u'Classement du challenge "%s" calculé' % (challenge.nom, ))

class ChallengeInscriptionEquipe(Thread):
    def __init__(self, equipe):
        Thread.__init__(self)
        self.equipe = equipe

    def run(self):
        time.sleep(10)

        for challenge in self.equipe.course.challenges.all():
            try:
                challenge.inscription_equipe(self.equipe)
            except:
                import traceback
                traceback.print_exc()
                logger.exception('error updating challenge')
