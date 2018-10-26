# -*- coding: utf-8 -*-
import sys, requests, random, json
import logging
from datetime import datetime, date
from functools import reduce
from collections import defaultdict
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage
from django.urls import reverse
from django.db import transaction
from django.db.models import Count, Sum, Min, F, Q, Prefetch, Value, CharField, DecimalField, Case, When
from django.db.models.functions import Coalesce, Concat
from django.db.models.query import prefetch_related_objects
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template import Template, Context
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from .decorators import open_closed
from .forms import EquipeForm, EquipierFormset, ContactForm
from .models import Equipe, Equipier, Categorie, Course, NoPlaceLeftException, TemplateMail, ExtraQuestion, Challenge, ParticipationChallenge, EquipeChallenge, ParticipationEquipier, CompareNames
from .utils import MailThread, jsonDate
from django_countries.data import COUNTRIES

logger = logging.getLogger(__name__)

@open_closed
@transaction.atomic
def form(request, course_uid, numero=None, code=None):
    EQ = ExtraQuestion.objects.prefetch_related('choices')
    course = get_object_or_404(Course.objects.prefetch_related(
            Prefetch('extra', queryset=EQ.filter(page__in=("Equipe", "Categorie")), to_attr='extra_equipe'),
            Prefetch('extra', queryset=EQ.filter(page="Equipier"), to_attr='extra_equipier'),
            'categories',
        ).annotate(min_age=Min('categories__min_age')), uid=course_uid)
    instance = None
    old_password = None
    update = False
    equipiers_count = Equipier.objects.filter(equipe__course=course).count()
    message = ''
    if numero:
        instance = get_object_or_404(Equipe, course=course, numero=numero)
        code = code or request.COOKIES.get(instance.cookie_key(), None)
        old_password = instance.password
        if instance.password != code:
            raise Http404()
        update = True
    if request.method == 'POST':
        try:
            equipe_form = EquipeForm(request.POST, request.FILES, instance=instance, extra_questions=course.extra_equipe)
            if instance:
                equipier_formset = EquipierFormset(request.POST, request.FILES, queryset=instance.equipier_set.all(), form_kwargs={ 'extra_questions': course.extra_equipier })
            else:
                if date.today() >= course.date_fermeture or equipiers_count >= course.limite_participants:
                    if not request.user.is_staff:
                        return redirect('/')
                equipier_formset = EquipierFormset(request.POST, request.FILES, form_kwargs={ 'extra_questions': course.extra_equipier })

            if equipe_form.is_valid() and equipier_formset.is_valid():
                new_instance = equipe_form.save(commit=False)
                new_instance.course = course
                new_instance.password = old_password
                if not instance:
                    new_instance.password = '%06x' % random.randrange(0x100000, 0xffffff)
                new_instance.prix = reduce(lambda a, b: a + b['prix'], new_instance.facture(), 0)
                new_instance.save()
                for i in range(0, new_instance.nombre):
                    equipier_instance = equipier_formset.forms[i].save(commit=False)
                    equipier_instance.numero = i + 1
                    equipier_instance.equipe = new_instance
                    equipier_instance.save()
                if not instance:
                    try:
                        course.send_mail('inscription', [ new_instance ])
                    except Exception as e:
                        logging.exception('Fail to send "inscription" mail')
                    try:
                        course.send_mail('inscription_admin', [ new_instance ])
                    except Exception as e:
                        logging.exception('Fail to send "inscription_admin" mail')
                for challenge in course.challenges.all():
                    challenge.inscription_equipe(new_instance)
                response = redirect('inscriptions_done', course_uid=course.uid, numero=new_instance.numero)
                response.set_cookie(new_instance.cookie_key(), new_instance.password, max_age=365*86400, httponly=True)
                return response
            else:
                text = 'Error in form submit\n'
                text += request.META['REMOTE_ADDR'] + '\n'
                text += request.path + '\n'
                text += json.dumps(equipe_form.errors) + '\n'
                for f in equipier_formset:
                    text += json.dumps(f.errors) + '\n'
                text += json.dumps(request.POST)
                mail = EmailMessage('Error in form submit', text, settings.DEFAULT_FROM_EMAIL, [ settings.SERVER_EMAIL ], reply_to=[course.email_contact,])
                mail.content_subtype = "text"
                MailThread([ mail ]).start()
        except NoPlaceLeftException as e:
            message = _(u"Désolé, il n'y a plus de place dans cette catégorie")
        except Exception as e:
            raise e
    else:
        if not instance and 'course' in request.GET and 'numero' in request.GET:
            course2 = get_object_or_404(Course, uid=request.GET['course'])
            instance = get_object_or_404(Equipe, course=course2, numero=request.GET['numero'])
            code = request.GET.get('code',  request.COOKIES.get(instance.cookie_key(), None))
            if instance.password != code:
                raise Http404()
        equipe_form = EquipeForm(instance=instance, extra_questions=course.extra_equipe)
        if instance:
            equipier_formset = EquipierFormset(queryset=instance.equipier_set.all(), form_kwargs={ 'extra_questions': course.extra_equipier })
        else:
            equipier_formset = EquipierFormset(queryset=Equipier.objects.none(), form_kwargs={ 'extra_questions': course.extra_equipier })
        link = '<a href="%s" target="_blank">%s</a>'
        autorisation_link = link % (reverse('inscriptions_model_autorisation', kwargs={ 'course_uid': course.uid }), _("Modèle d'autorisation"))
        certificat_link   = link % (reverse('inscriptions_model_certificat',   kwargs={ 'course_uid': course.uid }), _("Modèle de certificat"))
        for equipier_form in equipier_formset:
            equipier_form.fields['date_de_naissance'].help_text = _(Equipier.DATE_DE_NAISSANCE_HELP) % { 'min_age': course.min_age, 'date': course.date }
            equipier_form.fields['autorisation'].help_text = _(Equipier.AUTORISATION_HELP) % { 'link': autorisation_link }
            equipier_form.fields['piece_jointe'].help_text = _(Equipier.PIECE_JOINTE_HELP) % { 'link': certificat_link }

    nombres_par_tranche = { e['range']: e['count'] 
            for e in course.equipe_set
                .annotate(range=Concat(
                    'categorie__numero_debut',
                    Value('-'),
                    'categorie__numero_fin',
                    output_field=CharField()
                )).values('range').annotate(count=Count('numero'))
        }
    extra_categorie = [ q.id for q in course.extra_equipe if q.page == 'Categorie' ]
    
    return TemplateResponse(request, "form.html", {
        "equipe_form": equipe_form,
        "equipier_formset": equipier_formset,
        "errors": equipe_form.errors or reduce(lambda a,b: a or b, [e.errors for e in equipier_formset]),
        "instance": instance,
        "update": update,
        "nombres_par_tranche": nombres_par_tranche,
        "equipiers_count": equipiers_count,
        "course": course,
        "message": message,
        "extra_categorie": extra_categorie,
        "is_staff": request.user.is_staff and request.user.accreditations.filter(course=course).exclude(role='').count() > 0,
    })

@open_closed
def find_challenges_categories(request, course_uid):
    EQ = ExtraQuestion.objects.prefetch_related('choices')
    course = get_object_or_404(Course.objects.prefetch_related(
            Prefetch('extra', queryset=EQ.filter(page="Equipier"), to_attr='extra_equipier'),
        ), uid=course_uid)
    if request.method != 'POST':
        return HttpResponse(status=405)
    instance = None
    if 'id' in request.POST:
        instance = get_object_or_404(Equipe, course=course, id=request.POST['instance_id'])
    equipier_formset = EquipierFormset(request.POST, form_kwargs={ 'extra_questions': course.extra_equipier })

    if not equipier_formset.is_valid():
        return HttpResponse(json.dumps(equipier_formset.errors), status=400, content_type='application/json')
    equipiers = []
    for i in range(0, int(request.POST['nombre'])):
        equipier = equipier_formset.forms[i].save(commit=False)
        equipier.numero = i + 1
        equipiers.append(equipier)

    course_categories = course.categories.filter(code__in=request.POST.getlist('categories'))
    
    all_result = defaultdict(list)
    for challenge in course.challenges.prefetch_related(Prefetch('courses', Course.objects.order_by('date'))):
        result = challenge.find_categories(equipiers, course_categories, course)
        for ec, cc in result.items():
            participations = list(challenge.find_participation_for_equipe_raw(
                    course, request.POST['nom'], equipiers, ec
                ).exclude(
                    equipes__equipe__course=course,
                    equipes__equipe=instance,
                ).prefetch_related('equipes__equipe__course'))

            ctx = {
                'challenge': challenge,
                'participation': len(participations) and participations[0],
                'nolinks': True,
                'preview': True,
            }
            all_result[ec.code].append(render_to_string("_participation.html", ctx, request=request))
    return HttpResponse(json.dumps(all_result, default=jsonDate), content_type='application/json')

@open_closed
def done(request, course_uid, numero):
    course = get_object_or_404(Course, uid=request.path.split('/')[1])
    try:
        instance = Equipe.objects.select_related('course').prefetch_related(
		'equipier_set',
                Prefetch('challenges', EquipeChallenge.objects.select_related('participation', 'participation__challenge').prefetch_related(
                    Prefetch('participation__equipes', EquipeChallenge.objects.select_related('equipe__course')),
                    Prefetch('participation__challenge__courses', Course.objects.order_by('date'))
                )),
            ).get(course=course, numero=numero)
        #prefetch_related_objects([instance], [Prefetch('equipier_set', Equipier.objects.filter(numero__lte=instance.nombre))])
        if instance.course != course:
            raise Http404()
        ctx = {
            "instance": instance,
            "url": request.build_absolute_uri(reverse(
                'inscriptions_edit', kwargs={
                    'course_uid': instance.course.uid,
                    'numero': instance.numero,
                    'code': instance.password
                }
            )),
            "paypal_ipn_url": request.build_absolute_uri(reverse('inscriptions_ipn', kwargs={'course_uid': course.uid })),
            "hour": datetime.now().strftime('%H%M'),
        }
        return TemplateResponse(request, 'done.html', ctx)
    except Equipe.DoesNotExist as e:
        raise Http404()


@csrf_exempt
def ipn(request, course_uid):
    """PayPal IPN (Instant Payment Notification)
    Cornfirms that payment has been completed and marks invoice as paid.
    Adapted from IPN cgi script provided at http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/456361"""

    try:
        if not confirm_ipn_data(request.body.decode('ascii'), settings.PAYPAL_URL):
            logger.warning('Reject ipn %s', json.dumps(request.POST))
            return HttpResponse()

        data = request.POST
        if not 'payment_status' in data or not data['payment_status'] == "Completed":
            # We want to respond to anything that isn't a payment - but we won't insert into our database.
            logger.warning('ipn is not a payment %s', json.dumps(request.POST))
            return HttpResponse()

        equipe = get_object_or_404(Equipe, id=data['invoice'][0:-4], course__uid=course_uid)
        equipe.paiement = data['mc_gross']
        equipe.paiement_info = 'Paypal %s %s' % (datetime.now(), data['txn_id'])
        equipe.save()

    except:
        logger.exception('error handling paypal ipn')

    return HttpResponse()

def confirm_ipn_data(data, PP_URL):
    # data is the form data that was submitted to the IPN URL.
    #PP_URL = 'https://www.paypal.com/cgi-bin/webscr'

    params = data + '&' + urlencode({ 'cmd': "_notify-validate" })

    response = requests.post(PP_URL, params, headers={ "Content-type": "application/x-www-form-urlencoded" })

    if response.text == "VERIFIED":
        logger.debug("PayPal IPN data verification was successful %s.", data)
    else:
        logger.debug("PayPal IPN data verification failed %s.", data)
        return False

    return True

@csrf_exempt
def check_name(request, course_uid):
    if 'nom' not in request.POST and 'id' not in request.POST:
        return HttpResponse(status=422)
    return HttpResponse(
            Equipe.objects
                .filter(course__uid=course_uid, nom__iexact=request.POST['nom'])
                .exclude(id=request.POST['id'])
                .count(),
            content_type="text/plain")

def equipe_list(request, course_uid):
    equipes = Equipe.objects.filter(course__uid=course_uid).select_related('categorie', 'gerant_ville2')
    (_('date'), _('numero'), _('nom'), _('club'), _('categorie__code'))
    return _list(course_uid, equipes, request, template='list.html', sorts=['date', 'numero', 'nom', 'club', 'categorie__code'])

def resultats(request, course_uid):
    equipes = Equipe.objects.filter(course__uid=course_uid, position_generale__isnull=False)
    (_('position_generale'), _('position_categorie'), _('numero'), _('nom'), _('categorie__code'))
    return _list(course_uid, equipes, request, template='resultats.html', sorts=['position_generale', 'position_categorie', 'numero', 'nom', 'categorie__code'])

def _list(course_uid, equipes, request, template, sorts):
    if request.GET.get('search'):
        equipes = equipes.filter(Q(nom__icontains=request.GET['search']) | Q(club__icontains=request.GET['search']))
    s = []
    if request.GET.get('by_categories') == '1':
        s.append('categorie__code')
    if request.GET.get('sort') in sorts + [ '-' + i for i in sorts ]:
        s.append(request.GET['sort'])
    else:
        s.append(sorts[0])
    equipes = equipes.order_by(*s)
    if request.GET.get('categorie'):
        equipes = equipes.filter(categorie__code=request.GET['categorie'])
    if request.GET.get('top'):
        try:
            top = int(request.GET.get('top'))
            if request.GET.get('by_categories') == '1':
                equipes = equipes.filter(position_categorie__lte=top)
            else:
                equipes = equipes.filter(position_generale__lte=top)
        except ValueError as e:
            pass

    stats = equipes.aggregate(
        count     = Count('id'),
        prix      = Sum('prix'), 
        nbpaye    = Count('paiement'), 
        paiement  = Sum('paiement'), 
        club      = Count('club', distinct=True),
        villes    = Count('gerant_ville2__nom', distinct=True),
        pays      = Count('gerant_ville2__pays', distinct=True),
    )
    stats['equipiers'] = equipes.aggregate(
        equipiers = Count('equipier'),
    )['equipiers']
    user_is_staff = (request.user and request.user.is_staff and 
        request.user.accreditations.filter(course__uid=course_uid).exclude(role='').count() > 0)
    return TemplateResponse(request, template, {
        'user_is_staff': user_is_staff,
        'stats': stats,
        'equipes': equipes,
        'sorts': sorts,
        'split_categories':  request.GET.get('by_categories') == '1',
    })

def change(request, course_uid, numero=None, sent=None):
    if numero:
        equipe = get_object_or_404(Equipe, course__uid=course_uid, numero=numero)
        if 'question' in request.POST and request.POST['question'] == '7':
            equipe.send_mail('change_request')
            return redirect('inscriptions_change_sent', course_uid=course_uid)
        return TemplateResponse(request, 'change_numero.html', {
            'equipe': equipe
        })
    equipes = Equipe.objects.filter(course__uid=course_uid).order_by('date')
    return TemplateResponse(request, 'change.html', {
        'sent': sent,
        'equipes': equipes
    })

def stats(request, course_uid):
    course = get_object_or_404(Course, uid=request.path.split('/')[1])
    stats = course.stats()

    return TemplateResponse(request, 'stats.html', {
        'stats': stats,
        'course': course,
        'json': json.dumps(stats),
    })

def stats_compare(request, course_uid, course_uid2):
    uids = [ course_uid ]
    uids.extend(course_uid2.split(','))

    align = request.GET.get('align', '')
    course1 = get_object_or_404(Course, uid=course_uid)
    duree1 = (course1.date - course1.date_ouverture).days
    if align == "augment":
        duree1 = (course1.date_augmentation - course1.date_ouverture).days

    res = []
    i = 0;
    for uid in uids:
        course = get_object_or_404(Course, uid=uid)
        stats = course.stats()
        
        duree = (course.date - course.date_ouverture).days
        if align == "augment":
            duree = (course.date_augmentation - course.date_ouverture).days

        delta = duree1 - duree
        if align == 'start':
            delta = 0
        res.append({
            'index': i,
            'stats': stats,
            'course': course,
            'json': json.dumps(stats),
            'delta': delta,
            'augment': (course.date_augmentation - course.date_ouverture).days,
        });
        i += 1;

    return TemplateResponse(request, 'stats_compare.html', {
        'data': res,
        'today': (date.today() - course1.date_ouverture).days,
        'align': request.GET.get('align', '')
    });

def index(request):
    return TemplateResponse(request, 'index.html', {
        'prochaines_courses': Course.objects.filter(active=True, date__gt=date.today()).order_by('date'),
        'anciennes_courses': Course.objects.filter(active=True, date__lte=date.today()).order_by('date'),
    })

def contact(request, course_uid):
    course = get_object_or_404(Course, uid=request.path.split('/')[1])
    name = request.POST.get('name', '')
    message = request.POST.get('message', '')
    from_email = request.POST.get('email', '')

    if message and from_email:
        message = EmailMessage('[%s] Message' % course.uid, """Nom: %s
Email: %s

%s""" % (name, from_email, message), settings.DEFAULT_FROM_EMAIL, [ course.email_contact ], reply_to=[from_email,])
        MailThread([message]).start()
        return HttpResponseRedirect('thankyou/')
    else:
        return TemplateResponse(request, 'contact.html', {'form': ContactForm()})

    return TemplateResponse(request, 'contact.html', {'form': ContactForm()})

def contact_done(request, course_uid):
    return TemplateResponse(request, 'contact_done.html')

def facture(request, course_uid, numero):
    equipe = get_object_or_404(Equipe, course__uid=course_uid, numero=numero)
    if not equipe.paiement_complet():
        raise Http404()

    if not equipe.date_facture:
        equipe.date_facture = date.today();
        equipe.save()
    tpl = TemplateMail.objects.get(nom='facture', course__uid=course_uid);
    context = Context({
        "instance": equipe,
    })
    content = Template(tpl.message).render(context)
    return TemplateResponse(request, 'facture.html', {
        'content': content,
    })

def challenges(request):
    challenges = Challenge.objects.filter(active=True).order_by('nom').prefetch_related(Prefetch('courses', Course.objects.order_by('date')))
    prochains_challenges = []
    anciens_challenges = []
    for challenge in challenges:
        if len([course for course in challenge.courses.all() if course.date > date.today()]):
            prochains_challenges.append(challenge)
        else:
            anciens_challenges.append(challenge)

    return TemplateResponse(request, 'challenges.html', {
        'prochains_challenges': prochains_challenges, 
        'anciens_challenges':   anciens_challenges,
    })

def challenge(request, challenge_uid):
    sorts = ['position2', 'count', 'nom', 'categorie__code', 'distance' ]
    (_('position2'), _('count'), _('nom'), _('categorie__code'), _('distance'))
    challenge = get_object_or_404(Challenge.objects.prefetch_related(
        Prefetch('courses', Course.objects.order_by('date')),
        'categories',
    ), uid=challenge_uid)

    participations = ParticipationChallenge.objects.filter(challenge=challenge).prefetch_related(
        Prefetch('equipes', EquipeChallenge.objects.order_by('equipe__course__date')),
        'equipes__equipe__categorie',
        'equipes__equipe__course',
        Prefetch('equipiers', ParticipationEquipier.objects.annotate(m=Min('equipiers__equipe__date')).order_by('m')),
        'equipiers__equipiers__equipe__course'
    ).select_related('categorie')
    if request.GET.get('search'):
        participations = participations.filter(Q(equipes__equipe__nom__icontains=request.GET['search']) | Q(equipes__equipe__club__icontains=request.GET['search']))
    participations = participations.annotate(
        points=Sum('equipes__points'),
        count=Count('equipes'),
        position2=Coalesce('position', 10000),
        distance=Sum(F('equipes__equipe__course__distance') * F('equipes__equipe__tours'), output_field=DecimalField())
    ).filter(count__gt=0)
    s = []
    if request.GET.get('by_categories') == '1':
        s.append('categorie__code')
    if request.GET.get('sort') in (sorts + [ '-' + i for i in sorts ]):
        if request.GET['sort'].endswith('distance'):
            if request.GET['sort'].startswith('-'):
                s.append(F('distance').desc(nulls_last=True))
            else:
                s.append(F('distance').asc(nulls_first=True))
        else:
            s.append(request.GET['sort'])
    else:
        s.append(sorts[0])
    participations = participations.order_by(*s)
    if request.GET.get('categorie'):
        participations = participations.filter(categorie__code=request.GET['categorie'])
    if request.GET.get('top'):
        participations = participations.filter(position__lte=request.GET.get('top'))

    return TemplateResponse(request, 'resultats_challenge.html', {
        'challenge': challenge,
        'participations': participations,
        'sorts': sorts,
        'split_categories':  request.GET.get('by_categories') == '1',
    })

def challenge_participation(request, challenge_uid, participation_id):
    if request.method == 'POST' and request.user.is_superuser:
        with transaction.atomic():
            participation = get_object_or_404(ParticipationChallenge, id=participation_id)
            challenge = participation.challenge
            equipe_challenge = get_object_or_404(participation.equipes.all(), equipe__course__uid=request.POST['course_uid'])
            equipe = equipe_challenge.equipe
            participation.del_equipe(equipe)
            if request.POST['participation']:
                new_participation = get_object_or_404(ParticipationChallenge.objects.filter(challenge=challenge), id=request.POST['participation'])
            else:
                new_participation = ParticipationChallenge(challenge=challenge)
                new_participation.save()
            new_participation.add_equipe(equipe, points=equipe_challenge.points)
            challenge.compute_challenge()
            return redirect('inscriptions_challenge', challenge_uid=challenge.uid)

    challenge = get_object_or_404(Challenge.objects.prefetch_related(
        Prefetch('courses', Course.objects.order_by('date')),
        'categories',
    ), uid=challenge_uid)
    participations = ParticipationChallenge.objects.prefetch_related(
        Prefetch('equipes', EquipeChallenge.objects.order_by('equipe__course__date')),
        'equipes__equipe__categorie',
        'equipes__equipe__course',
        Prefetch('equipiers', ParticipationEquipier.objects.annotate(m=Min('equipiers__equipe__date')).order_by('m')),
        'equipiers__equipiers__equipe__course'
    ).select_related('categorie')
    participations = participations.annotate(
        points=Sum('equipes__points'),
        count=Count('equipes'),
        distance=Sum(F('equipes__equipe__course__distance') * F('equipes__equipe__tours'), output_field=DecimalField())
    )
    participation = get_object_or_404(participations, id=participation_id)
    return TemplateResponse(request, 'participation_challenge.html', {
        'challenge': challenge,
        'participation': participation,
    })

def get_participations_to_move(request, challenge_uid, participation_id, course_uid):
    challenge = get_object_or_404(Challenge.objects.prefetch_related(
        Prefetch('courses', Course.objects.order_by('date')),
        'categories',
    ), uid=challenge_uid)
    course = get_object_or_404(Course, uid=course_uid)
    participation = get_object_or_404(ParticipationChallenge.objects.select_related('categorie'), id=participation_id)
    participations = ParticipationChallenge.objects.filter(
        challenge=challenge,
        categorie=participation.categorie,
    ).exclude(
        id=participation.id,
    ).exclude(
        equipes__equipe__course=course,
    ).prefetch_related(
        Prefetch('equipes', EquipeChallenge.objects.order_by('equipe__course__date')),
        'equipes__equipe__categorie',
        'equipes__equipe__course',
        Prefetch('equipiers', ParticipationEquipier.objects.annotate(m=Min('equipiers__equipe__date')).order_by('m')),
        'equipiers__equipiers__equipe__course'
    ).select_related('categorie')
    participations = participations.annotate(
        points=Sum('equipes__points'),
        count=Count('equipes'),
        distance=Sum(F('equipes__equipe__course__distance') * F('equipes__equipe__tours'), output_field=DecimalField()),
        d=CompareNames('nom', Value(participation.equipes.select_related('equipe').get(equipe__course=course).equipe.nom)),
    ).order_by('d')
    return TemplateResponse(request, 'selection_participation.html', {
        'challenge': challenge,
        'course': course,
        'participations': participations,
        'participation': participation,
    })

    
def model_certificat(request, course_uid):
    return redirect(settings.STATIC_URL + '/certificat_medical.pdf')

def live_push(request, course_uid):
    if request.method == 'POST':
        course = get_object_or_404(Course, uid=course_uid)
        date = dateTime.strptime(request.GET['date'], '%d/%m/%Y %H:%M:%S')
        snapshort = LiveSnapshort(
            course=course,
            date=date
        )
        snapshot.save()
        csv_file = request.FILES['csv']
        with io.StringIO(csv_file.read().decode('utf-8')) as io_file:
            csv_reader = csv.reader(io_file)
            for row in csv_reader:
                try:
                    # format : c.writerow([num, tours, temps, pos, meilleur_tour, penalite])
                    result = LiveResult(
                        snapshot=snapshot,
                        equipe=Equipe.objects.get(course=course, numero=row[0]),
                        tours=int(row[1]),
                        temps=Decimal(row[2]),
                        position=int(row[3]),
                        meilleur_tour=Decimal(row[4])
                    )
                    result.save()
                except Exception as e:
                    logger.exception('Error importing row %s' % row)
        return HttpResponse()

def countries(request):
    return HttpResponse(json.dumps([ [k, str(v)] for k, v in COUNTRIES.items()]), content_type='application/json')

