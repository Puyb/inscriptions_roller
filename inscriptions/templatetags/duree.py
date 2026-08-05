from django import template
from math import floor, ceil
import logging
logger = logging.getLogger(__name__)

register = template.Library()

@register.filter
def duree(value):
    if not value:
        return ''
    if value > 3600:
        return '%d:%02d:%06.3f' % (floor(value / 3600), floor(value / 60) % 60, value % 60)
    return '%d:%06.3f' % (floor(value / 60), value % 60)

@register.filter
def mod3(value, total):
    return (value + 1) % ceil(total / 4) == 0

@register.filter
def choose(value, lst):
    index = int(value) - 1
    choices = lst.split(',')
    if index < 0 or index >= len(choices):
        return 'color%d' % (index + 1)
    return choices[index]
