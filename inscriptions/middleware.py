from datetime import datetime
from django.db.models import F
from django.db.models.functions import Coalesce
from inscriptions.models import Mail

def tracking_middleware(get_response):
    def middleware(request):
        message_id = request.GET.get('message_id', None)
        if message_id:
            Mail.objects.filter(uid=message_id).update(read=Coalesce(F('read'), datetime.utcnow()))

        return get_response(request)

    return middleware
