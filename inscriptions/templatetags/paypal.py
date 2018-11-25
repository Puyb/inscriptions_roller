from decimal import Decimal
from django import template

register = template.Library()

def frais(value):
    return (value + Decimal('0.25')) / (Decimal('1.000') - Decimal('0.034')) - value

@register.filter
def frais_paypal(value):
    return frais(value)

@register.filter
def prix_paypal(value):
    return value + frais(value)
