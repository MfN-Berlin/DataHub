# Generated by Django 4.1.5 on 2023-04-05 09:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('datahub', '0013_remove_dataset_requester_id'),
    ]

    operations = [
        migrations.RenameField(
            model_name='report',
            old_name='user_id',
            new_name='user',
        ),
    ]
