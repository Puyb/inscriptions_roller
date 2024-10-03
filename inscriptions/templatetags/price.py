from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def price(value, instance):
    return value.price(instance and instance.date)
