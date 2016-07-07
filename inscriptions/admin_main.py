# -*- coding: utf-8 -*-
from inscriptions.models import *
from django.contrib import admin
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import ugettext_lazy as _
from django.template.response import TemplateResponse
from .forms import ChallengeForm


site = admin.site

from django.contrib.admin.models import LogEntry
from django.utils.html import escape
from django.utils.safestring import mark_safe
class LogAdmin(admin.ModelAdmin):
    """Create an admin view of the history/log table"""
    list_display = ('action_time','user','content_type','modified_object','change_message','is_addition','is_change','is_deletion')
    list_filter = ['action_time','user','content_type']
    ordering = ('-action_time',)
    readonly_fields = [ 'user','content_type','object_id','object_repr','action_flag','change_message']
    #We don't want people changing this historical record:
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        #returning false causes table to not show up in admin page :-(
        #I guess we have to allow changing for now
        return True
    def has_delete_permission(self, request, obj=None):
        return False
    def modified_object(self, obj=None):
        if not obj:
            return ''
        return mark_safe(u'<a href="/admin/%s">%s</a>' % (
            obj.get_admin_url(),
            escape(obj.object_repr)
        ))
    modified_object.allow_tags = True
site.register(LogEntry, LogAdmin)


class CourseAdmin(admin.ModelAdmin):
    pass
site.register(Course, CourseAdmin)

class AccreditationAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'role', )
    list_filter = ('user', 'course', 'role', )
site.register(Accreditation, AccreditationAdmin)

class ChallengeCategorieInline(admin.StackedInline):
    model = ChallengeCategorie
    extra = 0
    readonly_fields = ('categories', )

    def get_formset(self, request, obj=None, **kwargs):
        # Hack! Hook parent obj just in time to use in formfield_for_manytomany
        self.parent_obj = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'categories':
            if self.parent_obj:
                kwargs['queryset'] = Categorie.objects.filter(
                    course__in=self.parent_obj.courses.all(),
                )
            else:
                kwargs['queryset'] = Categorie.objects.none()
            f = super().formfield_for_manytomany(db_field, request, **kwargs)
            f.label_from_instance = lambda x: '%s (%s) - %s (%s)' % (x.course.nom, x.course.uid, x.nom, x.code)
            return f
        return super().formfield_for_manytomany(db_field, request, **kwargs)


class ChallengeAdmin(admin.ModelAdmin):
    list_display = ('nom', )
    inlines = [ ChallengeCategorieInline,  ]
    readonly_fields = ('courses', )
    actions = ['compute_challenge', 'manage_courses']

    def get_form(self, request, obj=None, **kwargs):
        if obj == None:
            return ChallengeForm
        return super().get_form(request, obj, **kwargs)

    def get_urls(self):
        from django.conf.urls import url
        urls = super().get_urls()
        my_urls = [
            url(r'^send/$', self.manage_courses, name='challenge_courses'),
        ]
        return my_urls + urls

    def compute_challenge(self, request, queryset=None):
        for challenge in queryset:
            challenge.compute_challenge()
            messages.add_message(request, messages.INFO, _(u'Classement du challenge "%s" calculé') % (challenge.nom, ))
        return redirect('/admin/inscriptions/challenge/')
    compute_challenge.short_description = _(u'Calculer le classement')

    def manage_courses(self, request, queryset=None):
        if 'courses' in request.POST and 'challenge_id' in request.POST:
            challenge = Challenge.objects.filter(id=int(request.POST['challenge_id'])).prefetch_related('categories').get()
            challenge_categories = { c.id: c for c in challenge.categories.all() }

            courses = Course.objects.filter(id__in=request.POST.getlist('courses')).prefetch_related('categories')
            courses_by_id = { c.id: { 'course': c, 'categories': { cat.id: cat for cat in c.categories.all() } } for c in courses }
            categories = defaultdict(lambda: defaultdict(set)) # nested object, keys : Course, ChallengeCategorie, value: array of Categorie
            for key in request.POST.keys():
                key = key.split('_')
                if key[0] != 'course' and len(key) != 4:
                    continue
                course = courses_by_id.get(int(key[1]))
                if not course:
                    continue
                categorie = course['categories'].get(int(key[2]))
                challenge_categorie = challenge_categories[int(key[3])]
                categories[course['course']][challenge_categorie].add(categorie)



            for c in challenge.courses.all():
                if c not in courses:
                    challenge.courses.remove(c)
                    challenge.del_course(c)
                    messages.add_message(
                        request,
                        messages.INFO,
                        _(u'Course "%s (%s)" supprimée.') % (c.nom, c.uid),
                    )
                elif any(cat for cat in challenge.categories.all() if set(cat.categories.filter(course=c)) != categories[c][cat]):
                    equipes_skiped = challenge.add_course(c, categories[c])
                    messages.add_message(
                        request,
                        messages.WARNING if len(equipes_skiped) else messages.INFO,
                        _(u'Catégories de la course "%s (%s)" modifiées.') % (c.nom, c.uid) + (_(u' %d équipes ne correspondent à aucune catégorie') % len(equipes_skiped) if len(equipes_skiped) else ''),
                    )
            for c in courses:
                if c not in challenge.courses.all():
                    challenge.courses.add(c)
                    equipes_skiped = challenge.add_course(c, categories[c])
                    messages.add_message(
                        request,
                        messages.WARNING if len(equipes_skiped) else messages.INFO,
                        _(u'Catégories de la course "%s (%s)" modifiées.') % (c.nom, c.uid) + (_(u' %d équipes ne correspondent à aucune catégorie') % len(equipes_skiped) if len(equipes_skiped) else ''),
                    )
            challenge.compute_challenge()
            return redirect('/admin/inscriptions/challenge/')

        if len(queryset) != 1:
            messages.add_message(request, messages.ERROR, _(u'Sélectionnez une seul course'))
        challenge = queryset.prefetch_related('categories__categories').get()

        return TemplateResponse(request, 'admin/challenge/courses.html', dict(self.admin_site.each_context(request),
            challenge=challenge,
            courses=Course.objects.prefetch_related('categories'),
        ))
    manage_courses.short_description = _(u'Gérer les courses')


site.register(Challenge, ChallengeAdmin)
    
