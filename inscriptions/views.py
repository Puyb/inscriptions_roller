# -*- coding: utf-8 -*-
import sys, requests, random, json
import logging
from datetime import datetime, date
from functools import reduce
from collections import defaultdict
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models import Count, Sum, Min, F, Q, Prefetch
from django.db.models.functions import Coalesce
from django.db.models.query import prefetch_related_objects
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError, Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext, Template, Context
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from .decorators import open_closed
from .forms import EquipeForm, EquipierFormset, ContactForm
from .models import Equipe, Equipier, Categorie, Course, NoPlaceLeftException, TemplateMail, Challenge, ParticipationChallenge, EquipeChallenge
from .utils import MailThread, jsonDate

logger = logging.getLogger(__name__)

@open_closed
@transaction.atomic
def form(request, course_uid, numero=None, code=None):
    course = get_object_or_404(Course.objects.annotate(min_age=Min('categories__min_age')), uid=course_uid)
    instance = None
    old_password = None
    create = True
    equipiers_count = Equipier.objects.filter(equipe__course=course).count()
    message = ''
    if numero:
        instance = get_object_or_404(Equipe, course=course, numero=numero)
        code = code or request.COOKIES.get(instance.cookie_key(), None)
        old_password = instance.password
        if instance.password != code:
            raise Http404()
        create = False
    if request.method == 'POST':
        try:
            equipe_form = EquipeForm(request.POST, request.FILES, instance=instance)
            if instance:
                equipier_formset = EquipierFormset(request.POST, request.FILES, queryset=instance.equipier_set.all())
            else:
                if date.today() >= course.date_fermeture or equipiers_count >= course.limite_participants:
                    if not request.user.is_staff:
                        return redirect('/')
                equipier_formset = EquipierFormset(request.POST, request.FILES)

            if equipe_form.is_valid() and equipier_formset.is_valid():
                new_instance = equipe_form.save(commit=False)
                new_instance.course = course
                new_instance.password = old_password
                if not instance:
                    new_instance.password = '%06x' % random.randrange(0x100000, 0xffffff)
                # FIXME: price is set client side... This is really bad... I'm lazy ! Shame on me !
                #if instance and instance.categorie == new_instance.categorie and instance.prix:
                #    new_instance.prix = instance.prix
                #else:
                #    new_instance.prix = CATEGORIES[new_instance.categorie]['prix']
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
                response = redirect('inscriptions.done', course_uid=course.uid, numero=new_instance.numero)
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
            code = request.GET.get('code',  request.COOKIES.get(instance.cookie_key, None))
            if instance.password != code:
                raise Http404()
        equipe_form = EquipeForm(instance=instance)
        if instance:
            equipier_formset = EquipierFormset(queryset=instance.equipier_set.all())
        else:
            equipier_formset = EquipierFormset(queryset=Equipier.objects.none())
        link = '<a href="%s" target="_blank">%s</a>'
        autorisation_link = link % (reverse('inscriptions.model_autorisation', kwargs={ 'course_uid': course.uid }), _("Modèle d'autorisation"))
        certificat_link   = link % (reverse('inscriptions.model_certificat',   kwargs={ 'course_uid': course.uid }), _("Modèle de certificat"))
        for equipier_form in equipier_formset:
            equipier_form.fields['date_de_naissance'].help_text = _(Equipier.DATE_DE_NAISSANCE_HELP) % { 'min_age': course.min_age, 'date': course.date }
            equipier_form.fields['autorisation'].help_text = _(Equipier.AUTORISATION_HELP) % { 'link': autorisation_link }
            equipier_form.fields['piece_jointe'].help_text = _(Equipier.PIECE_JOINTE_HELP) % { 'link': certificat_link }

    nombres_par_tranche = {}
    for categorie in Categorie.objects.filter(course=course):
        key = '%d-%d' % (categorie.numero_debut, categorie.numero_fin)
        if key not in nombres_par_tranche:
            nombres_par_tranche[key] = Equipe.objects.filter(course=course, numero__gte=categorie.numero_debut, numero__lte=categorie.numero_fin).count()
    
    return render_to_response("form.html", RequestContext(request, {
        "equipe_form": equipe_form,
        "equipier_formset": equipier_formset,
        "errors": equipe_form.errors or reduce(lambda a,b: a or b, [e.errors for e in equipier_formset]),
        "instance": instance,
        "create": create,
        "update": not create,
        "nombres_par_tranche": nombres_par_tranche,
        "equipiers_count": equipiers_count,
        "course": course,
        "message": message,
    }))

@open_closed
def find_challenges_categories(request, course_uid):
    course = get_object_or_404(Course, uid=course_uid)
    if request.method != 'POST':
        return HttpResponse(status=405)
    equipier_formset = EquipierFormset(request.POST)

    if not equipier_formset.is_valid():
        return HttpResponse(json.dumps(equipier_formset.errors), status=400, content_type='application/json')
    equipiers = []
    for i in range(0, int(request.POST['nombre'])):
        equipier = equipier_formset.forms[i].save(commit=False)
        equipier.numero = i + 1
        equipiers.append(equipier)
    print(len(equipiers))

    course_categories = course.categories.filter(code__in=request.POST.getlist('categories'))
    
    all_result = defaultdict(list)
    for challenge in course.challenges.all():
        result = challenge.find_categories(equipiers, course_categories, course)
        for ec, cc in result.items():
            participations = list(challenge.find_participation_for_equipe_raw(
                    course, request.POST['nom'], equipiers, ec
                ).exclude(equipes__equipe__course=course).prefetch_related('equipes__equipe__course'))

            ctx = RequestContext(request, {
                'challenge': challenge,
                'participation': len(participations) and participations[0],
            })
            all_result[ec.code].append(render_to_string("_participation.html", ctx))
    return HttpResponse(json.dumps(all_result, default=jsonDate), content_type='application/json')

@open_closed
def done(request, course_uid, numero):
    course = get_object_or_404(Course, uid=request.path.split('/')[1])
    try:
        instance = Equipe.objects.prefetch_related(
                Prefetch('challenges', EquipeChallenge.objects.select_related('participation').prefetch_related(
                    Prefetch('participation__equipes', EquipeChallenge.objects.select_related('equipe__course'))
                )),
            ).get(course=course, numero=numero)
        #prefetch_related_objects([instance], [Prefetch('equipier_set', Equipier.objects.filter(numero__lte=instance.nombre))])
        if instance.course != course:
            raise Http404()
        ctx = RequestContext(request, {
            "instance": instance,
            "url": request.build_absolute_uri(reverse(
                'inscriptions.edit', kwargs={
                    'course_uid': course.uid,
                    'numero': instance.numero,
                    'code': instance.password
                }
            )),
            "paypal_ipn_url": request.build_absolute_uri(reverse('inscriptions.ipn', kwargs={'course_uid': course.uid })),
            "hour": datetime.now().strftime('%H%M'),
        })
        return render_to_response('done.html', ctx)
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
    return _list(equipes, request, template='list.html', sorts=['date', 'numero', 'nom', 'club', 'categorie__code'])

def resultats(request, course_uid):
    equipes = Equipe.objects.filter(course__uid=course_uid, position_generale__isnull=False)
    (_('position_generale'), _('position_categorie'), _('numero'), _('nom'), _('categorie__code'))
    return _list(equipes, request, template='resultats.html', sorts=['position_generale', 'position_categorie', 'numero', 'nom', 'categorie__code'])

def _list(equipes, request, template, sorts):
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
        if request.GET.get('by_categories') == '1':
            equipes = equipes.filter(position_categorie__lte=request.GET.get('top'))
        else:
            equipes = equipes.filter(position_generale__lte=request.GET.get('top'))

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
    return render_to_response(template, RequestContext(request, {
        'stats': stats,
        'equipes': equipes,
        'sorts': sorts,
        'split_categories':  request.GET.get('by_categories') == '1',
    }))

def change(request, course_uid, numero=None, sent=None):
    if numero:
        equipe = get_object_or_404(Equipe, course__uid=course_uid, numero=numero)
        if 'question' in request.POST and request.POST['question'] == '7':
            equipe.send_mail('change_request')
            return redirect('inscriptions.change_sent', course_uid=course_uid)
        return render_to_response('change_numero.html', RequestContext(request, {
            'equipe': equipe
        }))
    equipes = Equipe.objects.filter(course__uid=course_uid).order_by('date')
    return render_to_response('change.html', RequestContext(request, {
        'sent': sent,
        'equipes': equipes
    }))

def stats(request, course_uid):
    course = get_object_or_404(Course, uid=request.path.split('/')[1])
    stats = course.stats()

    return render_to_response('stats.html', RequestContext(request, {
        'stats': stats,
        'course': course,
        'json': json.dumps(stats),
    }))

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

    return render_to_response('stats_compare.html', RequestContext(request, {
        'data': res,
        'align': request.GET.get('align', '')
    }));

def index(request):
    return render_to_response('index.html', RequestContext(request, {
        'prochaines_courses': Course.objects.filter(active=True, date__gt=date.today()).order_by('date'),
        'anciennes_courses': Course.objects.filter(active=True, date__lte=date.today()).order_by('date'),
    }))

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
        return render_to_response('contact.html', RequestContext(request, {'form': ContactForm()}))

    return render_to_response('contact.html', RequestContext(request, {'form': ContactForm()}))

def contact_done(request, course_uid):
    return render_to_response('contact_done.html')

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
    challenges = Challenge.objects.filter(active=True).prefetch_related(Prefetch('courses', Course.objects.order_by('date')))

    return render_to_response('challenges.html', RequestContext(request, {
        'prochains_challenges': challenges.filter (courses__date__gt=date.today()).order_by('nom'),
        'anciens_challenges':   challenges.exclude(courses__date__gt=date.today()).order_by('nom'),
    }))

def challenge(request, challenge_uid):
    sorts = ['position2', 'count', 'nom', 'categorie__code']
    (_('position2'), _('count'), _('nom'), _('categorie__code'))
    challenge = get_object_or_404(Challenge.objects.prefetch_related(
        Prefetch('courses', Course.objects.order_by('date')),
        'categories',
    ), uid=challenge_uid)

    participations = ParticipationChallenge.objects.filter(challenge=challenge).prefetch_related(Prefetch('equipes', EquipeChallenge.objects.order_by('equipe__course__date')), 'equipes__equipe__categorie', 'equipes__equipe__course').select_related('categorie')
    if request.GET.get('search'):
        participations = participations.filter(Q(equipes__equipe__nom__icontains=request.GET['search']) | Q(equipes__equipe__club__icontains=request.GET['search']))
    participations = participations.annotate(nom=Min('equipes__equipe__nom'), points=Sum('equipes__points'), count=Count('equipes'), position2=Coalesce('position', 10000)).filter(count__gt=0)
    s = []
    if request.GET.get('by_categories') == '1':
        s.append('categorie__code')
    if request.GET.get('sort') in (sorts + [ '-' + i for i in sorts ]):
        s.append(request.GET['sort'])
    else:
        s.append(sorts[0])
    participations = participations.order_by(*s)
    if request.GET.get('categorie'):
        participations = participations.filter(categorie__code=request.GET['categorie'])
    if request.GET.get('top'):
        participations = participations.filter(position__lte=request.GET.get('top'))

    return render_to_response('resultats_challenge.html', RequestContext(request, {
        'challenge': challenge,
        'participations': participations,
        'sorts': sorts,
        'split_categories':  request.GET.get('by_categories') == '1',
    }))

def model_certificat(request, course_uid):
    return redirect(settings.STATIC_URL + '/certificat_medical.pdf')

def live_push(request, course_uid):
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


