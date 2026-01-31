from django import template

register = template.Library()

@register.filter
def price(value, instance):
    return value.price(instance and instance.date)
