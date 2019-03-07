import decimal
import logging
import re
import time
from decimal import Decimal
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
    def __init__ (self, mails):
        Thread.__init__(self)
        self.mails = mails

    def run(self):  
        for mail in self.mails:
            try:
                logger.debug('send mail %s' % mail)
                mail.send()
                logger.debug('mail sent %s' % mail)
            except Exception as e:
                logger.exception('error send mail')


class ChallengeUpdateThread(Thread):
    def __init__(self, course):
        Thread.__init__(self)
        self.course = course

    def run(self):
        for challenge in self.course.challenges.all():
            challenge.compute_course(self.course)
            challenge.compute_challenge()
            #messages.add_message(request, messages.INFO, u'Classement du challenge "%s" calculé' % (challenge.nom, ))

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

def jsonDate(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError('Object of type %s with value of %s is not JSON serializable' % (type(obj), repr(obj)))

def floor(value):
    with decimal.localcontext() as ctx:
        ctx.rounding = decimal.ROUND_FLOOR
        return value.quantize(Decimal('1.00'))

def roundcent(value):
    if value - floor(value) > Decimal('0.005'):
        return Decimal('0.01')
    return Decimal('0.00')

def round(value):
    return floor(value) + roundcent(value)

def repartition_frais(montants, frais):
    """
    Calcul de la repartition des frais au prorata avec arrondis au centime
    Assure que le total des arrondis est bien equal au total des frais
    quite a ajouter un centime en plus si besoin
    """
    total = Decimal('0.00')
    for montant in montants:
        total += montant

    frais_list = []
    montant_arrondis = Decimal('0.00')
    for montant in montants:
        montant_frais = montant / total * frais
        frais_list.append([
            floor(montant_frais),
            roundcent(montant_frais)
        ])
        montant_arrondis += floor(montant_frais)
    for item in frais_list:
        if item[1] == Decimal('0.01') and montant_arrondis < frais:
            item[0] += item[1]
            montant_arrondis += item[1]
    for item in frais_list:
        if item[1] == Decimal('0') and montant_arrondis < frais:
            item[0] += Decimal('0.01')
            montant_arrondis += Decimal('0.01')
    return (item[0] for item in frais_list)
