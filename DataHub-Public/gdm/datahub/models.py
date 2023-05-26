from django.db import models
from django.contrib.auth.models import User
import os
from django.utils import timezone
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_delete
from django.core.files.storage import FileSystemStorage
import shutil
from django.utils.safestring import mark_safe
import json
from django.template.defaultfilters import truncatechars

# def filePath(instance, filename):
#     # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
#     return 'user_{0}/{1}'.format(instance.user.id, filename)


class OverwriteStorage(FileSystemStorage):
    """
    Custom file system storage: Overwrite get_available_name to make Django replace files instead of
    creating new ones over and over again.
    """
    def get_available_name(self, name, max_length=None):
        self.delete(name)
        return super().get_available_name(name, max_length)


class Test(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    published = models.DateTimeField('date published')

    def __str__(self):
        return self.title


class OriginStatus(models.Model):
    title = models.CharField(max_length=1000,)
    flag = models.CharField(max_length=1000, verbose_name="Tagline", null=True, blank=True) 
    comment = models.TextField(verbose_name="Comment", null=True, blank=True)

    def __str__(self):
        return self.title


class Origin(models.Model):
    title = models.CharField(max_length=1000)
    logo_path = models.CharField(max_length=1000, null=True, blank=True, verbose_name="relative path to the logo in static")
    link = models.CharField(max_length=1000, null=True, blank=True, verbose_name="Link to the integration initiation")
    tagline = models.CharField(max_length=1000, verbose_name="Tagline", null=True, blank=True)
    description = models.TextField(verbose_name="Description", null=True, blank=True)
    origin_status = models.ForeignKey(OriginStatus, on_delete=models.SET_NULL,null=True, blank=True, verbose_name="Status", help_text="The current status of integration pipeline.")
    active = models.BooleanField(default=False, verbose_name="Active?", help_text="Activates the pipeline.")
    metadata = models.JSONField(null=True, blank=True, verbose_name="Reference JSON of metadata")
    comment = models.TextField(verbose_name="Comment", null=True, blank=True)
    
    def __str__(self):
        return self.title

class DatasetStatus(models.Model):
    title = models.CharField(max_length=1000,)
    flag = models.CharField(max_length=1000, verbose_name="Tagline", null=True, blank=True) 
    comment = models.TextField(verbose_name="Comment", null=True, blank=True)

    def __str__(self):
        return self.title

class Dataset(models.Model):
    datetime = models.DateTimeField(default=timezone.now, verbose_name="Latest Date & Time")
    creation_datetime = models.DateTimeField(default=timezone.now, verbose_name="Dataset Creation Timestamp")
    CSV = models.FileField(max_length=1000, upload_to="dataset/csv/", storage=OverwriteStorage(), null=True, blank=True, verbose_name='CSV file')
    JSON = models.JSONField(null=True, blank=True, verbose_name="JSON file")
    files = models.CharField(max_length=1000, null=True, blank=True, verbose_name='image path', help_text='Provide a path from the shared "digi1" directory: e.g. /digi1/11_Picturae/01_delivered')
    origin = models.ForeignKey(Origin, on_delete=models.SET_NULL,null=True, blank=True, verbose_name="Origin of the Dataset", help_text="The origin of data")
    params = models.CharField(max_length=1000, null=True, blank=True, verbose_name='Import Parameters', help_text="The directory name of the dataset that holds the records.")
    stats = models.CharField(max_length=1000, null=True, blank=True, verbose_name='The latest stats of integration')
    integrated = models.BooleanField(max_length=1000, default=False, verbose_name='Integrated')
    validated = models.BooleanField(max_length=1000, default=False, verbose_name='Validated')
    dataset_status = models.ManyToManyField(DatasetStatus, blank=True, verbose_name="Status", help_text="The current status of the dataset.")
    flag = models.BooleanField(default=False, verbose_name="Automated")
    comment = models.TextField(verbose_name="Comment", null=True, blank=True)
    
    def __str__(self):
        str_text = None
        if self.CSV:
            str_text = self.CSV.name.split('/')[-1].replace(".csv","")
        elif self.JSON:
            str_text = self.params
        
        return str(str_text)
    
    def files_links(self):
        image_link = ''
        if self.CSV: 
            image_link += '<a style="font-weight:bold;" href="/media/{}">CSV File</a>'.format(self.CSV.name)
        if self.files:
            image_link += '<br><br><a style="font-weight:bold;" href="{}">All Files</a>'.format(self.files.split('/storage')[-1])
       

        return mark_safe(image_link)
    
    def stats_specimens(self):
        stats_text = ""
        if self.stats:
            stats_dict  = json.loads(self.stats.replace("'",'"'))
            specimen_integrated_count = stats_dict['specimen_integrated_count']
            specimen_count = stats_dict['specimen_count']
            stats_text = str(specimen_integrated_count) + "/" + str(specimen_count)
        return stats_text
    
    def stats_images(self):
        stats_text = ""
        if self.stats:
            stats_dict  = json.loads(self.stats.replace("'",'"'))
            image_integrated_count = stats_dict['image_integrated_count']
            image_count = stats_dict['image_count']
            stats_text = str(image_integrated_count) + "/" + str(image_count)                          
        return stats_text
    
    def stats_problems(self):
        stats_text = ""
        if self.stats:
            stats_dict  = json.loads(self.stats.replace("'",'"'))
            if 'specimen_problem_count' in stats_dict:
                specimen_problem_count =  stats_dict['specimen_problem_count']
            if 'image_problem_count' in stats_dict:
                image_problem_count =  stats_dict['image_problem_count']
                stats_text  = str(specimen_problem_count) + "/" + str(image_problem_count)
        return stats_text

    def sampled(self):        
        if self.dataset_status.all():
            for s in self.dataset_status.all():
                if s.title.lower() == "sampled":
                    return mark_safe('<img src="/static/admin/img/icon-yes.svg" alt="True">')
        return mark_safe('<img src="/static/admin/img/icon-no.svg" alt="False">')
    
    def backup(self):
        backup = False
        if self.dataset_status.all():
            for s in self.dataset_status.all():
                if s.title.lower() == "backup":
                    return mark_safe('<img src="/static/admin/img/icon-yes.svg" alt="True">')
        return mark_safe('<img src="/static/admin/img/icon-no.svg" alt="False">')

    # def save(self, *args, **kwargs):
    #     if self.files: 
    #         if self.files.startswith("/digi1"): self.files.replace("/digi1","/media/smb")
    #         if not self.files.startswith("/digi1") or not self.files.startswith("/media/smb") and not os.environ.get('SMB_PATH'):
    #             self.files = None
    #     super().save(*args, **kwargs)

    def reports(self):
        reports_link = ''
        if self.id:
            reports_link = mark_safe('<a style="font-weight:bold;" href="/admin/datahub/report/?dataset__id__exact={}">Reports</a>'.format(self.id))
        return reports_link


class ReportType(models.Model):
    title = models.CharField(max_length=1000,)
    flag = models.CharField(max_length=1000, verbose_name="Tagline", null=True, blank=True) 
    comment = models.TextField(verbose_name="Comment", null=True, blank=True)

    def __str__(self):
        return self.title


class Report(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL,null=True, blank=True, verbose_name="Username", help_text="The user who does the operation.")
    dataset = models.ForeignKey(Dataset, on_delete=models.SET_NULL,null=True, blank=True, verbose_name="Dataset", help_text="The Exported Dataset")
    report_type = models.ForeignKey(ReportType, on_delete=models.SET_NULL,null=True, blank=True, verbose_name="Report Type", help_text="Type of the Report")
    datetime = models.DateTimeField(verbose_name="Calendar Datetime", default=timezone.now)
    flag = models.BooleanField(default=False, verbose_name="Done Successfully")
    comment = models.TextField(verbose_name="Comment", null=True, blank=True)
    
    def __str__(self):
        return str(self.datetime)

    def report_origin(self):
        if self.dataset:
            return self.dataset.origin 
        else:
            return None

    def short_comment(self):
        return truncatechars(self.comment, 100)
    
# @receiver(post_delete, sender=Dataset)
# def post_delete_object(sender, instance, *args, **kwargs):
#     """ Clean Old Image file """
#     try:
#         instance.csv.delete(save=False)
#     except:
#         pass

# @receiver(post_delete, sender=Dataset)
# def post_save_image(sender, instance, *args, **kwargs):
#     """ Clean Old Image file """
#     try:
#         instance.files.delete(save=False)
#     except:
#         pass

@receiver(post_delete)
def delete_files_when_row_deleted_from_db(sender, instance, **kwargs):
    """ Whenever ANY model is deleted, if it has a file field on it, delete the associated file too"""
    for field in sender._meta.concrete_fields:
        if isinstance(field,models.FileField):
            instance_file_field = getattr(instance,field.name)
            delete_file_if_unused(sender,instance,field,instance_file_field)
        if field.name == 'files':
            instance_file_field = getattr(instance,field.name)
            if instance_file_field:
                if 'Picturae' not in instance_file_field and os.path.isdir(instance_file_field):
                    shutil.rmtree(instance_file_field)            


def delete_file_if_unused(model,instance,field,instance_file_field):
    """ Only delete the file if no other instances of that model are using it"""    
    dynamic_field = {}
    dynamic_field[field.name] = instance_file_field.name
    other_refs_exist = model.objects.filter(**dynamic_field).exclude(pk=instance.pk).exists()
    if not other_refs_exist:
        instance_file_field.delete(False)