# -*- coding: utf-8 -*-
from inscriptions.models import *
from django.contrib import admin


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

