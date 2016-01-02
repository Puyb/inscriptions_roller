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
from django.utils.translation import ugettext_lazy as _
from django.contrib.admin import SimpleListFilter
from django.http import HttpResponseRedirect
from django.conf import settings
from .forms import CourseForm
from account.views import LogoutView
import json
import re


class CourseAdminSite(admin.sites.AdminSite):
    def has_permission(self, request):
        if not request.user.is_authenticated():
            return False
        if request.path.endswith('/logout/'):
            return True
        if request.user.is_superuser:
            return True
        if request.path.endswith('/choose/') or request.path.endswith('/ask/') or re.search(r'/ask/[^/]+/$', request.path) or request.path.endswith('/inscriptions/course/add/') or request.path.endswith('/course/jsi18n/'):
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
        ] + super().get_urls()
        return urls

    def course_choose(self, request):
        request.current_app = self.name
        return TemplateResponse(request, 'admin/course_choose.html', dict(self.each_context(request),
            courses=(a.course for a in request.user.accreditations.all()),
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
        uid = request.COOKIES['course_uid']
        course = Course.objects.get(uid=uid, accreditations__user=request.user)
        
        skip = []
        
        equipier = None

        if request.method == 'POST':
            if 'skip' in request.POST and request.POST['skip'] != '':
                skip = request.POST['skip'].split(',')
            equipier = Equipier.objects.get(id=request.POST['id'])
            print('value:', request.POST['value'])
            if request.POST['value'] == 'yes' or request.POST['value'] == 'no':
                equipier.piece_jointe_valide = request.POST['value'] == 'yes'
                equipier.save()
                equipier.equipe.commentaires = request.POST['commentaires']
                equipier.equipe.save()
            else:
                skip.append(str(equipier.id))
        equipier = Equipier.objects.filter(equipe__course=course).exclude(id__in=skip).filter(verifier=True)
        print(equipier.query)

        print(equipier.count())
        if equipier.count() == 0:
            return redirect('/course/')


        return TemplateResponse(request, 'admin/document_review.html', dict(self.each_context(request),
            count=equipier.count(),
            index=len(skip) + 1,
            equipier=equipier[0],
            skip=','.join(skip)
        ))

    def listing_dossards(self, request):
        uid = request.COOKIES['course_uid']
        course = Course.objects.get(uid=uid, accreditations__user=request.user)

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

            return TemplateResponse(request, 'listing_dossards.html', { 'equipes': datas, 'keys': keys })
        return TemplateResponse(request, 'admin/listing_dossards_form.html', { 'course': course })

    index_template = 'admin/dashboard.html'


site = CourseAdminSite(name='course')

class CourseFilteredObjectAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        course_uid = request.COOKIES['course_uid']
        qs = qs.filter(course__uid=course_uid, course__accreditations__user=request.user)
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
            <li>Vérifiez s'il a été émis après le 4 août 2012 et s'il autorise la pratique du roller en compétition</li>
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
            ('verifier', _(u'À vérifier')),
            ('complet', _(u'Complet')),
            ('incomplet', _(u'Incomplet')),
            ('erreur', _(u'Erreur')),
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
        qs = qs.annotate(
            verifier_count = Coalesce(Sum('equipier__verifier'), Value(0)),
            valide_count   = Coalesce(Sum('equipier__valide'), Value(0)),
            erreur_count   = Coalesce(Sum('equipier__erreur'), Value(0)),
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
        ("Autre", { 'description': '<div id="autre"></div>', 'classes': ('collapse', 'collapsed'), 'fields': () }),

    )
    actions = ['send_mails']
    search_fields = ('numero', 'nom', 'club', 'gerant_nom', 'gerant_prenom', 'equipier__nom', 'equipier__prenom')
    list_per_page = 500

    def documents_manquants2(self, obj):
        return (len(obj.licence_manquantes()) + len(obj.certificat_manquantes()) + len(obj.autorisation_manquantes())) or ''
    documents_manquants2.short_description = u'✉'

    def paiement_complet2(self, obj):
        return obj.paiement_complet() and u"""<img alt="None" src="/static/admin/img/icon-yes.gif">""" or u"""<img alt="None" src="/static/admin/img/icon-no.gif">"""
    paiement_complet2.allow_tags = True
    paiement_complet2.short_description = '€'
    
    def nombre2(self, obj):
        return obj.nombre
    nombre2.short_description = u'☺'

    def dossier_complet_auto2(self, obj):
        if obj.verifier():
            return u"""<img alt="None" src="/static/admin/img/icon-unknown.gif">"""
        auto = obj.dossier_complet_auto()
        if auto:
            return u"""<img alt="None" src="/static/admin/img/icon-yes.gif">"""
        if auto == False:
            return u"""<img alt="None" src="/static/admin/img/icon-no.gif">"""
        return u""
    dossier_complet_auto2.allow_tags = True
    dossier_complet_auto2.short_description = mark_safe(u"""<img alt="None" src="/static/admin/img/icon-yes.gif">""")

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        from django.conf.urls import url
        urls = super().get_urls()
        my_urls = [
            url(r'^version/$', self.version, name='equipe_version'),
            url(r'^send/$', self.send_mails, name='equipe_send_mails'),
            url(r'^send/preview/$', self.preview_mail, name='equipe_preview_mail'),
            url(r'^(?P<id>\d+)/send/(?P<template>.*)/$', self.send_mail, name='equipe_send_mail'),
            url(r'^(?P<id>\d+)/autre/$', self.autre, name='equipe_autre'),
        ]
        return my_urls + urls

    def send_mail(self, request, id, template):
        request.current_app = self.admin_site.name
        instance = get_object_or_404(Equipe, id=id)

        if request.method == 'POST':
            msg = EmailMessage(request.POST['subject'], request.POST['message'], settings.DEFAULT_FROM_EMAIL, [ request.POST['mail'] ], reply_to=[request.POST['sender'],])
            msg.content_subtype = "html"
            msg.send()
            messages.add_message(request, messages.INFO, u'Message envoyé à %s' % (request.POST['mail'], ))
            return redirect('/course/inscriptions/equipe/%s/' % (instance.id, ))


        mail = get_object_or_404(TemplateMail, id=template)
        sujet = ''
        message = ''
        try:
            sujet = Template(mail.sujet).render(Context({ "course": instance.course, "instance": instance, }))
            message = Template(mail.message).render(Context({ "course": instance.course, "instance": instance, }))
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
            sujet = Template(mail.sujet).render(Context({ "course": instance.course, "instance": instance, }))
            message = Template(mail.message).render(Context({ "course": instance.course, "instance": instance, }))
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
        course = get_object_or_404(Course, uid=request.COOKIES['course_uid'], accreditations__user=request.user)

        if 'template' in request.POST and 'id' in request.POST:
            mail = get_object_or_404(TemplateMail, id=request.POST['template'])
            equipes = Equipe.objects.filter(id__in=request.POST['id'].split(','))
            mail.send(equipes)
            messages.add_message(request, messages.INFO, u'Message envoyé à %d équipes' % (len(equipes), ))
            return redirect('/course/inscriptions/equipe/')

        return TemplateResponse(request, 'admin/equipe/send_mails.html', dict(self.admin_site.each_context(request),
            queryset=queryset,
            templates=TemplateMail.objects.filter(course=course),
        ))
    send_mails.short_description = _(u'Envoyer un mail groupé')

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
        qs = qs.filter(uid=course_uid, accreditations__user=request.user)
        print(qs.query)
        return qs

    def changelist_view(self, request):
        return self.change_view(request, str(self.get_queryset(request)[0].id))

    def get_form(self, request, obj=None, **kwargs):
        if obj == None:
            return CourseForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        obj.save()
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
        js  = ('http://tinymce.cachefly.net/4.0/tinymce.min.js', 'custom_admin/templatemail.js', )
    list_display = ('nom', 'sujet', )
site.register(TemplateMail, TemplateMailAdmin)


class AccreditationAdmin(CourseFilteredObjectAdmin):
    list_display = ('user_name', 'user_email', 'role', 'active', )
    fields = ('user_name', 'user_email', 'role', )
    readonly_fields = ('user_name', 'user_email', )

    def active(self, obj):
        return obj.role != '' and u"""<img alt="None" src="/static/admin/img/icon-yes.gif">""" or u"""<img alt="None" src="/static/admin/img/icon-no.gif">"""
    active.allow_tags = True

    def user_name(self, obj):
        return obj.user.username

    def user_email(self, obj):
        return '<a href="mailto:%s">%s</a>' % (obj.user.email, obj.user.email)
    user_email.allow_tags = True

    def has_add_permission(self, request):
        return False
site.register(Accreditation, AccreditationAdmin)
