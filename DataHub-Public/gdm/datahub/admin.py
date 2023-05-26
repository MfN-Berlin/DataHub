from django.http import HttpResponse
from django.contrib import admin
from .actions import export_dataset_easydb, export_dataset_samba, export_csv_specify, \
     export_csv_portal, export_validation_report, export_dataset_picturae, rotate_images, sample_files
from .models import  Report, ReportType, Dataset, Origin, OriginStatus, DatasetStatus
from django.core.management import call_command
from django.conf import settings
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.gevent import GeventScheduler


@admin.action(permissions=['change'])
def export_easydb_attachment(modeladmin, request, queryset):
    for dataset in queryset:
        export_dataset_easydb(dataset=dataset, user=request.user, attachment=1)

export_easydb_attachment.short_description = "Integrate Datasets to EasyDB"


@admin.action(permissions=['change'])
def export_easydb_metadata(modeladmin, request, queryset):
    for dataset in queryset:
        export_dataset_easydb(dataset=dataset, user=request.user, attachment=0)

export_easydb_metadata.short_description = "Validate Datasets"


@admin.action(permissions=['change'])
def export_samba(modeladmin, request, queryset):
    for dataset in queryset: 
        export_dataset_samba(dataset)

export_samba.short_description = "Export to Z-drive"


@admin.action(permissions=['view'])
def export_specify(modeladmin, request, queryset):
    # filename for the output
    filename = queryset[0].CSV.name.split('/')[-1]
    # get the response from memory
    buffer = export_csv_specify(queryset)  
    response = HttpResponse(buffer, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
    return response
  
export_specify.short_description = "Export Specify CSV"


@admin.action(permissions=['view'])
def export_validation(modeladmin, request, queryset):
    # filename for the output
    filename = "validation_report_" + queryset[0].files.split("/")[-1].split("__")[0] + "_" + queryset[len(queryset) - 1].files.split("/")[-1].split("__")[0] + ".csv"
    # get the response from memory
    buffer = export_validation_report(queryset)  
    response = HttpResponse(buffer, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
    return response
  
export_validation.short_description = "Export Validation Report CSV"


@admin.action(permissions=['view'])
def export_portal(modeladmin, request, queryset):
    # filename for the output
    z = len(queryset) - 1
    filename = "picturae_dataportal_collection_objects.csv" # + queryset[0].params.split("__")[0] + "_" + queryset[len(queryset) - 1].params.split("__")[0] + ".csv"
    # get the response from memory
    buffer = export_csv_portal(queryset)
    response = HttpResponse(buffer, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
    return response
  
export_portal.short_description = "Export Data Portal CSV"


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'files_links', 'origin', 'creation_datetime', 'datetime', 'integrated', 'validated', 'sampled', 'backup' , 'flag', 'stats_specimens', 'stats_images', 'stats_problems', 'reports'] #[field.name for field in Dataset._meta.get_fields()] # link_to_xmlfile
    list_filter = ['origin', 'integrated', 'validated']
    date_hierarchy = 'creation_datetime'
    filter_horizontal = ['dataset_status']
    list_per_page=50
    
    # def link_to_xmlfile(self, obj):
    #     return "{}{}{}{}{}".format("<a href=\"/files/", obj.file_field, "\">", obj.title, "</a>")
    # link_to_xmlfile.allow_tags = True
    # link_to_xmlfile.short_description = 'XML File'
    actions_on_bottom = True
    actions_on_top = True
    ordering = ['-datetime']
    actions = [export_easydb_attachment, export_dataset_picturae, export_specify, export_portal, export_samba, export_easydb_metadata, export_validation, rotate_images, sample_files]
    
@admin.register(ReportType)
class ReportTypeAdmin(admin.ModelAdmin):
    list_display = ["title", "comment"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["user", "datetime", "dataset", "report_type", "report_origin", "short_comment"]
    list_filter = [ "dataset__origin","report_type__title"]

    readonly_fields = ["user","dataset", "flag"]
    actions_on_bottom = True
    actions_on_top = True
    list_per_page = 50

@admin.register(DatasetStatus)
class DatasetStatusAdmin(admin.ModelAdmin):
    list_display = ["title", "comment"]



@admin.register(OriginStatus)
class OriginStatusAdmin(admin.ModelAdmin):
    list_display = ["title", "comment"]


@admin.register(Origin)
class OriginAdmin(admin.ModelAdmin):
    list_display = ["title", "origin_status_title",]

    def origin_status_title(self, instance):
        return instance.origin_status.title