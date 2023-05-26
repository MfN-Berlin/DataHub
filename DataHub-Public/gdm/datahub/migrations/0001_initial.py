# Generated by Django 4.1.5 on 2023-02-09 13:55

import datahub.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datetime', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Calendar Date & Time')),
                ('CSV', models.FileField(blank=True, max_length=1000, null=True, storage=datahub.models.OverwriteStorage(), upload_to='dataset/csv/', verbose_name='CSV file')),
                ('JSON', models.JSONField(blank=True, null=True, verbose_name='JSON file')),
                ('files', models.CharField(blank=True, max_length=1000, null=True, verbose_name='image path')),
                ('params', models.CharField(blank=True, max_length=1000, null=True, verbose_name='Import Parameters')),
                ('flag', models.BooleanField(default=False, verbose_name='Automated')),
            ],
        ),
        migrations.CreateModel(
            name='OriginStatus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=1000)),
                ('flag', models.CharField(blank=True, max_length=1000, null=True, verbose_name='Tagline')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Comment')),
            ],
        ),
        migrations.CreateModel(
            name='ReportType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=1000)),
                ('flag', models.CharField(blank=True, max_length=1000, null=True, verbose_name='Tagline')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Comment')),
            ],
        ),
        migrations.CreateModel(
            name='Test',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('content', models.TextField()),
                ('published', models.DateTimeField(verbose_name='date published')),
            ],
        ),
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datetime', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Calendar Datetime')),
                ('flag', models.BooleanField(default=False, verbose_name='Done Successfully')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Comment')),
                ('dataset_id', models.ForeignKey(blank=True, help_text='The Exported Dataset', null=True, on_delete=django.db.models.deletion.SET_NULL, to='datahub.dataset', verbose_name='Dataset')),
                ('report_type_id', models.ForeignKey(blank=True, help_text='Type of the Report', null=True, on_delete=django.db.models.deletion.SET_NULL, to='datahub.reporttype', verbose_name='Report Type')),
                ('user_id', models.ForeignKey(blank=True, help_text='The user who does the operation.', null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Username')),
            ],
        ),
        migrations.CreateModel(
            name='Origin',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=1000)),
                ('logo_path', models.CharField(blank=True, max_length=1000, null=True, verbose_name='relative path to the logo in static')),
                ('link', models.CharField(blank=True, max_length=1000, null=True, verbose_name='Link to the integration initiation')),
                ('tagline', models.CharField(blank=True, max_length=1000, null=True, verbose_name='Tagline')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('active', models.BooleanField(default=False, help_text='Activates the pipeline.', verbose_name='Active?')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Comment')),
                ('origin_status_id', models.ForeignKey(blank=True, help_text='The current status of integration pipeline.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='datahub.originstatus', verbose_name='Status')),
            ],
        ),
        migrations.CreateModel(
            name='ImportLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datetime', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Calendar Datetime')),
                ('flag', models.BooleanField(default=False, verbose_name='Imported Successfully')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Comment')),
                ('dataset_id', models.ForeignKey(blank=True, help_text='The Imported Dataset', null=True, on_delete=django.db.models.deletion.SET_NULL, to='datahub.dataset', verbose_name='Dataset')),
                ('user_id', models.ForeignKey(blank=True, help_text='The user who does the operation.', null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Username')),
            ],
        ),
        migrations.AddField(
            model_name='dataset',
            name='origin_id',
            field=models.ForeignKey(blank=True, help_text='The origin of data', null=True, on_delete=django.db.models.deletion.SET_NULL, to='datahub.origin', verbose_name='Origin of the Dataset'),
        ),
        migrations.AddField(
            model_name='dataset',
            name='requester_id',
            field=models.ForeignKey(blank=True, help_text='The user who does the operation.', null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Username'),
        ),
    ]