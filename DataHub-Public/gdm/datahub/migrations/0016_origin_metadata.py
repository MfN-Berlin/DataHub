# Generated by Django 4.1.5 on 2023-05-16 08:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datahub', '0015_rename_dataset_id_report_dataset'),
    ]

    operations = [
        migrations.AddField(
            model_name='origin',
            name='metadata',
            field=models.JSONField(blank=True, null=True, verbose_name='Reference JSON of metadata'),
        ),
    ]