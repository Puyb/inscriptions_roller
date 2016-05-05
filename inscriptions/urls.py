from django.conf import settings
from django.conf.urls import patterns, include, url
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.generic import ListView
from .models import Equipe

from inscriptions import admin
from inscriptions import views as inscriptions_views
from inscriptions import admin_views as inscriptions_admin
from django.views.i18n import javascript_catalog

urlpatterns = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [
    url(r'^admin/', include(admin.main_site.urls)),
    url(r"^account/", include("account.urls")),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^jsi18n/$', javascript_catalog, { 'packages': ('inscriptions',), 'domain': 'djangojs' }),
    url(r'^(?P<course_uid>[^/]+)/admin/$', admin.course_setter, name='admin_course_setter'),
    url(r'^course/', include(admin.course_site.urls)),
]
urlpatterns += [
    url(r'^$', inscriptions_views.index, name='home'),
    url(r'^organisteurs/$', TemplateView.as_view(template_name='orga.html'), name='orga'),
    url(r'^challenges/$', 'inscriptions.views.challenges', name='inscriptions.challenges'),
    url(r'^challenges/(?P<challenge_uid>[^/]+)/$', 'inscriptions.views.challenge', name='inscriptions.challenge'),
    url(r'^(?P<course_uid>[^/]+)/vars.js$', TemplateView.as_view(template_name='vars.js')),
    url(r'^(?P<course_uid>[^/]+)/(?P<numero>\d+)/done/$', 'inscriptions.views.done', name='inscriptions.done'),
    url(r'^(?P<course_uid>[^/]+)/(?P<numero>\d+)/facture/$', 'inscriptions.views.facture', name='inscriptions.facture'),
    url(r'^(?P<course_uid>[^/]+)/(?P<numero>\d+)/(?P<code>\w+)/$', 'inscriptions.views.form', name='inscriptions.edit'),
    url(r'^(?P<course_uid>[^/]+)/(?P<numero>\d+)/$', 'inscriptions.views.form', name='inscriptions.edit'),
    url(r'^(?P<course_uid>[^/]+)/$', 'inscriptions.views.form', name='inscriptions.create'),
    url(r'^(?P<course_uid>[^/]+)/ipn/$', 'inscriptions.views.ipn', name='inscriptions.ipn'),
    url(r'^(?P<course_uid>[^/]+)/check_name/$', 'inscriptions.views.check_name', name='inscriptions.check_name'),
    url(r'^(?P<course_uid>[^/]+)/list/$', 'inscriptions.views.equipe_list', name='inscriptions.list'),
    url(r'^(?P<course_uid>[^/]+)/resultats/$', 'inscriptions.views.resultats', name='inscriptions.resultats'),
    url(r'^(?P<course_uid>[^/]+)/change/(?P<numero>\d+)/$', 'inscriptions.views.change', name='inscriptions.change'),
    url(r'^(?P<course_uid>[^/]+)/change/sent/$', 'inscriptions.views.change', { 'sent': True }, 'inscriptions.change_sent'),
    url(r'^(?P<course_uid>[^/]+)/change/$', 'inscriptions.views.change', name='inscriptions.change'),
    url(r'^(?P<course_uid>[^/]+)/stats/$', 'inscriptions.views.stats', name='inscriptions.stats'),
    url(r'^(?P<course_uid>[^/]+)/stats/(?P<course_uid2>[^/]+)$', 'inscriptions.views.stats_compare', name='inscriptions.stats_compare'),
    url(r'^(?P<course_uid>[^/]+)/contact/$', 'inscriptions.views.contact', name='contact'),
    url(r'^(?P<course_uid>[^/]+)/contact/thankyou/$', 'inscriptions.views.contact_done', name='contact_done'),
    url(r'^(?P<course_uid>[^/]+)/challenges/categories/$', 'inscriptions.views.find_challenges_categories', name='inscriptions.find_challenges_categories'),
    url(r'^(?P<course_uid>[^/]+)/model/certificat/$', 'inscriptions.views.model_certificat', name='inscriptions.model_certificat'),
    url(r'^(?P<course_uid>[^/]+)/model/autorisation/$', TemplateView.as_view(template_name='autorisation.html'), name='inscriptions.model_autorisation'),
    url(r'^(?P<course_uid>[^/]+)/live/$', 'inscriptions.views.live_push', name='inscriptions.live_push'),
]
urlpatterns += [
    url(r'^(?P<course_uid>[^/]+)/equipiers/$', 'inscriptions.admin_views.equipiers', name='inscriptions.equipiers'),
    url(r'^(?P<course_uid>[^/]+)/dossards.csv$', 'inscriptions.admin_views.dossardsCSV', name='inscriptions.dossardsCSV'),
    url(r'^(?P<course_uid>[^/]+)/dossards_equipes.csv$', 'inscriptions.admin_views.dossardsEquipesCSV', name='inscriptions.dossardsEquipesCSV'),
    url(r'^(?P<course_uid>[^/]+)/dossards_equipiers.csv$', 'inscriptions.admin_views.dossardsEquipiersCSV', name='inscriptions.dossardsEquipiersCSV'),
    url(r'^(?P<course_uid>[^/]+)/listing/$', 'inscriptions.admin_views.listing', name='inscriptions.listing'),
    url(r'^(?P<course_uid>[^/]+)/t-shirts/$', 'inscriptions.admin_views.tshirts', name='inscriptions.tshirts'),
]

