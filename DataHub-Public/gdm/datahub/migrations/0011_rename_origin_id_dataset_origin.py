# Generated by Django 4.1.5 on 2023-04-05 09:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('datahub', '0010_rename_origin_status_id_origin_origin_status'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dataset',
            old_name='origin_id',
            new_name='origin',
        ),
    ]
