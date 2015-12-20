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
    return {
        'COURSE':          course[0],
        'YEAR':            course[0].date.year,
        'MONTH':           course[0].date.month,
        'DAY':             course[0].date.day,
        'TITLE':           course[0].nom,
        'MIN_AGE':         course[0].min_age,
        'MAX_EQUIPIERS':   course[0].max_equipiers,
        'CLOSE_YEAR':      course[0].date_fermeture.year,
        'CLOSE_MONTH':     course[0].date_fermeture.month,
        'CLOSE_DAY':       course[0].date_fermeture.day,
        'PAYPAL_BUSINESS': course[0].paypal,
        'COURSES':         request.user.is_superuser and Course.objects.all() or [],
    }

def import_settings(request):
    return {
        'PAYPAL_URL':      settings.PAYPAL_URL,
        'ROOT_URL': 'http://%s' % Site.objects.get_current(),
        'FACEBOOK_APPID':  settings.FACEBOOK_APPID,
    }
