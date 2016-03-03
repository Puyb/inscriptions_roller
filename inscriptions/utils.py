import re
from urllib.parse import urlparse, urlunparse
from threading import Thread
#from django.template.loader import render_to_string
#from django.core.mail import EmailMessage

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
