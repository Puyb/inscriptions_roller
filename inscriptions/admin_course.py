# -*- coding: utf-8 -*-
import operator
from functools import reduce
from inscriptions.models import *
from django.conf.urls import url
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template import Template, Context
from django.template.response import TemplateResponse
from django.contrib import messages
from django.db.models import Sum, Value, F, Q, Max, Prefetch, OuterRef, Subquery
from django.db.models.functions import Coalesce, Extract
from django.db.models.query import prefetch_related_objects
from django.utils.translation import ugettext_lazy as _
from django.contrib.admin import SimpleListFilter
from django.http import HttpResponseRedirect
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .forms import CourseForm, ImportResultatForm, AdminPaiementForm
from .utils import ChallengeUpdateThread, send_mail
from account.views import LogoutView
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
from pytz import timezone
import json
import re
from Levenshtein import distance
import csv, io
import inspect

import logging
logger = logging.getLogger(__name__)

ICON_OK = '✅'
ICON_KO = '🚫'
ICON_CHECK = '❔'
ICON_MISSING = '📨'
ICON_LOCK = '🔒'

def getCourse(request, qs=Course.objects.all()):
    uid = request.COOKIES['course_uid']
    if request.user.is_superuser:
        return qs.get(uid=uid)
    return qs.get(uid=uid, accreditations__user=request.user)

class CourseAdminSite(admin.sites.AdminSite):
    def has_permission(self, request):
        if not request.user.is_authenticated:
            return False
        prefetch_related_objects([request.user], 'accreditations__course')
        if request.path.endswith('/logout/'):
            return True
        if request.user.is_superuser:
            return True
        if request.path == '/course/' or request.path.endswith('/choose/') or request.path.endswith('/ask/') or re.search(r'/ask/[^/]+/$', request.path) or request.path.endswith('/inscriptions/course/add/') or request.path.endswith('/course/jsi18n/'):
            return True
        if 'course_uid' not in request.COOKIES:
            return False
        course_uid = request.COOKIES['course_uid']
        return request.user.accreditations.filter(course__uid=course_uid).exclude(role='').count() > 0

    def get_urls(self):
        from django.conf.urls import url
        urls = [
            url(r'^choose/$', self.admin_view(self.course_choose), name='course_choose'),
            url(r'^ask/(?P<course_uid>[^/]+)/$', self.admin_view(self.course_ask_accreditation), name='course_ask_acreditation'),
            url(r'^ask/$', self.admin_view(self.course_ask_accreditation),    name='course_ask_acreditation'),
            url(r'^document/review/$', self.admin_view(self.document_review), name='course_document_review'),
            url(r'^listing/dossards/$', self.admin_view(self.listing_dossards), name='course_listing_dossards'),
            url(r'^anomalies/$', self.admin_view(self.anomalies), name='course_anomalies'),
            url(r'^anniversaires/$', self.admin_view(self.anniversaires), name='course_anniversaires'),
            url(r'^resultats/$', self.admin_view(self.resultats), name='course_resultats'),
            url(r'^inscriptions/paiement/add/$', self.admin_view(self.paiement_change), name='paiement_add'),
            url(r'^inscriptions/paiement/(?P<id>\d+)/change/$', self.admin_view(self.paiement_change), name='paiement_change'),
            url(r'^inscriptions/paiement/search/equipe/$', self.admin_view(self.paiement_search_equipe), name='paiement_search_equipe'),
            url(r'^inscriptions/categorie/test/$', self.admin_view(self.test_categories), name='test_categories'),
            url(r'^stats/$', self.admin_view(self.stats), name='course_stats'),
            url(r'^stats/(?P<course_uid>[^/]+)/$', self.admin_view(self.get_stats_api), name='course_stats_api'),
        ] + super().get_urls()
        return urls

    def course_choose(self, request):
        request.current_app = self.name
        accreditations = request.user.accreditations.all()
        qs = Course.objects.all()
        if 'old' not in request.GET:
            qs = qs.filter(date__gte=datetime.now() - timedelta(days=60))
        return TemplateResponse(request, 'admin/course_choose.html', dict(self.each_context(request),
            courses=qs.filter(accreditations__in=accreditations).order_by('date'),
            courses_admin=qs.exclude(accreditations__in=accreditations).order_by('date') if request.user.is_superuser else None,
        ))

    @transaction.atomic
    def course_ask_accreditation(self, request, course_uid=None):
        request.current_app = self.name
        if course_uid:
            course = get_object_or_404(Course, uid=course_uid)
            Accreditation(
                user=request.user,
                course=course,
            ).save()
            messages.add_message(request, messages.INFO, u'Demande d\'accreditation pour la course "%s" envoyée. Vous serez prévenu quand elle sera activée.' % (course.nom, ))

            send_mail(
                subject="Demande d'accès à %s" % (course.uid, ),
                body=render_to_string('mails/ask_accreditation.html', { 'course': course }),
                to=[course.email_contact],
            )
            return redirect('../')

        courses = Course.objects.exclude(id__in=[a.course.id for a in request.user.accreditations.filter(user=request.user)])
        demandes = Course.objects.filter(accreditations__user=request.user, accreditations__role='')
        context = dict(self.each_context(request),
            courses=courses,
            demandes=demandes,
        )
        return TemplateResponse(request, 'admin/course_ask_accreditation.html', context)

    def document_review(self, request):
        request.current_app = self.name
        course = getCourse(request)
        
        skip = []
        
        equipier = None

        if request.method == 'POST':
            if 'skip' in request.POST and request.POST['skip'] != '':
                skip = request.POST['skip'].split(',')
            equipier = Equipier.objects.get(id=request.POST['id'])
            if request.POST['value'] == 'yes' or request.POST['value'] == 'no':
                equipier.piece_jointe_valide = request.POST['value'] == 'yes'
                equipier.save()
            else:
                skip.append(str(equipier.id))
            equipier.equipe.commentaires = request.POST['commentaires']
            equipier.equipe.save()
        equipier = Equipier.objects.filter(equipe__course=course).exclude(id__in=skip).filter(verifier=True)

        if equipier.count() == 0:
            return redirect('/course/')


        return TemplateResponse(request, 'admin/document_review.html', dict(self.each_context(request),
            count=equipier.count(),
            index=len(skip) + 1,
            equipier=equipier[0],
            skip=','.join(skip)
        ))

    def listing_dossards(self, request):
        request.current_app = self.name
        course = getCourse(request)

        if request.method == 'POST':
            equipes = Equipe.objects.filter(course=course).order_by(*request.GET.get('order','numero').split(','))
            numero_max = equipes.aggregate(Max('numero'))['numero__max'] + 1
            splits = ('1,' + request.POST.get('split', numero_max)).split(',')
            splits = [ int(i) for i in splits ]
            if splits[-1] < numero_max:
                splits.append(numero_max)
            datas = {}
            keys = []
            for i in range(len(splits) - 1):
                key = u'%d à %d' % (splits[i], splits[i + 1] - 1)
                datas[key] = equipes.filter(numero__gte=splits[i],  numero__lt=splits[i + 1])
                keys.append(key)

            return TemplateResponse(request, 'listing_dossards.html', dict(self.each_context(request),
                equipes=datas,
                keys=keys,
            ))
        return TemplateResponse(request, 'admin/listing_dossards_form.html', dict(self.each_context(request), course=course))

    def anomalies(self, request):
        request.current_app = self.name
        course = getCourse(request)
        equipiers = list(Equipier.objects.annotate(
            n=Unaccent(Lower(RegexpReplace('nom', Value('[ -]\\+'), Value(' ')))),
            p=Unaccent(Lower(RegexpReplace('prenom', Value('[ -]\\+'), Value(' ')))),
        ).filter(equipe__course=course).select_related('equipe__categorie'))

        doublons = []
        for i, e in enumerate(equipiers):
            if e.numero > e.equipe.nombre:
                continue
            dbl = []
            for j in range(i + 1, len(equipiers)):
                e2 = equipiers[j]
                if e2.numero > e2.equipe.nombre:
                    continue
                if distance(e.n, e2.n) < 3 and distance(e.p, e2.p) < 3:
                    doublons.append([e, e2])
        return TemplateResponse(request, 'admin/anomalies.html', dict(self.each_context(request),
            doublons=doublons,
            course=course,
        ))

    def anniversaires(self, request):
        request.current_app = self.name
        course = getCourse(request)
        anniversaires = Equipier.objects.filter(
            equipe__course=course,
            date_de_naissance__day=Extract('equipe__course__date', 'day'),
            date_de_naissance__month=Extract('equipe__course__date', 'month'),
        )

        return TemplateResponse(request, 'admin/anniversaires.html', dict(self.each_context(request),
            anniversaires=anniversaires,
            course=course,
        ))

    def resultats(self, request):
        request.current_app = self.name
        course = getCourse(request, Course.objects.prefetch_related('categories', 'challenges'))
        form = ImportResultatForm()

        if request.method == 'POST':
            form = ImportResultatForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv']
                data = form.cleaned_data

                class AbortException(Exception):
                    pass
                try:
                    with transaction.atomic():
                        course.equipe_set.all().update(
                            tours              = None,
                            temps              = None,
                            position_generale  = None,
                            position_categorie = None,
                        )

                        for enc in ('utf-8', 'iso8859-1'):
                            try:
                                csv_file.seek(0)
                                with io.StringIO(csv_file.read().decode(enc)) as io_file:
                                    csv_reader = csv.reader(io_file, delimiter=request.POST.get('delimiter', ','))
                                    if data.get('skip_first'):
                                        next(csv_reader)

                                    def g(row, n, f=lambda x: x):
                                        if not data.get(n):
                                            return None
                                        return f(row[data[n] - 1])
                                    equipes = list(course.equipe_set.select_related('categorie'))
                                    numeros = [ e.numero for e in equipes]
                                    equipes_by_numero = { e.numero: e for e in equipes }

                                    def intOrNone(x):
                                        try:
                                            return int(x)
                                        except:
                                            return None

                                    line = 0
                                    for row in csv_reader:
                                        line += 1
                                        try:
                                            numero = int(g(row, 'dossard_column'))
                                        except ValueError as e:
                                            messages.add_message(
                                                request,
                                                messages.ERROR,
                                                _(u'Numéro d\'équipe incorrect dans la colonne %d à la ligne %d (%s)') % (data['dossard_column'], line, g(row, 'dossard_column'))
                                            )
                                            raise AbortException()
                                        equipe = equipes_by_numero.get(numero)
                                        if not equipe:
                                            if data.get('categorie_column'):
                                                categorie = course.categories.get(code=g(row, 'categorie_column'))
                                            else:
                                                categorie = course.categories.filter(numero_debut__lte=numero, numero_fin__gte=numero)[0]
                                            equipe = Equipe(
                                                numero=numero,
                                                course=course,
                                                categorie=categorie,
                                                nom=g(row, 'nom_column') or ('Equipe non inscrite %s' % numero),
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

                                        equipe.tours = g(row, 'tours_column', intOrNone)
                                        if data.get('time_column'):
                                            try:
                                                if data['time_format'] == 'HMS':
                                                    s = re.split('[^0-9.,]+', g(row, 'time_column').strip())
                                                    time = Decimal(0)
                                                    n = Decimal(1)
                                                    while len(s):
                                                        time += n * Decimal(s.pop().replace(',', '.'))
                                                        n *= Decimal(60)
                                                else:
                                                    time = Decimal(g(row, 'time_column'))
                                            except:
                                                messages.add_message(
                                                    request,
                                                    messages.ERROR,
                                                    _(u'Temps incorrect dans la colonne %d à la ligne %d (%s)') % (data['time_column'], line, g(row, 'time_column'))
                                                )
                                                raise AbortException()
                                            equipe.temps = time
                                        equipe.position_generale  = g(row, 'position_generale_column', intOrNone)
                                        equipe.position_categorie = g(row, 'position_categorie_column', intOrNone)


                                        #super(Equipe, equipe).save()
                                break
                            except UnicodeDecodeError as exc:
                                if enc == 'iso8859-1':
                                    raise exc

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

                        # save and add to challenges newly created equiped
                        for equipe in equipes:
                            _id = equipe.id
                            super(Equipe, equipe).save()
                            if not _id:
                                for challenge in course.challenges.all():
                                    challenge.inscription_equipe(equipe)

                    ChallengeUpdateThread(course).start()

                    return TemplateResponse(request, 'admin/import_resultat_done.html', dict(self.each_context(request),
                        course=course,
                        equipes=course.equipe_set.exclude(numero__in=numeros).select_related('categorie').order_by('position_generale'),
                        equipes_manquantes=course.equipe_set.filter(numero__in=numeros),
                    ))
                except AbortException as e:
                    pass
        return TemplateResponse(request, 'admin/import_resultat_form.html', dict(self.each_context(request),
            course=course,
            form=form,
        ))

    def paiement_change(self, request, id=None):
        paiement = None
        course = getCourse(request, Course.objects.all())
        courses = set(Course.objects.filter(accreditations__user=request.user, date__gte=datetime.now() - timedelta(days=60)))
        courses.add(course)

        equipes = {}
        montants = {}
        initials = {}
        repartitions = []
        
        if id:
            paiement = get_object_or_404(Paiement, id=id)
            repartitions = [{
                'equipe': r.equipe,
                'montant': r.montant,
                'paiement': r.equipe.montant_paiements - r.montant,
                'reste': r.equipe.prix - r.equipe.montant_paiements + r.montant,
            } for r in paiement.equipes.all()]
        elif request.GET.get('equipe_id'):
            repartitions = []
            initials['montant'] = Decimal(0)
            for equipe in Equipe.objects.filter(id__in=request.GET.getlist('equipe_id'), course__in=courses):
                repartitions.append({
                    'equipe': equipe,
                    'montant': None,
                    'paiement': equipe.montant_paiements,
                    'reste': equipe.prix - equipe.montant_paiements,
                });
                initials['montant'] += equipe.prix - equipe.montant_paiements

        paiement_form = AdminPaiementForm(instance=paiement, initial=initials)

        if request.method == 'POST':
            paiement_form = AdminPaiementForm(request.POST, instance=paiement)
            equipes = { str(e.id): e for e in Equipe.objects.filter(id__in=request.POST.getlist('equipe_id'), course__in=courses) }
            montants = zip(request.POST.getlist('equipe_id'), request.POST.getlist('repartition'))

            class PaiementException(Exception):
                pass
            try:
                with transaction.atomic():
                    paiement = paiement_form.save()
                    paiement.equipes.all().delete()
                    montant = Decimal(0)
                    repartitions = []
                    for equipe_id, repartition_montant in montants:
                        repartition = PaiementRepartition(
                            paiement=paiement,
                            equipe=equipes[equipe_id],
                            montant=Decimal(repartition_montant.replace(',', '.')),
                        )
                        repartition.save()
                        repartitions.append({
                            'equipe': repartition.equipe,
                            'montant': repartition.montant,
                            'paiement': repartition.equipe.montant_paiements,
                            'reste': repartition.equipe.prix - repartition.equipe.montant_paiements,
                        })

                        montant += repartition.montant
                        print(montant, equipe_id, repartition_montant, montant, paiement.montant)
                    if montant != paiement.montant:
                        raise PaiementException('montant incorrect')
                    print('len equipe_id', len(request.GET.getlist('equipe_id')))
                    paiement.send_equipes_mail()
                    if len(request.GET.getlist('equipe_id')) == 1:
                        return redirect('/course/inscriptions/equipe/%s/change/' % request.GET['equipe_id'])
                    if len(request.GET.getlist('equipe_id')) > 1:
                        return redirect('/course/inscriptions/equipe/')
                    return redirect('/course/inscriptions/paiement/')
            except PaiementException as e:
                messages.add_message(request, messages.ERROR, u'Répartition des montants incorrectes')

        return TemplateResponse(request, 'admin/paiement/add.html', dict(self.each_context(request),
            courses=courses,
            readonly=paiement.type in ('stripe', 'paypal') if paiement else False,
            paiement_form=paiement_form,
            repartitions=repartitions,
            app_label='inscriptions',
        ))

    @csrf_exempt
    def paiement_search_equipe(self, request):
        search = request.POST['search']

        course = getCourse(request, Course.objects.all())
        courses = Course.objects.filter(accreditations__user=request.user, date__gte=datetime.now() - timedelta(days=60))

        equipes = Equipe.objects.filter(Q(course__in=courses) | Q(course=course)).distinct()
        for bit in search.split():
            or_queries = [ Q(**{field + '__icontains': bit})
                            for field in EquipeAdmin.search_fields ]
            equipes = equipes.filter(reduce(operator.or_, or_queries))
        repartitions = {}
        if request.GET.get('id'):
            repartitions = {
                r.equipe_id: r.montant
                for r in PaiementRepartition.object.filter(paiement_id=request.GET.get('id'))
            }

        return HttpResponse(json.dumps({
            'equipes': [{
                'id': e.id,
                'course': e.course.nom,
                'numero': e.numero,
                'nom': e.nom,
                'prix': str(e.prix),
                'paiement': str(e.montant_paiements or '0'),
                'montant': str(repartitions.get(e.id, '0')),
            } for e in equipes],
        }))

    def test_categories(self, request):
        course = getCourse(request, Course.objects.all())
        return TemplateResponse(request, "admin/test_categories.html", {
            "course": course,
        })

    def stats(self, request):
        courses = Course.objects.filter(accreditations__user=request.user)
        courses_other = Course.objects.none()
        if request.user.is_superuser:
            courses_other = Course.objects.exclude(accreditations__user=request.user)
        course = getCourse(request, Course.objects.all())
        return TemplateResponse(request, "admin/stats.html", {
            "course": course,
            "courses": courses,
            "courses_other": courses_other,
        })

    def get_stats_api(self, request, course_uid):
        course = get_object_or_404(Course, uid=course_uid)
        stats = course.stats()
        def iso(d):
            return datetime.combine(d, datetime.min.time()).astimezone(timezone('Europe/Paris')).strftime('%Y-%m-%dT%H:%M:%S%z')
            
        return HttpResponse(json.dumps({
            'stats': {
                k: {
                    'equipes': v['equipes'],
                    'equipiers': v['equipiers'],
                    'prix': v['prix'],
                } for k, v in stats['jours'].items()
            },
            'uid': course.uid,
            'course': course.nom,
            'date': {
                'ouverture': iso(course.date_ouverture),
                'fermeture': iso(course.date_fermeture - timedelta(days=1)),
                'augmentation': iso((course.date_augmentation or course.date_fermeture) - timedelta(days=1)),
                'course': iso(course.date),
            },
            'delta': {
                'ouverture': 0,
                'fermeture': (course.date_fermeture - course.date_ouverture).days - 1,
                'augmentation': ((course.date_augmentation or course.date_fermeture) - course.date_ouverture).days - 1,
                'course': (course.date - course.date_ouverture).days,
            },
        }), content_type='application/json')


    index_template = 'admin/dashboard.html'


site = CourseAdminSite(name='course')

class CourseFilteredObjectAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        course_uid = request.COOKIES['course_uid']
        qs = qs.filter(course__uid=course_uid)
        if not request.user.is_superuser:
            qs = qs.filter(course__accreditations__user=request.user)
        return qs
    pass

class EquipierInline(admin.StackedInline):
    model = Equipier
    extra = 0
    max_num = 5
    readonly_fields = [ 'nom', 'prenom', 'sexe', 'adresse1', 'adresse2', 'ville', 'code_postal', 'pays', 'email', 'date_de_naissance', 'autorisation', 'justificatif', 'num_licence', 'piece_jointe', 'cerfa_valide', 'age']
    fieldsets = (
        (None, { 'fields': (('nom', 'prenom', 'sexe'), ) }),
        (u'Coordonnées', { 'classes': ('collapse', 'collapsed'), 'fields': ('adresse1', 'adresse2', ('ville', 'code_postal'), 'pays', 'email') }),
        (None, { 'classes': ('wide', ), 'fields': (('date_de_naissance', 'age', ), ('autorisation_valide', 'autorisation'), ('justificatif', 'num_licence', ), ('piece_jointe_valide', 'piece_jointe', 'cerfa_valide')) }),
    )

class StatusFilter(SimpleListFilter):
    title = _('Statut')
    parameter_name = 'status'
    def lookups(self, request, model_admin):
        return (
            ('verifier', _('%s À vérifier') % ICON_CHECK),
            ('complet', _('%s Complet') % ICON_OK),
            ('incomplet', _('%s Incomplet') % ICON_MISSING),
            ('erreur', _('%s Erreur') % ICON_KO),
        )
    def queryset(self, request, queryset):
        if self.value() == 'verifier':
            return queryset.filter(verifier_count__gt=0)
        if self.value() == 'erreur':
            return queryset.filter(verifier_count=0).filter(erreur_count__gt=0)
        if self.value() == 'complet':
            return queryset.filter(verifier_count=0).filter(erreur_count=0).filter(valide_count=F('nombre'))
        if self.value() == 'incomplet':
            return (queryset
                .filter(verifier_count=0)
                .filter(erreur_count=0)
                .exclude(valide_count=F('nombre'))
            )
        return queryset

class PaiementCompletFilter(SimpleListFilter):
    #TODO
    title = _('Paiement')
    parameter_name = 'paiement'
    def lookups(self, request, model_admin):
        return (
            ('complet', _('%s Paiement complet') % ICON_OK),
            ('incomplet', _('%s Impayé ou partiel') % ICON_KO),
            ('trop', _('> Trop payé')),
            ('exact', _('= Paiement exact')),
            ('partiel', _('< Partiel')),
            ('impaye', _('0 Impayé')),
        )
    def queryset(self, request, queryset):
        qs = Equipe.objects.filter(course=getCourse(request)).annotate(
            _montant_paiements=Sum(Case(When(paiements__paiement__montant__isnull=False, then=F('paiements__montant')), default=Value(0), output_field=models.DecimalField(max_digits=7, decimal_places=2)))
        )
        if self.value() == 'complet':
            qs = qs.filter(_montant_paiements__gte=F('prix'))
        if self.value() == 'incomplet':
            qs = qs.filter(Q(_montant_paiements__lt=F('prix')) | Q(_montant_paiements__isnull=True))
        if self.value() == 'trop':
            qs = qs.filter(_montant_paiements__gt=F('prix'))
        if self.value() == 'exact':
            qs = qs.filter(_montant_paiements=F('prix'))
        if self.value() == 'partiel':
            qs = qs.filter(_montant_paiements__lt=F('prix'), _montant_paiements__gt=0, _montant_paiements__isnull=False)
        if self.value() == 'impaye':
            qs = qs.filter(Q(_montant_paiements=0) | Q(_montant_paiements__isnull=True)).exclude(prix=0)
        return queryset.filter(id__in=qs);

class CategorieFilter(SimpleListFilter):
    title = _(u'Catégories')
    parameter_name = 'categorie'
    def lookups(self, request, model_admin):
        return [
            (c.code, u'%s - %s' % (c.code, c.nom))
            for c in Categorie.objects.filter(course__uid=request.COOKIES['course_uid']).order_by('max_equipiers', 'code')
        ]
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(categorie__code=self.value())
        return queryset

class MineurFilter(SimpleListFilter):
    title = _(u'Mineurs')
    parameter_name = 'mineurs'
    def lookups(self, request, model_admin):
        return [
            ('1', _('Avec mineurs')),
            ('0', _('Sans mineur')),
        ]
    def queryset(self, request, queryset):
        course = getCourse(request)
        date = course.date - relativedelta(years=18)
        if self.value() == '1':
            return queryset.filter(equipier__date_de_naissance__gt=date)
        if self.value() == '0':
            return queryset.exclude(equipier__date_de_naissance__gt=date)
        return queryset

class EquipeAdmin(CourseFilteredObjectAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.prefetch_related('equipier_set', 'paiements')
        qs = qs.annotate(
            verifier_count = Coalesce(Sum(Case(When(equipier__verifier=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
            valide_count   = Coalesce(Sum(Case(When(equipier__valide=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
            erreur_count   = Coalesce(Sum(Case(When(equipier__erreur=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
            _montant_paiements=Subquery(
                Equipe.objects.filter(pk=OuterRef('pk')).annotate(sum=Sum(Case(When(paiements__paiement__montant__isnull=False, then=F('paiements__montant')), default=Value(0), output_field=models.DecimalField(max_digits=7, decimal_places=2)))).values('sum')[:1]
            )
        )
        return qs

    class Media:
        css = {"all": ("admin.css",)}
        js = ('custom_admin/equipe.js', )
    readonly_fields = [ 'numero', 'nom', 'club', 'gerant_nom', 'gerant_prenom', 'gerant_adresse1', 'gerant_adress2', 'gerant_ville', 'gerant_code_postal', 'gerant_pays', 'gerant_telephone', 'categorie', 'nombre', 'prix', 'date', 'password', 'date']
    list_display = ['numero', 'categorie', 'nom', 'club', 'gerant_email', 'date', 'nombre2', 'paiement_complet2', 'documents_manquants2', 'dossier_complet_auto2']
    list_display_links = ['numero', 'categorie', 'nom', 'club', ]
    list_filter = [PaiementCompletFilter, StatusFilter, 'verrou', CategorieFilter, 'nombre', MineurFilter, 'date']
    ordering = ['-date', ]
    inlines = [ EquipierInline ]

#TODO add paiements amount, and link to add a new one
    fieldsets = (
        (None, { 'fields': (('numero', 'nom', 'club'), ('categorie', 'nombre', 'date'), ('prix',), 'commentaires')}),
        (u'Gérant', { 'classes': ('collapse', 'collapsed'), 'fields': (('gerant_nom', 'gerant_prenom'), 'gerant_adresse1', 'gerant_adress2', ('gerant_ville', 'gerant_code_postal'), 'gerant_pays', 'gerant_email', 'gerant_telephone', 'password') }),
        (None, { 'description': '<div id="autre"></div>', 'fields': ('verrou', ) }),

    )
    actions = ['send_mails', 'export', 'do_paiement', 'lock', 'unlock']
    search_fields = ('numero', 'nom', 'club', 'gerant_nom', 'gerant_prenom', 'equipier__nom', 'equipier__prenom')
    list_per_page = 500

    def documents_manquants2(self, obj):
        return (len(obj.licence_manquantes()) + len(obj.certificat_manquantes()) + len(obj.autorisation_manquantes())) or ''
    documents_manquants2.short_description = u'✉'

    def paiement_complet2(self, obj):
        span = '<span title="%(title)s">%(text)s</span>';
        return mark_safe(span % {
            'text': obj.paiement_complet() and ICON_OK or ICON_KO,
            'title': '%s / %s €' % (obj.montant_paiements, obj.prix),
        })
    paiement_complet2.allow_tags = True
    paiement_complet2.short_description = '€'
    
    def nombre2(self, obj):
        return obj.nombre
    nombre2.short_description = u'☺'

    def dossier_complet_auto2(self, obj):
        ret = ''
        if obj.verrou:
            ret = ICON_LOCK
        if obj.verifier():
            return ICON_CHECK + ret
        auto = obj.dossier_complet_auto()
        if auto:
            return ICON_OK + ret
        if auto == False:
            return ICON_KO + ret
        return ICON_MISSING + ret
    dossier_complet_auto2.allow_tags = True
    dossier_complet_auto2.short_description = mark_safe(ICON_OK)

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            url(r'^send/$', self.send_mails, name='equipe_send_mails'),
            url(r'^export/$', self.export, name='equipe_send_mails'),
            url(r'^send/preview/$', self.preview_mail, name='equipe_preview_mail'),
            url(r'^(?P<id>\d+)/send/(?P<template>.*)/$', self.send_mail, name='equipe_send_mail'),
            url(r'^(?P<id>\d+)/autre/$', self.autre, name='equipe_autre'),
        ]
        return my_urls + urls

    def send_mail(self, request, id, template):
        request.current_app = self.admin_site.name
        instance = get_object_or_404(Equipe, id=id)

        if request.method == 'POST':
            mail = Mail(
                course=instance.course,
                template=None,
                equipe=instance,
                emetteur=request.POST['sender'],
                destinataires=[ request.POST['mail'], ],
                bcc=[],
                sujet=request.POST['subject'],
                message=request.POST['message'],
            )
            mail.send()
            messages.add_message(request, messages.INFO, u'Message envoyé à %s' % (request.POST['mail'], ))
            return redirect('/course/inscriptions/equipe/%s/' % (instance.id, ))


        template = get_object_or_404(TemplateMail, id=template)
        sujet = ''
        message = ''
        try:
            context = Context({
                "instance": instance,
                'ROOT_URL': 'https://%s' % Site.objects.get_current(),
            })
            sujet   = Template(template.sujet).render(context)
            message = Template(template.message).render(context)
        except Exception as e:
            message = '<p style="color: red">Error in template: %s</p>' % str(e)

        return TemplateResponse(request, 'admin/equipe/send_mail.html', dict(self.admin_site.each_context(request),
            message=message,
            sender=instance.course.email_contact,
            mail=instance.gerant_email,
            subject=sujet,
        ))

    def preview_mail(self, request):
        instance = get_object_or_404(Equipe, id=request.GET['id'])

        mail = get_object_or_404(TemplateMail, id=request.GET['template'])
        sujet = ''
        message = ''
        try:
            context = Context({
                "instance": instance,
                'ROOT_URL': 'https://%s' % Site.objects.get_current(),
            })
            sujet   = Template(mail.sujet).render(context)
            message = Template(mail.message).render(context)
        except Exception as e:
            message = '<p style="color: red">Error in template: %s</p>' % str(e)

        return HttpResponse(json.dumps({
            'mail': instance.gerant_email,
            'subject': sujet,
            'message': message,
        }))

    def send_mails(self, request, queryset=None):
        request.current_app = self.admin_site.name
        course = getCourse(request)

        if 'template' in request.POST and 'ids' in request.POST:
            ids = json.loads(request.POST['ids'])
            mail = get_object_or_404(TemplateMail, id=request.POST['template'])
            equipes = Equipe.objects.filter(id__in=ids)
            mail.send(equipes)
            messages.add_message(request, messages.INFO, u'Message envoyé à %d équipes' % (len(equipes), ))
            return redirect('/course/inscriptions/equipe/')

        return TemplateResponse(request, 'admin/equipe/send_mails.html', dict(self.admin_site.each_context(request),
            queryset=queryset,
            templates=TemplateMail.objects.filter(course=course),
        ))
    send_mails.short_description = _(u'Envoyer un mail groupé')

    def export(self, request, queryset=None):
        request.current_app = self.admin_site.name
        course = getCourse(request)

        fields = {
            'equipe.%s' % field.name: '%s - %s' % (_('Equipe'), field.verbose_name or field.name)
            for field in Equipe._meta.get_fields()
            if not field.one_to_many and field.name not in ('id', 'course', 'gerant_ville2', 'categorie', 'extra')
        }
        fields.update({
            'equipe.extra%d' % extra.id: '%s - %s' % (_('Equipe'), extra.label)
            for extra in course.extra.filter(page__in=('Equipe', 'Categorie'))
        })
        fields.update({
            'equipier.%s' % field.name: '%s - %s' % (_('Equipier'), field.verbose_name or field.name)
            for field in Equipier._meta.get_fields()
            if not field.one_to_many and field.name not in ('id', 'equipe', 'ville2', 'extra', 'participations') and hasattr(field, 'verbose_name')
        })
        fields.update({
            'equipier.extra%d' % extra.id: '%s - %s' % (_('Equipier'), extra.label)
            for extra in course.extra.filter(page='Equipier')
        })

        if 'ids' in request.POST:
            objet = request.POST['objet']
            delimiter = request.POST.get('delimiter', ';')
            encoding = request.POST.get('encoding', 'utf-8')
            name = request.POST.get('name', objet)
            header = request.POST.get('header', 'yes')
            ids = json.loads(request.POST['ids'])
            if objet == 'equipes':
                objects = Equipe.objects.filter(course=course)
                if len(ids):
                    objects = objects.filter(id__in=ids)
            else:
                objects = Equipier.objects.filter(equipe__course=course, numero__lte=F('equipe__nombre'))
                if len(ids):
                    objects = objects.filter(equipe_id__in=ids)
            response = HttpResponse(content_type='text/csv', charset=encoding)
            response['Content-Disposition'] = 'attachment; filename=%s.csv' % name

            writer = csv.writer(response, delimiter=delimiter)
            def resolve(obj, field):
                field = field.split('.')
                if isinstance(obj, Equipier) and field[0] == 'equipe':
                    obj = obj.equipe
                if field[1].startswith('extra'):
                    return (str(obj.extra[field[1]]) if field[1] in obj.extra else '')
                v = getattr(obj, field[1])
                if inspect.ismethod(v):
                    return str(v())
                return str(v)
            
            fieldnames = [ f for f in request.POST.getlist('colonnes') if objet == 'equipiers' or f.startswith('equipe.') ]

            if header:
                writer.writerow([ fields[f] for f in fieldnames ])
            for obj in objects:
                writer.writerow([
                    resolve(obj, field).encode(encoding, 'replace').decode(encoding) 
                    for field in fieldnames])

            return response
        
        queryset = queryset or Equipe.objects.none()

        return TemplateResponse(request, 'admin/equipe/export.html', dict(self.admin_site.each_context(request),
            queryset=queryset,
            equipes=queryset.count() or course.equipe_set.count(),
            equipiers=queryset.aggregate(Sum('nombre'))['nombre__sum'] or course.equipe_set.aggregate(Sum('nombre'))['nombre__sum'] or 0,
            course=course,
            fields=fields,
        ))
    export.short_description = _(u'Exporter')

    def autre(self, request, id):
        request.current_app = self.admin_site.name
        instance = get_object_or_404(Equipe, id=id)
        return TemplateResponse(request, 'admin/equipe/autre.html', dict(self.admin_site.each_context(request),
            templates=instance.course.templatemail_set.all(),
            instance=instance,
            mail_error=instance.mail_set.filter(error__isnull=False).count(),
        ))

    def do_paiement(self, request, queryset=None):
        return HttpResponseRedirect('../paiement/add/?' + '&'.join([ 'equipe_id=%d' % equipe.id for equipe in queryset ]))
    do_paiement.short_description = _(u'Paiement reçu')

    def lock(self, request, queryset=None):
        queryset.update(verrou=True)
        return HttpResponseRedirect(request.META['HTTP_REFERER'])
    lock.short_description = _(u'Verrouiller')

    def unlock(self, request, queryset=None):
        queryset.update(verrou=False)
        return HttpResponseRedirect(request.META['HTTP_REFERER'])
    unlock.short_description = _(u'Déverrouiller')


#main_site.disable_action('delete_selected')
site.register(Equipe, EquipeAdmin)

class CourseAdmin(admin.ModelAdmin):
    class Media:
        js = ('custom_admin/course.js', )
    exclude = ('active', )
    def get_fieldsets(self, request, obj=None):
        return (
            (None, {
                'classes': ('wide', 'extrapretty'),
                'fields': self.get_fields(request, obj),
            }),
        )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        course_uid = request.COOKIES['course_uid']
        qs = qs.filter(uid=course_uid)
        if not request.user.is_superuser:
            qs = qs.filter(accreditations__user=request.user)
        return qs

    def changelist_view(self, request):
        return self.change_view(request, str(self.get_queryset(request)[0].id))

    def get_form(self, request, obj=None, **kwargs):
        if obj == None:
            return CourseForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        obj.save()
        if not change:
            obj.accreditations.create(user=request.user, role='admin')
            messages.add_message(request, messages.INFO, u"Course créée. Vous recevrez un message dès qu'elle sera activée.")

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue=post_url_continue)
        response = HttpResponseRedirect('/course/')
        response.set_cookie('course_uid', obj.uid)
        response.set_cookie('course_id',  obj.id)
        response.set_cookie('course_nom', obj.nom)
        return response

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            url(r'^models/$', self.get_models, name='models'),
        ]
        return my_urls + urls

    def get_models(self, request):
        models = {}
        with (Path(settings.PACKAGE_ROOT) / 'static' / 'course_models.json').open() as f:
            models = json.load(f)
        for course in Course.objects.filter(accreditations__user=request.user):
            models[course.id] = {
                '_name': str(course),
                'categories': [
                    {
                        'code': cat.code,
                        'nom': cat.nom,
                        'prix1': str(cat.prix1),
                        'prix2': str(cat.prix2),
                    } for cat in course.categories.all()
                ],
            }
            
        return HttpResponse(json.dumps(models))

site.register(Course, CourseAdmin)


class CategorieAdmin(CourseFilteredObjectAdmin):
    class Media:
        js = ('custom_admin/categorie.js', )
    list_display = ('code', 'nom', 'min_equipiers', 'max_equipiers', 'min_age', 'sexe', 'numero_debut', 'numero_fin', )
site.register(Categorie, CategorieAdmin)


class TemplateMailAdmin(CourseFilteredObjectAdmin):
    class Media:
        js  = ('https://tinymce.cachefly.net/4.0/tinymce.min.js', 'custom_admin/templatemail.js', )
    list_display = ('nom', 'sujet', )
site.register(TemplateMail, TemplateMailAdmin)


class AccreditationAdmin(CourseFilteredObjectAdmin):
    list_display = ('user_name', 'user_email', 'role', 'active', )
    fields = ('user_name', 'user_email', 'role', )
    readonly_fields = ('user_name', 'user_email', )

    def active(self, obj):
        return obj.role != '' and ICON_OK or ICON_KO
    active.allow_tags = True

    def user_name(self, obj):
        return obj.user.username

    def user_email(self, obj):
        return mark_safe('<a href="mailto:%s">%s</a>' % (obj.user.email, obj.user.email))
    user_email.allow_tags = True

    def has_add_permission(self, request):
        return False
site.register(Accreditation, AccreditationAdmin)

class EquipeFilter(SimpleListFilter):
    title = _(u'Equipes')
    parameter_name = 'equipe'
    def lookups(self, request, model_admin):
        return [
            (e.id, u'%s - %s - %s' % (e.numero, e.nom, e.categorie.code))
            for e in Equipe.objects.select_related('categorie').filter(course__uid=request.COOKIES['course_uid']).order_by('numero')
        ]
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(equipe__id=self.value())
        return queryset

class TemplateMailFilter(SimpleListFilter):
    title = _(u'Modèle')
    parameter_name = 'template'
    def lookups(self, request, model_admin):
        return [('', _('Aucun'))] + [
            (t.id, t.nom)
            for t in TemplateMail.objects.filter(course__uid=request.COOKIES['course_uid']).order_by('nom')
        ]
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(template__id=self.value())
        return queryset

class MailAdmin(CourseFilteredObjectAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('equipe__categorie', 'equipe__course', 'template')
        return qs

    list_display = ('date', 'equipe', 'sujet', 'template', 'status')
    fields = ('equipe', 'template', 'date', 'emetteur', 'destinataires', 'bcc', 'sujet', 'read', 'error', 'message')
    readonly_fields = ('equipe', 'template', 'date', 'emetteur', 'destinataires', 'bcc', 'sujet', 'read', 'error', 'message')
    list_filter = [EquipeFilter, TemplateMailFilter, 'date']
    class Media:
        js = ('custom_admin/mail.js', )
    def status(self, obj):
        if obj.read:
            return ICON_OK
        if obj.error:
            return ICON_KO
        return ''
    status.allow_tags = True
    status.short_description = mark_safe(ICON_OK)
site.register(Mail, MailAdmin)

class ExtraQuestionChoiceInline(admin.TabularInline):
    model = ExtraQuestionChoice
    extra = 0
    max_num = 20
    fields = ('label', 'price1', 'price2', )

class ExtraQuestionAdmin(CourseFilteredObjectAdmin):
    class Media:
        js = ('custom_admin/extraquestion.js', )
    fields = ('course', 'page', 'type', 'label', 'help_text', 'required', 'price1', 'price2', )
    list_display = ('label', 'page', 'type', )
    inlines = [ ExtraQuestionChoiceInline ]
site.register(ExtraQuestion, ExtraQuestionAdmin)

class PaiementRepartitionInline(admin.TabularInline):
    model = PaiementRepartition
    extra = 0
    max_num = 20
    fields = ('course', 'equipe_numero', 'equipe_nom', 'prix', 'paye', 'reste', 'montant', )
    readonly_fields = ('course', 'equipe_numero', 'equipe_nom', 'prix', 'paye', 'reste', )
    def course(self, obj):
        return obj.equipe.course.nom
    def equipe_numero(self, obj):
        return obj.equipe.numero
    def equipe_nom(self, obj):
        return obj.equipe.nom
    def prix(self, obj):
        return obj.equipe.prix

class PaiementEquipeFilter(SimpleListFilter):
    title = _('Equipe')
    parameter_name = 'equipe_id'
    def lookups(self, request, model_admin):
        if self.value():
            return (
                (self.value(), Equipe.objects.get(id=self.value())),
            )
        return ()
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(equipes__equipe__id=self.value())
        return queryset

class PaiementAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        course_uid = request.COOKIES['course_uid']
        qs = qs.filter(equipes__equipe__course__uid=course_uid).distinct()
        if not request.user.is_superuser:
            qs = qs.filter(equipes__equipe__course__accreditations__user=request.user)
        qs = qs.prefetch_related(Prefetch('equipes', PaiementRepartition.objects.select_related('equipe', 'equipe__course', 'equipe__categorie')))
        return qs
    fields = ('montant', 'type', 'date', 'detail', )
    readonly_fields = ('date', )
    list_display = ('equipes', 'montant', 'type', 'date', )
    list_filter = ('type', PaiementEquipeFilter, )
    inlines = [ PaiementRepartitionInline ]

    def equipes(self, obj):
        #TODO hide course if t's the current one
        equipes = list(obj.equipes.all())
        if len(equipes) == 1:
            return str(equipes[0].equipe)
        courses = defaultdict(lambda: [])
        for e in equipes:
            courses[e.equipe.course.uid].append(str(e.equipe.numero))
        if len(equipes) < 4:
            return ', '.join('%s: [%s]' % (uid, ', '.join(numeros)) for uid, numeros in courses.items())
        return str(len(equipes))

site.register(Paiement, PaiementAdmin)
