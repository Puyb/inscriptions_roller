from django import template

register = template.Library()

@register.filter
def price(value, instance):
    return value.price(instance and instance.date)

@register.filter
def price_base(value, instance):
    return value.price_base(instance and instance.date)

@register.filter
def price_equipier(value, instance):
    return value.price_equipier(instance and instance.date)
