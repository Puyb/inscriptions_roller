# Generated by Django 2.0 on 2017-12-22 01:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inscriptions', '0029_auto_20171222_0212'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtraQuestionChoice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=200, verbose_name='Label')),
                ('help_text', models.TextField(blank=True, default='', verbose_name="Texte d'aide")),
                ('price1', models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name='Prix normal')),
                ('price2', models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name='Prix augmenté')),
                ('order', models.IntegerField()),
            ],
        ),
        migrations.RemoveField(
            model_name='extraquestion',
            name='attache',
        ),
        migrations.RemoveField(
            model_name='extraquestion',
            name='options',
        ),
        migrations.AddField(
            model_name='extraquestion',
            name='help_text',
            field=models.TextField(blank=True, default='', verbose_name="Texte d'aide"),
        ),
        migrations.AddField(
            model_name='extraquestion',
            name='page',
            field=models.CharField(choices=[('Equipe', "Gerant d'équipe"), ('Equipier', 'Equipier'), ('Categorie', 'Page finale')], default='Equipe', max_length=20, verbose_name='Rattaché à'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='extraquestion',
            name='price1',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name='Prix normal'),
        ),
        migrations.AddField(
            model_name='extraquestion',
            name='price2',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name='Prix augmenté'),
        ),
        migrations.AddField(
            model_name='extraquestionchoice',
            name='question',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='choices', to='inscriptions.ExtraQuestion'),
        ),
    ]
