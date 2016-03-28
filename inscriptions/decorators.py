from .models import Course
from datetime import date
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

def open_closed(func):
    def newFunc(request, course_uid, *args, **kwargs):
        course = get_object_or_404(Course, uid=course_uid)
        now = date.today()
        if not request.user.is_staff and not course.ouverte:
            return render_to_response('not_opened_yet.html', RequestContext(request, {}))
        if not request.user.is_staff and course.fermee:
            return render_to_response('closed.html', RequestContext(request, {}))
        return func(request, course_uid, *args, **kwargs)
    return newFunc
