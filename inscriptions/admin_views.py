# -*- coding: utf-8 -*-
import random
import csv, io
from .forms import ImportResultatForm
from .models import Equipe, Equipier, TemplateMail, Course
from .settings import *
from .utils import ChallengeUpdateThread
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
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

def import_resultats(course, request):
    form = ImportResultatForm()

    if request.method == 'POST':
        form = ImportResultatForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv']
            data = form.cleaned_data

            with transaction.atomic():
                course.equipe_set.all().update(
                    tours              = None,
                    temps              = None,
                    position_generale  = None,
                    position_categorie = None,
                )

                with io.StringIO(csv_file.read().decode('utf-8')) as io_file:
                    csv_reader = csv.reader(io_file, delimiter=',')
                    if data.get('skip_first'):
                        next(csv_reader)

                    def g(row, n, f=lambda x: x):
                        if not data.get(n):
                            return None
                        return f(row[data[n] - 1])
                    equipes = list(course.equipe_set.select_related('categorie'))
                    numeros = [ e.numero for e in equipes]
                    equipes_by_numero = { e.numero: e for e in equipes }


                    for row in csv_reader:
                        numero = int(g(row, 'dossard_column'))
                        equipe = equipes_by_numero.get(numero)
                        if not equipe:
                            categorie = course.categories.filter(numero_debut__lte=numero, numero_fin__gte=numero)[0]
                            equipe = Equipe(
                                numero=numero,
                                course=course,
                                categorie=categorie,
                                nom='Equipe non inscrite %s' % numero,
                                gerant_nom='?',
                                gerant_prenom='?',
                                gerant_ville='?',
                                gerant_code_postal='?',
                                gerant_email=course.email_contact,
                                nombre=categorie.max_equipiers,
                                prix=Decimal(0),
                            )
                            equipes.append(equipe)
                            equipes_by_numero[numero] = equipe
                        else:
                            numeros.remove(numero)

                        equipe.tours = g(row, 'tours_column', int)
                        if data.get('time_column'):
                            if data['time_format'] == 'HMS':
                                s = g(row, 'time_column').split(':')
                                time = Decimal(0)
                                n = Decimal(1)
                                while len(s):
                                    time += n * Decimal(s.pop())
                                    n *= Decimal(60)
                            else:
                                time = Decimal(g(row, 'time_column'))
                            equipe.temps = time
                        equipe.position_generale  = g(row, 'position_generale_column', int)
                        equipe.position_categorie = g(row, 'position_categorie_column', int)


                        #super(Equipe, equipe).save()

                # compute positions
                equipes_to_compute = None
                if data.get('time_column') and data.get('tours_column'):
                    #equipes = course.equipe_set.exclude(numero__in=numeros).select_related('categorie').order_by('tours', 'temps')
                    equipes_to_compute = [ e for e in equipes if e.numero not in numeros ]
                    equipes_to_compute = sorted(equipes_to_compute, key=lambda e: e.temps)
                    equipes_to_compute = sorted(equipes_to_compute, key=lambda e: e.tours, reverse=True)

                elif not data.get('position_categorie_column') and data.get('position_generale_column'):
                    #equipes = course.equipe_set.exclude(numero__in=numeros).filter(position_generale__isnull=False).select_related('categorie').order_by('position_generale')
                    equipes_to_compute = [ e for e in equipes if e.numero not in numeros and e.position_generale is not None ]
                    equipes_to_compute = sorted(equipes_to_compute, key=lambda e: e.position_generale)

                if equipes_to_compute:
                    position = 1
                    position_categories = {}
                    for categorie in course.categories.all():
                        position_categories[categorie.code] = 1

                    for equipe in equipes_to_compute:
                        if not data.get('position_generale_column'):
                            equipe.position_generale = position
                            position += 1
                        code = equipe.categorie.code
                        equipe.position_categorie = position_categories[code]
                        position_categories[code] += 1
                for equipe in equipes:
                    super(Equipe, equipe).save()

            ChallengeUpdateThread(courses.challenges.all()).start()

            return render_to_response('admin/import_resultat_done.html', RequestContext(request, {
                'course': course,
                'equipes': course.equipe_set.exclude(numero__in=numeros).select_related('categorie').order_by('position_generale'),
                'equipes_manquantes': course.equipe_set.filter(numero__in=numeros),
            }))
    return render_to_response('admin/import_resultat_form.html', RequestContext(request, {
        'course': course,
        'form': form,
    }))



