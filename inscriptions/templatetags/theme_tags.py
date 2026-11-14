from django import template
from django.contrib.messages.utils import get_level_tags
from django.utils.encoding import force_str

register = template.Library()


@register.simple_tag()
def get_message_tags(message):
    """
    Classe CSS Bootstrap ("alert-<niveau>") du niveau du message, suivie de ses extra_tags.
    (Ancien tag de pinax-theme-bootstrap, repris ici depuis que le paquet n'est plus utilise.)
    """
    level_tag = force_str(get_level_tags().get(message.level, ''), strings_only=True)
    if level_tag == "error":
        # .alert-error n'existe plus en Bootstrap 3
        level_tag = "danger"
    alert_level_tag = "alert-{tag}".format(tag=level_tag) if level_tag else None
    extra_tags = force_str(message.extra_tags, strings_only=True)

    if extra_tags and alert_level_tag:
        return ' '.join([extra_tags, alert_level_tag])
    return extra_tags or alert_level_tag or ''
