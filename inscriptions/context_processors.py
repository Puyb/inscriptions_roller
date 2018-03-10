from django.conf import settings
from .models import Course
from django.db.models import Min, Max
from django.contrib.sites.models import Site

def course(request):
    uid = request.path.split('/')[1]
    if uid in ('course', 'admin'):
        if 'course_uid' not in request.COOKIES:
            return {
                'COURSES': request.user.is_superuser and Course.objects.all() or [],
            }
        uid = request.COOKIES['course_uid']
    course = (Course.objects
        .filter(uid=uid)
        .prefetch_related('categories')
        .annotate(min_age=Min('categories__min_age'), max_equipiers=Max('categories__max_equipiers')))
    if not course.count():
        return {}
    course = course[0]
    return {
        'COURSE':          course,
        'YEAR':            course.date.year,
        'MONTH':           course.date.month,
        'DAY':             course.date.day,
        'TITLE':           course.nom,
        'MIN_AGE':         course.min_age,
        'MAX_EQUIPIERS':   course.max_equipiers,
        'CLOSE_YEAR':      course.date_fermeture.year,
        'CLOSE_MONTH':     course.date_fermeture.month,
        'CLOSE_DAY':       course.date_fermeture.day,
        'PAYPAL_BUSINESS': course.paypal,
        'COURSES':         request.user.is_superuser and Course.objects.all() or [],
    }

def import_settings(request):
    return {
        'PAYPAL_URL':      settings.PAYPAL_URL,
        'ROOT_URL': 'http://%s' % Site.objects.get_current(),
    }
