from django.conf import settings
from django.urls import path, register_converter
from django.urls import re_path, include
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.generic import ListView
from django.views.i18n import JavaScriptCatalog
from .models import Equipe

from inscriptions import admin
from inscriptions import views
from inscriptions import admin_views

class EditionKeyConverter:
    """« course/edition » : les deux segments d'URL qui designent une edition."""
    regex = '[^/]+/[^/]+'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(EditionKeyConverter, 'edition')

urlpatterns = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [
    path(r'admin/', admin.main_site.urls),
    re_path(r"^account/signup/$", views.SignupView.as_view(), name="account_signup"),
    re_path(r"account/", include("account.urls")),
    re_path(r'i18n/', include('django.conf.urls.i18n')),
    path(r'jsi18n/', JavaScriptCatalog.as_view(), { 'packages': 'inscriptions', 'domain': 'djangojs' }, name='javascript_catalog'),
    path(r'<edition:course_uid>/admin/', admin.course_setter, name='admin_course_setter'),
    path(r'course/', admin.course_site.urls),
]
urlpatterns += [
    path(r'', views.index, name='home'),
    path(r'organisteurs/', TemplateView.as_view(template_name='orga.html'), name='orga'),
    path(r'challenges/', views.challenges, name='inscriptions_challenges'),
    path(r'blank.gif', views.blank, name='inscriptions_blank'),
    path(r'countries.json', views.countries, name='countries'),
    path(r'challenges/<str:challenge_uid>/', views.challenge, name='inscriptions_challenge'),
    path(r'challenges/<str:challenge_uid>/<int:participation_id>/', views.challenge_participation, name='inscriptions_challenge_participation'),
    path(r'challenges/<str:challenge_uid>/<int:participation_id>/<edition:course_uid>/', views.get_participations_to_move, name='inscriptions_get_participations_to_move'),
    path(r'<edition:course_uid>/vars.js', TemplateView.as_view(template_name='vars.js')),
    path(r'<edition:course_uid>/<int:numero>/done/', views.done, name='inscriptions_done'),
    path(r'<edition:course_uid>/<int:numero>/facture/', views.facture, name='inscriptions_facture'),
    path(r'<edition:course_uid>/<int:numero>/facture/thankyou/', views.contact_done, name='contact_done'),
    path(r'<edition:course_uid>/<int:numero>/facture/<str:code>/', views.facture, name='inscriptions_facture'),
    path('<edition:course_uid>/stripe/webhook/', views.stripe_webhook, name='inscriptions_stripe_webhook'),
    path('<edition:course_uid>/helloasso/webhook/', views.helloasso_webhook, name='inscriptions_helloasso_webhook'),
    path(r'<edition:course_uid>/intent/<str:methode>/', views.intent_paiement, name='inscriptions_intent_paiement'),
    path(r'<edition:course_uid>/<int:numero>/payee/', views.equipe_payee, name='inscriptions_equipe_payee'),
    path(r'<edition:course_uid>/<int:numero>/<str:code>/', views.form, name='inscriptions_edit'),
    path(r'<edition:course_uid>/<int:numero>/', views.form, name='inscriptions_edit'),
    path(r'<edition:course_uid>/', views.form, name='inscriptions_create'),
    path(r'<edition:course_uid>/ipn/', views.ipn, name='inscriptions_ipn'),
    path(r'<edition:course_uid>/check_name/', views.check_name, name='inscriptions_check_name'),
    path(r'<edition:course_uid>/list/', views.equipe_list, name='inscriptions_list'),
    path(r'<edition:course_uid>/resultats/', views.resultats, name='inscriptions_resultats'),
    path(r'<edition:course_uid>/resultats/<int:numero>/', views.resultats_equipe, name='inscriptions_resultats_equipe'),
    path(r'<edition:course_uid>/change/<int:numero>/', views.change, name='inscriptions_change'),
    path(r'<edition:course_uid>/change/sent/', views.change, { 'sent': True }, 'inscriptions_change_sent'),
    path(r'<edition:course_uid>/change/', views.change, name='inscriptions_change'),
    path(r'<edition:course_uid>/stats/', views.stats, name='inscriptions_stats'),
    path(r'<edition:course_uid>/stats/<path:course_uid2>', views.stats_compare, name='inscriptions_stats_compare'),
    path(r'<edition:course_uid>/contact/', views.contact, name='contact'),
    path(r'<edition:course_uid>/contact/thankyou/', views.contact_done, name='contact_done'),
    path(r'<edition:course_uid>/categories/', views.categories, name='categories'),
    path(r'<edition:course_uid>/challenges/categories/', views.find_challenges_categories, name='inscriptions_find_challenges_categories'),
    path(r'<edition:course_uid>/model/certificat/', views.model_certificat, name='inscriptions_model_certificat'),
    path(r'<edition:course_uid>/model/autorisation/', TemplateView.as_view(template_name='autorisation.html'), name='inscriptions_model_autorisation'),
]
urlpatterns += [
    path(r'<edition:course_uid>/equipiers/', admin_views.equipiers, name='inscriptions_equipiers'),
    path(r'<edition:course_uid>/dossards.csv', admin_views.dossardsCSV, name='inscriptions_dossardsCSV'),
    path(r'<edition:course_uid>/dossards_equipes.csv', admin_views.dossardsEquipesCSV, name='inscriptions_dossardsEquipesCSV'),
    path(r'<edition:course_uid>/dossards_equipiers.csv', admin_views.dossardsEquipiersCSV, name='inscriptions_dossardsEquipiersCSV'),
    path(r'<edition:course_uid>/transpondeurs.csv', admin_views.transpondeursCSV, name='inscriptions_transpondeursCSV'),
    path(r'<edition:course_uid>/listing/', admin_views.listing, name='inscriptions_listing'),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        re_path(r'__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
