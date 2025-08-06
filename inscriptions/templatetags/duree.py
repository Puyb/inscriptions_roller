from django import template
from math import floor

register = template.Library()

@register.filter
def duree(value):
    if not value:
        return ''
    if value > 60:
        return '%d:%02d:%02.1d' % (floor(value / 3600), floor(value / 60) % 60, value % 60)
    return '%d:%02.1d' % (floor(value / 60), value % 60)

