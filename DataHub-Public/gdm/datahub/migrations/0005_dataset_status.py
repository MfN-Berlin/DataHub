# Generated by Django 4.1.5 on 2023-03-22 10:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datahub', '0004_alter_dataset_integrated'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='status',
            field=models.CharField(blank=True, max_length=1000, null=True, verbose_name='Latest Status of Integration'),
        ),
    ]
