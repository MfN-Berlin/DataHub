# Generated by Django 4.1.5 on 2023-04-05 09:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('datahub', '0014_rename_user_id_report_user'),
    ]

    operations = [
        migrations.RenameField(
            model_name='report',
            old_name='dataset_id',
            new_name='dataset',
        ),
    ]
