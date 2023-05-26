# Generated by Django 4.1.5 on 2023-04-03 13:19

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('datahub', '0008_dataset_comment_alter_dataset_datetime_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='creation_datetime',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='Dataset Creation Timestamp'),
        ),
    ]