from .models import CourseEdition
from datetime import date
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404

def open_closed(func):
    def newFunc(request, course_uid, *args, **kwargs):
        course = get_object_or_404(CourseEdition, uid=course_uid)
        now = date.today()
        if not request.user.is_staff and not course.ouverte:
            return TemplateResponse(request, 'not_opened_yet.html', {})
        if not request.user.is_staff and course.fermee:
            return TemplateResponse(request, 'closed.html', {})
        return func(request, course_uid, *args, **kwargs)
    return newFunc
