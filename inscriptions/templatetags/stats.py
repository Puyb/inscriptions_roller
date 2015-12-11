from django import template
import sys

register = template.Library()

@register.filter
def get(dictionary, key):
    return dictionary.get(key)

@register.filter
def pertinent_values(dictionary, key):
    limit = '10'
    if ',' in key:
        key, limit = key.split(',')

    keys = dictionary.keys()

    total = reduce(lambda a, b: a + dictionary[b][key], keys, 0)
    if limit[-1:] == '%':
        limit = total * float(limit[:-1]) / 100.0
    else:
        limit = int(limit)

    print >>sys.stderr, limit

    keys.sort(lambda a, b: cmp(dictionary[b][key], dictionary[a][key]))

    index = len(keys) - 1
    while dictionary[keys[index]][key] < limit and index > 10:
        index -= 1
    return keys[:index + 1]

@register.filter
def other_values(dictionary, key):
    limit = '10'
    if ',' in key:
        key, limit = key.split(',')

    keys = dictionary.keys()

    total = reduce(lambda a, b: a + dictionary[b][key], keys, 0)
    if limit[-1:] == '%':
        limit = total * float(limit[:-1]) / 100.0
    else:
        limit = int(limit)

    print >>sys.stderr, limit

    keys.sort(lambda a, b: cmp(dictionary[b][key], dictionary[a][key]))

    index = len(keys) - 1
    while dictionary[keys[index]][key] < limit and index > 10:
        index -= 1
    return keys[index + 1:]


@register.filter
def get_range(last):
    return range(last)

@register.filter
def get_max(l):
    return max(l)

@register.filter
def get_min(l):
    return min(l)

