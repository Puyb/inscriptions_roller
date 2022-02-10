from django import template
from functools import reduce
import sys

register = template.Library()

@register.filter
def get(dictionary, key):
    if not dictionary:
        return None
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    if hasattr(dictionary, key):
        return getattr(dictionary, key)
    return None

@register.filter
def pertinent_values(dictionary, key):
    limit = '10'
    if ',' in key:
        key, limit = key.split(',')

    keys = list(dictionary.keys())

    total = reduce(lambda a, b: a + dictionary[b][key], keys, 0)
    if limit[-1:] == '%':
        limit = total * float(limit[:-1]) / 100.0
    else:
        limit = int(limit)

    keys.sort(key=lambda a: dictionary[a][key], reverse=True)

    index = len(keys) - 1
    while index > 10 and dictionary[keys[index]][key] < limit:
        index -= 1
    return keys[:index + 1]

@register.filter
def other_values(dictionary, key):
    limit = '10'
    if ',' in key:
        key, limit = key.split(',')

    keys = list(dictionary.keys())

    total = reduce(lambda a, b: a + dictionary[b][key], keys, 0)
    if limit[-1:] == '%':
        limit = total * float(limit[:-1]) / 100.0
    else:
        limit = int(limit)

    keys.sort(key=lambda a: dictionary[a][key], reverse=True)

    index = len(keys) - 1
    while index > 10 and dictionary[keys[index]][key] < limit:
        index -= 1
    return keys[index + 1:]


@register.filter
def get_range(last):
    return range(last)

@register.filter
def get_max(l):
    if len(l):
        return max(l)
    return 0

@register.filter
def get_min(l):
    if len(l):
        return min(l)
    return 0

