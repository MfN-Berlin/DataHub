from django import http
from django.shortcuts import render
from django.http import HttpResponse
import requests, json
from django.core.management import call_command
from django.http import HttpResponseRedirect
from .jobs import JobScheduler
from django.contrib.auth.decorators import login_required, permission_required
from rest_framework.decorators import api_view
from datahub.models import Dataset, Report
from io import StringIO
import logging
from django.conf import settings
from .actions import export_dataset_picturae, integrate_picturae, import_picturae
import ast
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.gevent import GeventScheduler

# import pandas as pd
# from .serializers import UserSerializer
# from rest_framework import viewsets
# from rest_framework import permissions
# from django.contrib.auth.models import User

# from django.views.generic.base import TemplateView

import datetime
import os
from datahub.models import Origin
from django.contrib.admin import AdminSite
from django.contrib import admin

class MyAdminSite(admin.AdminSite):
            pass
mysite = MyAdminSite()

logger = logging.getLogger('operation')

custom_page_values = {'site_header':'MfN Data Hub',
                    'site_title':'MfN Data Hub',
                    'is_popup': False,
                    'is_nav_sidebar_enabled': False,
                    }

def IndexView(request):
    return HttpResponseRedirect("/dashboard")


@login_required
@permission_required('datahub.view_dataset')
def media_view(request):
    response = HttpResponse()
    response['X-Accel-Redirect'] = '/media/'
    return response


@login_required
@permission_required('datahub.view_dataset')
def dashboard_view(request):
    origins = Origin.objects.all().order_by('id')
    if 'export_dataset' in request.POST:
        response_value = request.POST['export_dataset']
        if response_value == "test":            
            export_picturae(request)
            return HttpResponseRedirect("/admin/datahub/dataset/{}".format(''))             
    values = {'title': 'Dashboard',
            'subtitle': 'Available Integration Operations',
            'user': request.user,
            'has_permission': mysite.has_permission(request),
            'site_url': mysite.site_url,
            'origins': origins}
    values.update(custom_page_values)
    return render(request, 'dashboard.html', values)


@login_required
@permission_required('datahub.add_dataset')
def export_picturae(request):
    """
    Export the Picturae datasets from the file system to EasyDB
    """
    log_id = export_dataset_picturae(request.user.username)
    return HttpResponseRedirect("/admin/datahub/report/{}".format(log_id))
 

def current_datetime(request):
    now = datetime.datetime.now()
    html = "<html><body>It is now %s.</body></html>" % now
    return HttpResponse(html)


def odk_auth():
    """
    A Session Authentication with ODK endpoints, expires in 24h
    """
    odk_token = None
    # endpoint = 'https://odkcentral.naturkundemuseum.berlin/v1/sessions'
    endpoint = 'http://192.168.101.94/v1/sessions'
    headers = {'Content-Type':'application/json'}
    body = {"email": str(os.environ.get("ODK_USER")) ,"password": str(os.environ.get("ODK_PASS"))}
        
    response = requests.post(endpoint,data=json.dumps(body),headers=headers) # "/etc/customssl/fullchain.pem"
    if response.status_code == 200:
        token = json.loads(response.text)["token"] # TODO: tells us when it is expired
        odk_token = {"Authorization": "Bearer {}".format(token)}
    return odk_token


def odk_revoke(token):
    # logout the session
    # endpoint = 'https://odkcentral.naturkundemuseum.berlin/v1/sessions/'
    endpoint = 'http://192.168.101.94/v1/sessions/'

    headers = token
    if token:
        token = token["Authorization"].split(" ")[-1]
        response = requests.delete(endpoint + token,headers=headers)
        if response.status_code == 200:
            logger.info("session closed.")
    else:
        logger.info("Couldn't close the session.")
        

def odk_forms(projectId,odk_token):
    """
    Gets all the existing ODK forms in a specific project with projectId
    """
    # endpoint = 'https://odkcentral.naturkundemuseum.berlin/v1/projects/{}/forms'.format(projectId)
    endpoint = 'http://192.168.101.94/v1/projects/{}/forms'.format(projectId)
    headers = {'Content-Type':'application/json', 'X-Extended-Metadata':'true'}
    headers.update(odk_token)

    response = requests.get(endpoint,headers=headers) 
    if response.status_code == 200: 
        return response.text


@login_required
@permission_required('datahub.add_dataset')
def list_picturae(request):
    """
    Lists all Picturae dataset in one table.
    It does the import operation in postback
    """
    if request.method == 'POST':
        if 'import_all' in request.POST:
            response_value = request.POST['import_all']
            if response_value:
                response_value = response_value.replace("'",'"')
                datasets = json.loads(response_value)
                # TODO: make it to work with other cases
                filtered_datasets = [d for d in datasets if d['status_imported'] == ""]
                # Limit the Import 
                # TODO: improve batch imports
                if len(filtered_datasets) > 50:
                    filtered_datasets = filtered_datasets[:50]
                # validation
                integration_scheduler = None
                if os.environ.get('SMB_PATH'):
                    integration_scheduler = BackgroundScheduler()   
                else:
                    integration_scheduler = GeventScheduler()                 
                if len(filtered_datasets) > 0:
                    integration_scheduler.add_job(integrate_picturae,
                                    kwargs={"request":request, "filtered_datasets": filtered_datasets, "attachment": 0},
                                    replace_existing=True, id="update_easydb_batch" + filtered_datasets[0]["dataset"])
                # # scheduler.logger()
                    integration_scheduler.start()

                # for dataset in filtered_datasets:
                #     try:
                #         dataset["dataset"].encode()
                #         report_id = import_picturae(request.user, [dataset], 0)
                #     except UnicodeDecodeError:
                #         logger.warning("Invalid Dataset name: {}".format(dataset["dataset"]))
                #         continue
        elif 'update_all' in request.POST:  
            response_value = request.POST['update_all']        
            if response_value:
                response_value = response_value.replace("'",'"')
                datasets = json.loads(response_value)
                filtered_datasets = [d for d in datasets if d["status_imported"] == "checked" and d['status_integrated'] == "checked"]
                # TODO: improve batch imports
                if len(filtered_datasets) > 50:
                    filtered_datasets = filtered_datasets[:50]
                # filtered_datasets =  sorted(filtered_datasets, key=lambda d: d['creation_date'], reverse=True) 
                # validation
                # job in background
                integration_scheduler = None
                if os.environ.get('SMB_PATH'):
                    integration_scheduler = BackgroundScheduler()   
                else:
                    integration_scheduler = GeventScheduler()                 
                if len(filtered_datasets) > 0:
                    integration_scheduler.add_job(integrate_picturae,
                                    kwargs={"request":request, "filtered_datasets": filtered_datasets, "attachment": 1},
                                    replace_existing=True, id="update_easydb_batch" + filtered_datasets[0]["dataset"])
                # # scheduler.logger()
                    integration_scheduler.start()
                return HttpResponseRedirect("/admin/datahub/dataset/{}".format(''))
                # for dataset in filtered_datasets:
                #     try:
                #         dataset["dataset"].encode()
                #         report_id = import_picturae(request.user, [dataset], 0)
                #     except UnicodeDecodeError:
                #         logger.warning("Invalid Dataset name: {}".format(dataset["dataset"]))
                #         continue

        elif 'integrate_all' in request.POST:  
            response_value = request.POST['integrate_all']        
            if response_value:
                response_value = response_value.replace("'",'"')
                datasets = json.loads(response_value)
                filtered_datasets = [d for d in datasets if d["status_imported"] == "checked" and d['status_integrated'] == "" and '2023-02-' not in d['creation_date']]
                # Limit the Import 
                # TODO: improve batch imports
                if len(filtered_datasets) > 50:
                    filtered_datasets = filtered_datasets[:50]

                # job in background
                integration_scheduler = None
                if os.environ.get('SMB_PATH'):
                    integration_scheduler = BackgroundScheduler()   
                else:
                    integration_scheduler = GeventScheduler()                 
                if len(filtered_datasets) > 0:
                    integration_scheduler.add_job(integrate_picturae,
                                    kwargs={"request":request, "filtered_datasets": filtered_datasets, "attachment": 1},
                                    replace_existing=True, id="integrate_easydb_batch" + filtered_datasets[0]["dataset"])
                # # scheduler.logger()
                    integration_scheduler.start()                
                return HttpResponseRedirect("/admin/datahub/dataset/{}".format(''))            
        elif 'import_files' in request.POST:
                response_value = request.POST['import_files']
                response_value = response_value.replace("'",'"')
                datasets = json.loads(response_value)               
                report_id = import_picturae(request.user, [datasets], 0)
                return HttpResponseRedirect("/admin/datahub/report/{}".format(str(report_id)))
        elif 'integrate_files' in request.POST:
                response_value = request.POST['integrate_files']
                response_value = response_value.replace("'",'"')
                datasets = json.loads(response_value)               
                report_id = import_picturae(request.user, [datasets], 1)
                return HttpResponseRedirect("/admin/datahub/report/{}".format(str(report_id)))
    else:
        picturae_list = list()

        # dataset_path = str(settings.MEDIA_ROOT / 'smb/11_Picturae/01_delivered')
        origin_path = Origin.objects.get(id=2).comment
        local_path = "/run/user/1000/gvfs/smb-share:server=192.168.201.123,share=digi1" + origin_path
        test_path = "/home/mjvx/Work/archive/Picturae"
        pro_path = str(settings.MEDIA_ROOT / 'smb') + origin_path        
        dataset_path = ""
        max = 0
        if os.environ.get('SMB_PATH'):
            dataset_path = local_path # test_path # local_path #test_path # local_path #
            max = 20
        else:
            dataset_path = pro_path
        dataset_list = os.listdir(dataset_path)
        if max > 0:
            dataset_list = dataset_list[:max]
        for dataset_title in dataset_list:
            if 'mfn' in dataset_title:
                file_path = dataset_path + '/' + dataset_title
                checksum_path = file_path + '/' + dataset_title + '__SHA-256.sum'
                is_imported = ""
                is_integrated = ""
                is_validated = ""
                dataset_stats = ""
                dataset = Dataset.objects.filter(files__contains=dataset_title)
                if len(dataset) > 0:
                    is_imported = "checked"
                    if dataset[0].integrated:
                        is_integrated = "checked"
                    if dataset[0].validated:
                        is_validated = "checked"    
                    if dataset[0].stats:
                        current_stats = dataset[0].stats.replace("'",'"')
                        dataset_stats = json.loads(current_stats)

                    # stats_reference = ["specimen_count", "specimen_integrated_count", "image_count", "image_integrated_count"]

                if not os.path.exists(checksum_path):
                    continue
                creation_date =  (datetime.datetime.fromtimestamp(os.path.getmtime(checksum_path))).strftime("%Y-%m-%dT%H:%M:%S")            
                picturae_dict = {"dataset": dataset_title,"link": file_path,"status_imported":is_imported, "status_integrated": is_integrated, "status_validated": is_validated, "dataset_stats": dataset_stats, "creation_date":creation_date}
                picturae_list.append(picturae_dict)

        # picturae_list = [d for d in picturae_list if d['status_integrated'] == ""]
        picturae_list = sorted(picturae_list, key=lambda d: d['creation_date'])  
        
        values = {
                    "obj": picturae_list,
                    "total": len(picturae_list),
                    "total_validated": sum(1 for item in picturae_list if item["status_validated"] == "checked"),
                    "total_integrated": sum(1 for item in picturae_list if item["status_integrated"] == "checked"),
                    "total_specimens": sum(item["dataset_stats"]["specimen_integrated_count"] for item in picturae_list if item["dataset_stats"]),
                    "total_images": sum(item["dataset_stats"]["image_integrated_count"] for item in picturae_list if item["dataset_stats"]),
                    "title": "Picturae",
                    "subtitle": "List of Picturae datasets to be imported",
                    "user": request.user,
                    "has_permission": mysite.has_permission(request)
                }
        values.update(custom_page_values)
        return render(request, 'mass-digi.html', values)


@login_required
@permission_required('datahub.add_dataset')
def odk_list(request):
    """
    Lists all ODK forms of all projects in one table.
    It does the import operation in postback
    """

    # The postback call to deliver the choosen form title to the import. triggered with the button click
    if request.method == 'POST':
        csv_type = 'original'
        if 'import_all' in request.POST:
            response_value = request.POST['import_all']
            if response_value == "all":
                import_odk_all(request.user)
                return HttpResponseRedirect("/admin/datahub/dataset/{}".format(''))             
        elif 'import_files' in request.POST:
            response_value = request.POST['import_files']
            csv_type = response_value.split("//")[0]
            params = response_value.split('//')[1:]
            logger.debug('csv type is {}.'.format(csv_type))
            if csv_type == 'automated':
                csv_type = 'attachment'
                scheduled = False
                jobScheduler = JobScheduler(request.user,params,csv_type,scheduled)
                jobScheduler.start()
                return HttpResponseRedirect("/admin/datahub/dataset/{}".format(''))
        logger.debug('csv type is {}. [ FORCED ]'.format(csv_type))
        params = response_value.split('//')[1:]
        report_id = import_odk(request.user,params,csv_type)
        # if (import_result != -1):
        return HttpResponseRedirect("/admin/datahub/report/{}/change/".format(report_id))

    # Uses the bearer token if there is no existing session yet.
    odk_token = odk_auth()
    if odk_token:
        # endpoint = 'https://odkcentral.naturkundemuseum.berlin/v1/projects'
        endpoint = 'http://192.168.101.94/v1/projects'
        headers = {'Content-Type':'application/json'}
        headers.update(odk_token)
        # Make the list of forms, if the respose is OK
        response = requests.get(endpoint,headers=headers) 
        if response.status_code == 200:
            form_list = list()
            for x_dict in json.loads(response.text):
                forms = odk_forms(x_dict['id'],odk_token)
                for f_dict in json.loads(forms):
                    form_dict = f_dict.copy()                
                    form_dict['projectName'] = x_dict['name']
                    form_list.append(form_dict)
            odk_form_list = sorted(form_list, key=lambda k: k['projectId'])
        else:
            odk_form_list = dict()
            logger.debug("Couldn't Extract the list!")
    else:
        odk_form_list = dict()
        logger.error("Couldn't authenticate!")
    odk_revoke(odk_token)
    values = {"obj": odk_form_list, 
            'title': 'ODK',
            'subtitle': 'List of ODK datasets to be imported',
            'user': request.user,
            'has_permission': mysite.has_permission(request),}
    values.update(custom_page_values)
    return render(request, 'odk.html', values)


def import_odk(user,params,csv_type):
    """
    calls the import function as a management commands for odk_import.py
    """
    call_command_out = StringIO()
    call_command('odk_import',user,*params,csv_type, stdout=call_command_out)
    return call_command_out.getvalue().split('\n')[0]


def import_odk_all(user):
    queryset = Dataset.objects.order_by('-datetime').filter(flag=True)
    for dataset in queryset:
        params = dataset.params
        csv_type = 'attachment'
        scheduled = True
        jobScheduler = JobScheduler(user,params,csv_type, scheduled)
        jobScheduler.start()

def import_mass_digi_all(user):
    queryset = Dataset.objects.order_by('-datetime').filter(flag=True)
    for dataset in queryset:
        params = dataset.params
        csv_type = 'attachment'
        scheduled = True
        jobScheduler = JobScheduler(user,params,csv_type, scheduled)
        jobScheduler.start()

