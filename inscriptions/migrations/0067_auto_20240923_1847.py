# Generated by Django 2.0 on 2024-09-23 16:47

from django.db import migrations

def populate_prices(apps, schema_editor):
    Course = apps.get_model('inscriptions', 'Course')
    for course in Course.objects.all():
        course.dates_augmentation = [ course.date_augmentation ]
        course.save()
    Categorie = apps.get_model('inscriptions', 'Categorie')
    for categorie in Categorie.objects.all():
        categorie.prices = list(filter(lambda x: x is not None, [ categorie.prix1, categorie.prix2 ]))
        categorie.save()
    ExtraQuestion = apps.get_model('inscriptions', 'ExtraQuestion')
    for extra_question in ExtraQuestion.objects.all():
        extra_question.prices = list(filter(lambda x: x is not None, [ extra_question.price1, extra_question.price2 ]))
        extra_question.save()
    ExtraQuestionChoice = apps.get_model('inscriptions', 'ExtraQuestionChoice')
    for extra_question_choice in ExtraQuestionChoice.objects.all():
        extra_question_choice.prices = list(filter(lambda x: x is not None, [ extra_question_choice.price1, extra_question_choice.price2 ]))
        extra_question_choice.save()

class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0066_auto_20240923_1847'),
    ]

    operations = [
        migrations.RunPython(populate_prices),
    ]
