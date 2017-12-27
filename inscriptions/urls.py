from django.conf import settings
from django.urls import path
from django.conf.urls import url, include
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.generic import ListView
from django.views.i18n import JavaScriptCatalog
from .models import Equipe

from inscriptions import admin
from inscriptions import views
from inscriptions import admin_views

urlpatterns = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [
    path(r'admin/', admin.main_site.urls),
    url(r"account/", include("account.urls")),
    url(r'i18n/', include('django.conf.urls.i18n')),
    path(r'jsi18n/', JavaScriptCatalog.as_view(), { 'packages': 'inscriptions', 'domain': 'djangojs' }, name='javascript_catalog'),
    path(r'<str:course_uid>/admin/', admin.course_setter, name='admin_course_setter'),
    path(r'course/', admin.course_site.urls),
]
urlpatterns += [
    path(r'', views.index, name='home'),
    path(r'organisteurs/', TemplateView.as_view(template_name='orga.html'), name='orga'),
    path(r'challenges/', views.challenges, name='inscriptions_challenges'),
    path(r'challenges/<str:challenge_uid>/', views.challenge, name='inscriptions_challenge'),
    path(r'<str:course_uid>/vars.js', TemplateView.as_view(template_name='vars.js')),
    path(r'<str:course_uid>/<int:numero>/done/', views.done, name='inscriptions_done'),
    path(r'<str:course_uid>/<int:numero>/facture/', views.facture, name='inscriptions_facture'),
    path(r'<str:course_uid>/<int:numero>/<str:code>/', views.form, name='inscriptions_edit'),
    path(r'<str:course_uid>/<int:numero>/', views.form, name='inscriptions_edit'),
    path(r'<str:course_uid>/', views.form, name='inscriptions_create'),
    path(r'<str:course_uid>/ipn/', views.ipn, name='inscriptions_ipn'),
    path(r'<str:course_uid>/check_name/', views.check_name, name='inscriptions_check_name'),
    path(r'<str:course_uid>/list/', views.equipe_list, name='inscriptions_list'),
    path(r'<str:course_uid>/resultats/', views.resultats, name='inscriptions_resultats'),
    path(r'<str:course_uid>/change/<int:numero>/', views.change, name='inscriptions_change'),
    path(r'<str:course_uid>/change/sent/', views.change, { 'sent': True }, 'inscriptions.change_sent'),
    path(r'<str:course_uid>/change/', views.change, name='inscriptions_change'),
    path(r'<str:course_uid>/stats/', views.stats, name='inscriptions_stats'),
    path(r'<str:course_uid>/stats/<str:course_uid2>', views.stats_compare, name='inscriptions_stats_compare'),
    path(r'<str:course_uid>/contact/', views.contact, name='contact'),
    path(r'<str:course_uid>/contact/thankyou/', views.contact_done, name='contact_done'),
    path(r'<str:course_uid>/challenges/categories/', views.find_challenges_categories, name='inscriptions_find_challenges_categories'),
    path(r'<str:course_uid>/model/certificat/', views.model_certificat, name='inscriptions_model_certificat'),
    path(r'<str:course_uid>/model/autorisation/', TemplateView.as_view(template_name='autorisation.html'), name='inscriptions_model_autorisation'),
    path(r'<str:course_uid>/live/', views.live_push, name='inscriptions_live_push'),
]
urlpatterns += [
    path(r'<str:course_uid>/equipiers/', admin_views.equipiers, name='inscriptions_equipiers'),
    path(r'<str:course_uid>/dossards.csv', admin_views.dossardsCSV, name='inscriptions_dossardsCSV'),
    path(r'<str:course_uid>/dossards_equipes.csv', admin_views.dossardsEquipesCSV, name='inscriptions_dossardsEquipesCSV'),
    path(r'<str:course_uid>/dossards_equipiers.csv', admin_views.dossardsEquipiersCSV, name='inscriptions_dossardsEquipiersCSV'),
    path(r'<str:course_uid>/listing/', admin_views.listing, name='inscriptions_listing'),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
