# Generated by Django 4.1.5 on 2023-03-27 13:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datahub', '0006_remove_dataset_status_dataset_stats'),
    ]

    operations = [
        migrations.CreateModel(
            name='DatasetStatus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=1000)),
                ('flag', models.CharField(blank=True, max_length=1000, null=True, verbose_name='Tagline')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Comment')),
            ],
        ),
        migrations.AddField(
            model_name='dataset',
            name='validated',
            field=models.BooleanField(default=False, max_length=1000, verbose_name='Dataset has been validated'),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='stats',
            field=models.CharField(blank=True, max_length=1000, null=True, verbose_name='The latest stats of integration'),
        ),
        migrations.AddField(
            model_name='dataset',
            name='dataset_status',
            field=models.ManyToManyField(blank=True, help_text='The current status of the dataset.', to='datahub.datasetstatus', verbose_name='Status'),
        ),
    ]