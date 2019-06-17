import logging
import json
import re
from channels.consumer import SyncConsumer
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMessage
from django.urls import reverse

logger = logging.getLogger(__name__)

class MailConsumer(SyncConsumer):
    def send_mail(self, message):
        try:
            logger.info('sending mail %s', message)
            message.pop('type')
            name = message.pop('name', 'Enduroller')
            content_type = message.pop('content_type', 'html')
            message_id = message.pop('message_id')
            #to = json.loads(message.pop('to'))
            body = message.pop('body')
            if content_type == 'html':
                body = re.sub(
                    r'(https?://%s[^?"#]+)(\?([^#"]*))?(\#[^"]*)?' % Site.objects.get_current(),
                    r'\1?\3&message_id=%s\4' % message_id,
                    body
                )
                body += '<img src="https://%s%sblank.gif?message_id=%s" width=1 height=1 />' % (
                    Site.objects.get_current(),
                    settings.STATIC_URL,
                    message_id,
                )
            mail = EmailMessage(
                from_email='%s <%s>' % (name, settings.DEFAULT_FROM_EMAIL),
                #to=to,
                body=body,
                headers={'Message-ID': message_id},
                **message,
            )
            mail.content_subtype = content_type
            mail.send()
        except Exception:
            logger.exception('error sending mail')
