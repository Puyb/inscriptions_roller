from datetime import datetime
from django.db.models import F
from django.http import HttpResponsePermanentRedirect
from django.http.response import HttpResponseRedirectBase
from django.db.models.functions import Coalesce
from inscriptions.models import Mail

def tracking_middleware(get_response):
    def middleware(request):
        message_id = request.GET.get('message_id', None)
        if message_id:
            Mail.objects.filter(uid=message_id).update(read=Coalesce(F('read'), datetime.utcnow()))

        return get_response(request)

    return middleware


class HttpResponsePermanentRedirect308(HttpResponseRedirectBase):
    status_code = 308


# Chemins appeles par des services externes (qui ne suivent pas les redirections) :
# les anciennes URLs sont reecrites en interne au lieu d'etre redirigees.
CHEMINS_WEBHOOKS = ('ipn/', 'stripe/webhook/', 'helloasso/webhook/')


_legacy_cache = None


def _legacy_keys():
    """{ancien uid: cle course/edition}, charge une fois (le legacy_uid n'est pas editable)."""
    global _legacy_cache
    if _legacy_cache is None:
        from .models import Edition
        _legacy_cache = {
            e.legacy_uid: e.key
            for e in Edition.objects.select_related('course').exclude(legacy_uid__isnull=True)
        }
    return _legacy_cache


def _invalider_legacy(**kwargs):
    global _legacy_cache
    _legacy_cache = None


def legacy_uid_middleware(get_response):
    """Anciennes URLs /<uid>/... (un uid par edition) -> /<course>/<edition>/...

    GET/HEAD : redirection permanente ; autres methodes : 308 (conserve la
    methode et le corps) ; webhooks : reecriture interne, sans redirection."""
    from django.db.models.signals import post_delete, post_save
    from .models import Course, Edition, UIDS_RESERVES
    for modele in (Edition, Course):  # la cle depend aussi de l'uid de la course
        post_save.connect(_invalider_legacy, sender=modele, weak=False, dispatch_uid='legacy_save_%s' % modele.__name__)
        post_delete.connect(_invalider_legacy, sender=modele, weak=False, dispatch_uid='legacy_delete_%s' % modele.__name__)

    def middleware(request):
        segments = request.path_info.split('/')
        if len(segments) > 2 and segments[1] and segments[1] not in UIDS_RESERVES:
            cle = _legacy_keys().get(segments[1])
            if cle:
                reste = '/'.join(segments[2:])
                nouveau = '/%s/%s' % (cle, reste)
                if reste in CHEMINS_WEBHOOKS:
                    request.path_info = nouveau
                    request.path = nouveau
                else:
                    cible = nouveau
                    if request.META.get('QUERY_STRING'):
                        cible += '?' + request.META['QUERY_STRING']
                    if request.method in ('GET', 'HEAD'):
                        return HttpResponsePermanentRedirect(cible)
                    return HttpResponsePermanentRedirect308(cible)
        return get_response(request)

    return middleware
