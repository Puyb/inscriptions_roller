from django.conf import settings
from django.conf.urls import patterns, include, url
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.generic import ListView
from .models import Equipe

from inscriptions import admin


urlpatterns = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [
    url(r'^admin/', include(admin.main_site.urls)),
    url(r"^account/", include("account.urls")),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^jsi18n/$', 'django.views.i18n.javascript_catalog', { 'packages': ('inscriptions',), 'domain': 'djangojs' }),
    url(r'^(?P<course_uid>[^/]+)/admin/$', admin.course_setter, name='admin_course_setter'),
    url(r'^course/', include(admin.course_site.urls)),
]
urlpatterns += [
    url(r'^$', 'inscriptions.views.index', name='home'),
    url(r'^organisteurs/$', TemplateView.as_view(template_name='orga.html'), name='orga'),
    url(r'^(?P<course_uid>[^/]+)/vars.js$', TemplateView.as_view(template_name='vars.js')),
    url(r'^(?P<course_uid>[^/]+)/(?P<numero>\d+)/done/$', 'inscriptions.views.done', name='inscriptions.done'),
    url(r'^(?P<course_uid>[^/]+)/(?P<numero>\d+)/facture/$', 'inscriptions.views.facture', name='inscriptions.facture'),
    url(r'^(?P<course_uid>[^/]+)/(?P<numero>\d+)/(?P<code>\w+)/$', 'inscriptions.views.form', name='inscriptions.edit'),
    url(r'^(?P<course_uid>[^/]+)/$', 'inscriptions.views.form', name='inscriptions.create'),
    url(r'^(?P<course_uid>[^/]+)/ipn/$', 'inscriptions.views.ipn', name='inscriptions.ipn'),
    url(r'^(?P<course_uid>[^/]+)/check_name/$', 'inscriptions.views.check_name', name='inscriptions.check_name'),
    url(r'^(?P<course_uid>[^/]+)/list/$', 'inscriptions.views.list', name='inscriptions.list'),
    url(r'^(?P<course_uid>[^/]+)/change/(?P<numero>\d+)/$', 'inscriptions.views.change', name='inscriptions.change'),
    url(r'^(?P<course_uid>[^/]+)/change/sent/$', 'inscriptions.views.change', { 'sent': True }, 'inscriptions.change_sent'),
    url(r'^(?P<course_uid>[^/]+)/change/$', 'inscriptions.views.change', name='inscriptions.change'),
    url(r'^(?P<course_uid>[^/]+)/stats/$', 'inscriptions.views.stats', name='inscriptions.stats'),
    url(r'^(?P<course_uid>[^/]+)/stats/(?P<course_uid2>[^/]+)$', 'inscriptions.views.stats_compare', name='inscriptions.stats_compare'),
    url(r'^(?P<course_uid>[^/]+)/contact/$', 'inscriptions.views.contact', name='contact'),
    url(r'^(?P<course_uid>[^/]+)/contact/thankyou/$', 'inscriptions.views.contact_done', name='contact_done'),
]
urlpatterns += [
    url(r'^(?P<course_uid>[^/]+)/equipiers/$', 'inscriptions.admin_views.equipiers', name='inscriptions.equipiers'),
    url(r'^(?P<course_uid>[^/]+)/dossards.csv$', 'inscriptions.admin_views.dossardsCSV', name='inscriptions.dossardsCSV'),
    url(r'^(?P<course_uid>[^/]+)/dossards_equipes.csv$', 'inscriptions.admin_views.dossardsEquipesCSV', name='inscriptions.dossardsEquipesCSV'),
    url(r'^(?P<course_uid>[^/]+)/dossards_equipiers.csv$', 'inscriptions.admin_views.dossardsEquipiersCSV', name='inscriptions.dossardsEquipiersCSV'),
    url(r'^(?P<course_uid>[^/]+)/listing/$', 'inscriptions.admin_views.listing', name='inscriptions.listing'),
]

