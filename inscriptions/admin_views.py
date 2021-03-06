# -*- coding: utf-8 -*-
import random
import csv, io
from .models import Equipe, Equipier, TemplateMail, Course
from .settings import *
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum, Case, When, Value, IntegerField
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template.response import TemplateResponse
from django.utils.http import urlencode
from django.utils.translation import ugettext as _

@login_required
def dossards(request, course_uid):
    return TemplateResponse(request, 'dossards.html', {
        'equipiers': Equipier.objects.filter(equipe__course__uid=course_uid).order_by(*request.GET.get('order','equipe__numero,numero').split(','))
    })

@login_required
def listing(request, course_uid, template='listing.html'):
    return TemplateResponse(request, template, {
        'course': get_object_or_404(Course, uid=course_uid),
        'equipes': Equipe.objects.filter(course__uid=course_uid).order_by(*request.GET.get('order','numero').split(',')),
        'order': request.GET.get('order','numero')
    })

def equipiers(request, course_uid):
    return TemplateResponse(request, 'equipiers.html', {
        'course': get_object_or_404(Course, uid=course_uid),
        'equipiers': Equipier.objects.filter(equipe__course__uid=course_uid)
    })

#@login_required
def dossardsCSV(request, course_uid):
    code = request.GET.get('code', 'utf-8')
    out = io.StringIO()
    o=csv.writer(out, dialect='excel')
    o.writerow([
        'equipe',
        'nom',
        'categorie',
        'dossard',
        'nom',
        'prenom',
        'sexe',
        'date_de_naissance',
        'num_licence',
        'gerant_nom',
        'gerant_prenom',
        'gerant_ville',
        'gerant_code_postal',
        'gerant_code_pays',
    ])
    for e in Equipier.objects.filter(equipe__course__uid=course_uid):
        row = [
            e.equipe.numero,
            e.equipe.nom,
            e.equipe.categorie,
            e.dossard(),
            e.nom,
            e.prenom,
            e.sexe,
            e.date_de_naissance,
            e.num_licence,
            e.equipe.gerant_nom,
            e.equipe.gerant_prenom,
            e.equipe.gerant_ville,
            e.equipe.gerant_code_postal,
            e.equipe.gerant_pays,
        ]
        row = [ str(i) for i in row ]
        o.writerow(row)

    r = HttpResponse(out.getvalue().encode(code), content_type='text/csv', charset=code)
    out.close()
    return r

def dossardsEquipesCSV(request, course_uid):
    code = request.GET.get('code', 'utf-8')
    out = io.StringIO()
    o=csv.writer(out, dialect='excel')
    o.writerow([
        'equipe',
        'nom',
        'categorie',
        'gerant_nom',
        'gerant_prenom',
        'gerant_ville',
        'gerant_code_postal',
        'gerant_code_pays',
    ])
    for e in Equipe.objects.filter(course__uid=course_uid):
        row = [
            e.numero,
            e.nom,
            e.categorie,
            e.gerant_nom,
            e.gerant_prenom,
            e.gerant_ville,
            e.gerant_code_postal,
            e.gerant_pays,
        ]
        row = [ str(i) for i in row ]
        o.writerow(row)

    r = HttpResponse(out.getvalue().encode(code), content_type='text/csv', charset=code)
    out.close()
    return r

def dossardsEquipiersCSV(request, course_uid):
    code = request.GET.get('code', 'utf-8')
    out = io.StringIO()
    o=csv.writer(out, dialect='excel')
    o.writerow([
        'equipe',
        'dossard',
        'nom',
        'prenom',
        'sexe',
        'date_de_naissance',
        'num_licence',
    ])
    for e in Equipier.objects.filter(equipe__course__uid=course_uid):
        row = [
            e.equipe.numero,
            e.dossard(),
            e.nom,
            e.prenom,
            e.sexe,
            e.date_de_naissance,
            e.num_licence,
        ]
        row = [ str(i) for i in row ]
        o.writerow(row)

    r = HttpResponse(out.getvalue().encode(code), content_type='text/csv', charset=code)
    out.close()
    return r
