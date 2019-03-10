import logging
from channels.consumer import SyncConsumer
from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)

class MailConsumer(SyncConsumer):
    def send_mail(self, message):
        try:
            message.pop('type')
            name = message.pop('name', 'Enduroller')
            content_type = message.pop('content_type', 'html')
            mail = EmailMessage(
                from_email='%s <%s>' % (name, settings.DEFAULT_FROM_EMAIL),
                **message,
            )
            mail.content_subtype = content_type
            mail.send()
        except Exception:
            logger.exception('error sending mail')
