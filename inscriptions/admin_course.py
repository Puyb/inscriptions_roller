# -*- coding: utf-8 -*-
from inscriptions.models import *
from django.contrib import admin
from django.core.mail import EmailMessage
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template import Template, Context
from django.template.response import TemplateResponse
from django.contrib import messages
from django.db.models import Sum, Value, F, Q, Max
from django.db.models.functions import Coalesce
from django.db.models.query import prefetch_related_objects
from django.utils.translation import ugettext_lazy as _
from django.contrib.admin import SimpleListFilter
from django.http import HttpResponseRedirect
from django.conf import settings
from .forms import CourseForm, ImportResultatForm
from .utils import ChallengeUpdateThread
from account.views import LogoutView
from datetime import datetime, timedelta
import json
import re
from Levenshtein import distance
import csv, io
import inspect

ICON_OK = '✅'
ICON_KO = '🚫'
ICON_CHECK = '❔'
ICON_MISSING = '✉'

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
        print(request.path)
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
            url(r'^resultats/$', self.admin_view(self.resultats), name='course_resultats'),
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

    def course_ask_accreditation(self, request, course_uid=None):
        request.current_app = self.name
        if course_uid:
            course = get_object_or_404(Course, uid=course_uid)
            Accreditation(
                user=request.user,
                course=course,
            ).save()
            messages.add_message(request, messages.INFO, u'Demande d\'accreditation pour la course "%s" envoyée. Vous serez prévenu quand elle sera activée.' % (course.nom, ))
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
        equipiers = list(Equipier.objects.filter(equipe__course=course).select_related('equipe__categorie'))

        doublons = []
        for i, e in enumerate(equipiers):
            if e.numero > e.equipe.nombre:
                continue
            dbl = []
            for j in range(i + 1, len(equipiers)):
                e2 = equipiers[j]
                if e2.numero > e2.equipe.nombre:
                    continue
                if distance((e.nom + ' ' + e.prenom).lower(), (e2.nom + ' ' + e2.prenom).lower()) < 3:
                    dbl.append(e2)
            if dbl:
                dbl.insert(0, e)
                doublons.append(dbl)

        return TemplateResponse(request, 'admin/anomalies.html', dict(self.each_context(request),
            doublons=doublons,
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

                                for row in csv_reader:
                                    numero = int(g(row, 'dossard_column'))
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
                                        if data['time_format'] == 'HMS':
                                            s = re.split('[^0-9.,]+', g(row, 'time_column').strip())
                                            time = Decimal(0)
                                            n = Decimal(1)
                                            while len(s):
                                                time += n * Decimal(s.pop().replace(',', '.'))
                                                n *= Decimal(60)
                                        else:
                                            time = Decimal(g(row, 'time_column'))
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
        return TemplateResponse(request, 'admin/import_resultat_form.html', dict(self.each_context(request),
            course=course,
            form=form,
        ))




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

HELP_TEXT = """
<ul>
    <li>
        Réception d'un chèque : 
        <ol>
            <li>saisissez le montant du chèque dans la case 'Paiement reçu'.</li>
            <li>Au besoin, vous pouvez saisir une information complétentaire dans la case 'Détails'</li>
        </ol>
    </li>
    <li>
        Réception d'un certificat médical :
        <ol>
            <li>Identifier à quel équipier il se rapporte</li>
            <li>Vérifiez sa date et s'il autorise la pratique du roller en compétition</li>
            <li>Modifiez la case 'Certificat ou licence valide' de 'Inconnu' à 'Oui' ou 'Non' selon le cas</li>
        </ol>
    </li>
    <li>
        Réception d'une licence FFRS :
        <ol>
            <li>Identifier à quel équipier il se rapporte</li>
            <li>Vérifiez qu'elle est en cours de validité et qu'elle comporte la mention 'competition'</li>
            <li>Modifiez la case 'Certificat ou licence valide' de 'Inconnu' à 'Oui' ou 'Non' selon le cas</li>
        </ol>
    </li>
    <li>
        Réception d'une autorisation parentale :
        <ol>
            <li>Identifier à quel équipier il se rapporte</li>
            <li>Vérifiez qu'elle est valide</li>
            <li>Modifiez la case 'Autorisation parentale' de 'Inconnu' à 'Oui' ou 'Non' selon le cas</li>
        </ol>
    </li>
</ul>
<p>Au besoin, vous pouvez saisir des informations complémentaires dans la case 'commentaires'.</p>
<p>Une fois terminer, cliquer sur le bouton 'Enregistrer' en bas de page.</p>
"""

class EquipierInline(admin.StackedInline):
    model = Equipier
    extra = 0
    max_num = 5
    readonly_fields = [ 'nom', 'prenom', 'sexe', 'adresse1', 'adresse2', 'ville', 'code_postal', 'pays', 'email', 'date_de_naissance', 'autorisation', 'justificatif', 'num_licence', 'piece_jointe', 'age']
    fieldsets = (
        (None, { 'fields': (('nom', 'prenom', 'sexe'), ) }),
        (u'Coordonnées', { 'classes': ('collapse', 'collapsed'), 'fields': ('adresse1', 'adresse2', ('ville', 'code_postal'), 'pays', 'email') }),
        (None, { 'classes': ('wide', ), 'fields': (('date_de_naissance', 'age', ), ('autorisation_valide', 'autorisation'), ('justificatif', 'num_licence', ), ('piece_jointe_valide', 'piece_jointe')) }),
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
    title = _('Paiement complet')
    parameter_name = 'paiement_complet'
    def lookups(self, request, model_admin):
        return (
            ('paye', _(u'Payé')),
            ('impaye', _(u'Impayé')),
        )
    def queryset(self, request, queryset):
        if self.value() == 'paye':
            return queryset.filter(paiement__gte=F('prix'))
        if self.value() == 'impaye':
            return queryset.filter(Q(paiement__isnull=True) | Q(paiement__lt=F('prix')))
        return queryset

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

class EquipeAdmin(CourseFilteredObjectAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.prefetch_related('equipier_set')
        qs = qs.annotate(
            verifier_count = Coalesce(Sum(Case(When(equipier__verifier=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
            valide_count   = Coalesce(Sum(Case(When(equipier__valide=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
            erreur_count   = Coalesce(Sum(Case(When(equipier__erreur=True, then=Value(1)), default=Value(0), output_field=models.IntegerField())), Value(0)),
        )
        return qs

    class Media:
        css = {"all": ("admin.css",)}
        js = ('custom_admin/equipe.js', )
    readonly_fields = [ 'numero', 'nom', 'club', 'gerant_nom', 'gerant_prenom', 'gerant_adresse1', 'gerant_adress2', 'gerant_ville', 'gerant_code_postal', 'gerant_pays', 'gerant_telephone', 'categorie', 'nombre', 'prix', 'date', 'password', 'date']
    list_display = ['numero', 'categorie', 'nom', 'club', 'gerant_email', 'date', 'nombre2', 'paiement_complet2', 'documents_manquants2', 'dossier_complet_auto2']
    list_display_links = ['numero', 'categorie', 'nom', 'club', ]
    list_filter = [PaiementCompletFilter, StatusFilter, CategorieFilter, 'nombre', 'date']
    ordering = ['-date', ]
    inlines = [ EquipierInline ]

    fieldsets = (
        ("Instructions", { 'description': HELP_TEXT, 'classes': ('collapse', 'collapsed'), 'fields': () }),
        (None, { 'fields': (('numero', 'nom', 'club'), ('categorie', 'nombre', 'date'), ('paiement', 'prix', 'paiement_info'), 'commentaires')}),
        (u'Gérant', { 'classes': ('collapse', 'collapsed'), 'fields': (('gerant_nom', 'gerant_prenom'), 'gerant_adresse1', 'gerant_adress2', ('gerant_ville', 'gerant_code_postal'), 'gerant_pays', 'gerant_email', 'gerant_telephone', 'password') }),
        (None, { 'description': '<div id="autre"></div>', 'fields': ('verrou', ) }),

    )
    actions = ['send_mails', 'export']
    search_fields = ('numero', 'nom', 'club', 'gerant_nom', 'gerant_prenom', 'equipier__nom', 'equipier__prenom')
    list_per_page = 500

    def documents_manquants2(self, obj):
        return (len(obj.licence_manquantes()) + len(obj.certificat_manquantes()) + len(obj.autorisation_manquantes())) or ''
    documents_manquants2.short_description = u'✉'

    def paiement_complet2(self, obj):
        return obj.paiement_complet() and ICON_OK or ICON_KO
    paiement_complet2.allow_tags = True
    paiement_complet2.short_description = '€'
    
    def nombre2(self, obj):
        return obj.nombre
    nombre2.short_description = u'☺'

    def dossier_complet_auto2(self, obj):
        if obj.verifier():
            return ICON_CHECK
        auto = obj.dossier_complet_auto()
        if auto:
            return ICON_OK
        if auto == False:
            return ICON_KO
        return ICON_MISSING
    dossier_complet_auto2.allow_tags = True
    dossier_complet_auto2.short_description = mark_safe(ICON_OK)

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        from django.conf.urls import url
        urls = super().get_urls()
        my_urls = [
            url(r'^version/$', self.version, name='equipe_version'),
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
                emeteur=request.POST['sender'],
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
                'ROOT_URL': 'http://%s' % Site.objects.get_current(),
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
                'ROOT_URL': 'http://%s' % Site.objects.get_current(),
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

    def version(self, request):
        import django
        return HttpResponse(django.__file__ + ' ' + json.dumps(list(django.VERSION)))

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
            if not field.one_to_many and field.name not in ('id', 'equipe', 'ville2', 'extra')
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
                objects = Equipier.objects.filter(equipe__course=course)
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
                    return obj.extra[field[1]]
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
            equipiers=Equipier.objects.filter(equipe__in=queryset).count() or Equipier.objects.filter(equipe__course=course).count(),
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
        ))



#main_site.disable_action('delete_selected')
site.register(Equipe, EquipeAdmin)

class CourseAdmin(admin.ModelAdmin):
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
        return '<a href="mailto:%s">%s</a>' % (obj.user.email, obj.user.email)
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

    list_display = ('date', 'equipe', 'sujet', 'template')
    fields = ('equipe', 'template', 'date', 'emeteur', 'destinataires', 'bcc', 'sujet', 'message')
    readonly_fields = ('equipe', 'template', 'date', 'emeteur', 'destinataires', 'bcc', 'sujet', 'message')
    list_filter = [EquipeFilter, TemplateMailFilter, 'date']
    class Media:
        js = ('custom_admin/mail.js', )
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
