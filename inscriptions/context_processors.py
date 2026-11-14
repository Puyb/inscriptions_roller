from django.apps import apps
from django.conf import settings
from .models import Edition, edition_lookup
from django.db.models import Min, Max
from django.contrib.sites.models import Site

def course(request):
    segments = request.path.split('/')
    if segments[1] in ('course', 'admin'):
        if 'course_uid' not in request.COOKIES:
            return {
                'COURSES': request.user.is_superuser and Edition.objects.all() or [],
            }
        key = request.COOKIES['course_uid']
    else:
        key = '/'.join(segments[1:3])
    course = (Edition.objects
        .select_related('course')
        .filter(**edition_lookup(key))
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
        'COURSES':         request.user.is_superuser and Edition.objects.all() or [],
    }

def import_settings(request):
    return {
        'PAYPAL_URL':      settings.PAYPAL_URL,
        'ROOT_URL': 'https://%s' % Site.objects.get_current(),
    }


def theme(request):
    """Variables de gabarit herites de pinax-theme-bootstrap (vendorise)."""
    ctx = {
        "THEME_ADMIN_URL": getattr(settings, "THEME_ADMIN_URL", "admin:index"),
        "THEME_CONTACT_EMAIL": getattr(settings, "THEME_CONTACT_EMAIL", "support@example.com"),
    }
    if apps.is_installed('django.contrib.sites'):
        site = Site.objects.get_current()
        ctx.update({"SITE_NAME": site.name, "SITE_DOMAIN": site.domain})
    return ctx
