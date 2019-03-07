import logging
from django.conf import settings
from django.core.mail import EmailMessage


logger = logging.getLogger('email')

def send_mail(message):
    print('popopopo')
    try:
        name = message.content.pop('from', 'Enduroller')
        type = message.content.pop('type', 'html')
        logger.info(message.content)
        mail = EmailMessage(
            from_email='%s <%s>' % (name, settings.DEFAULT_FROM_EMAIL),
            **message.content,
        )
        mail.content_subtype = type
        mail.send()
    except Exception:
        logger.exception('error sending mail')
