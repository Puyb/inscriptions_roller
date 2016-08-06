# -*- coding: utf-8 -*-
import random
import csv, io
from .models import Equipe, Equipier, TemplateMail, Course, TAILLES_CHOICES
from .settings import *
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum, Case, When, Value, IntegerField
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils.http import urlencode
from django.utils.translation import ugettext as _

@login_required
def dossards(request, course_uid):
    return render_to_response('dossards.html', RequestContext(request, {
        'equipiers': Equipier.objects.filter(equipe__course__uid=course_uid).order_by(*request.GET.get('order','equipe__numero,numero').split(','))
    }))

@login_required
def tshirts(request, course_uid):
    annotates = {}
    annotates['hommme'] = Sum(Case(When(equipier__sexe='H', then=Value(1)), default=Value(0), output_field=IntegerField))
    annotates['femmme'] = Sum(Case(When(equipier__sexe='F', then=Value(1)), default=Value(0), output_field=IntegerField))
    rh = annotates['hommme']
    rf = annotates['femmme']

    for t, n in TAILLES_CHOICES:
        annotates['tailles_hommme_' + t] = Sum(Case(When(equipier__taille_shirt=t, equipier__sexe='H', then=Value(1)), default=Value(0), output_field=IntegerField))
        annotates['tailles_femmme_' + t] = Sum(Case(When(equipier__taille_shirt=t, equipier__sexe='F', then=Value(1)), default=Value(0), output_field=IntegerField))
        rh -= annotates['tailles_hommme_' + t]
        rh -= annotates['tailles_femmme_' + t]
    annotates['tailles_homme_reste'] = rh
    annotates['tailles_femme_reste'] = rf

    return render_to_response('t-shirts.html', RequestContext(request, {
        'course': get_object_or_404(Course, uid=course_uid),
        'equipes': Equipe.objects.filter(course__uid=course_uid).annotate(**annotates).order_by(*request.GET.get('order','numero').split(',')),
        'order': request.GET.get('order','numero')
    }))

@login_required
def listing(request, course_uid, template='listing.html'):
    return render_to_response(template, RequestContext(request, {
        'course': get_object_or_404(Course, uid=course_uid),
        'equipes': Equipe.objects.filter(course__uid=course_uid).order_by(*request.GET.get('order','numero').split(',')),
        'order': request.GET.get('order','numero')
    }))

def equipiers(request, course_uid):
    return render_to_response('equipiers.html', RequestContext(request, {
        'course': get_object_or_404(Course, uid=course_uid),
        'equipiers': Equipier.objects.filter(equipe__course__uid=course_uid)
    }))

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
        'transpondeur',
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
            e.transpondeur,
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
