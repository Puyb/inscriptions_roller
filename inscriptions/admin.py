# -*- coding: utf-8 -*-
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from .models import CourseEdition


from .admin_main import site as main_site
from .admin_course import site as course_site

def course_setter(request, course_uid):
    response = redirect(reverse('admin:index', current_app='course'))
    course = get_object_or_404(CourseEdition, uid=course_uid)
    response.set_cookie('course_uid', course_uid)
    response.set_cookie('course_id', course.id)
    response.set_cookie('course_nom', course.nom)
    return response
