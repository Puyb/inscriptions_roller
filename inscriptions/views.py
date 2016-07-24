# -*- coding: utf-8 -*-
import sys, requests, random, traceback, json
import logging
from datetime import datetime, date
from functools import reduce
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.db.models import Count, Sum, F
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
from .functions import DayOfWeek, Hour
from .models import Equipe, Equipier, Categorie, Course, NoPlaceLeftException, TemplateMail
from .utils import MailThread

logger = logging.getLogger(__name__)

@open_closed
def form(request, course_uid, numero=None, code=None):
    course = get_object_or_404(Course, uid=course_uid)
    instance = None
    old_password = None
    equipiers_count = Equipier.objects.filter(equipe__course=course).count()
    message = ''
    if numero:
        instance = get_object_or_404(Equipe, course=course, numero=numero)
        old_password = instance.password
        if instance.password != code:
            raise Http404()
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
                        traceback.print_exc()
                    try:
                        course.send_mail('inscription_admin', [ new_instance ])
                    except Exception as e:
                        traceback.print_exc()
                return redirect('inscriptions.done', course_uid=course.uid, numero=new_instance.numero)
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
        equipe_form = EquipeForm(instance=instance)
        if instance:
            equipier_formset = EquipierFormset(queryset=instance.equipier_set.all())
        else:
            equipier_formset = EquipierFormset(queryset=Equipier.objects.none())
    date_prix2 = timezone.make_aware(datetime(2013, 6, 17), timezone.get_default_timezone())

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
        "create": not instance,
        "update": not not instance,
        "nombres_par_tranche": nombres_par_tranche,
        "equipiers_count": equipiers_count,
        "course": course,
        "message": message,
    }))

@open_closed
def done(request, course_uid, numero):
    course = get_object_or_404(Course, uid=request.path.split('/')[1])
    instance = get_object_or_404(Equipe, course=course, numero=numero)
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

def list(request, course_uid):
    stats = Equipe.objects.filter(course__uid=course_uid).aggregate(
        count     = Count('id'),
        prix      = Sum('prix'), 
        nbpaye    = Count('paiement'), 
        paiement  = Sum('paiement'), 
        club      = Count('club', distinct=True),
        villes    = Count('gerant_ville2__nom', distinct=True),
        pays      = Count('gerant_ville2__pays', distinct=True),
    )
    stats['equipiers'] = Equipe.objects.filter(course__uid=course_uid).aggregate(
        equipiers = Count('equipier'),
    )['equipiers']
    equipes = Equipe.objects.filter(course__uid=course_uid).order_by('date')
    return render_to_response('list.html', RequestContext(request, {
        'stats': stats,
        'equipes': equipes
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

    jours = [[0] * 24 for i in range(7)]
    max_jours = 0
    nb_jours = [(course.date_fermeture - course.date_ouverture).days / 7] * 7
    for i in range(7):
        n = (course.date_ouverture.weekday() + i) % 7
        if n < min(date.today(), course.date_fermeture).weekday():
            nb_jours[n] += 1
    for e in course.equipe_set.annotate(jour=DayOfWeek('date'), heure=Hour('date')).values('jour', 'heure').annotate(count=Count('id')):
        jours[e['jour']][e['heure']] = e['count'] / nb_jours[e['jour']]
        max_jours = max(max_jours, e['count'] / nb_jours[e['jour']])

    return render_to_response('stats.html', RequestContext(request, {
        'stats': stats,
        'course': course,
        'jours': jours,
        'max_jours': max_jours,
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

