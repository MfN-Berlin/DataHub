# Generated by Django 4.1.5 on 2023-03-23 15:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datahub', '0005_dataset_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dataset',
            name='status',
        ),
        migrations.AddField(
            model_name='dataset',
            name='stats',
            field=models.CharField(blank=True, max_length=1000, null=True, verbose_name='Latest Stats of Integration'),
        ),
    ]
