from datetime import datetime
from .actions import export_dataset_samba
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.gevent import GeventScheduler
from django.core.management import call_command
from io import StringIO
from .models import Report, Dataset
from django.conf import settings
import logging
import shutil
import os
import random


class JobScheduler:
        
    def __init__(self, user, params, csv_type, scheduled):
        self.user = user
        self.params = params
        self.csv_type = csv_type
        self.scheduled = scheduled
        self.logger = logging.getLogger('operation')
        self.report_id = -1

    def auto_import_odk(self):
        # Check if it nessasary to import using last submition datetime
        self.logger.info("lastSubmission: {}".format(self.params[-1]))
        queryset = Dataset.objects.order_by('-datetime').filter(params=self.params).filter(flag=True)
        if len(queryset) > 0:
            self.logger.info("No changes in the existing Dataset.\nSkip the job.")
            dataset_id = queryset[0].id
            with open(self.logger.handlers[0].baseFilename,'r') as logfile:
                logs = logfile.read()            
            report = Report.objects.create(user=self.user,dataset_id=dataset_id, report_type_od=1, flag=False,comment=logs)
        call_command_out = StringIO()
        call_command('odk_import',self.user,*self.params, self.csv_type, stdout=call_command_out)
        self.report_id = int(call_command_out.getvalue().split('\n')[0])
        
        dataset_id = -1
        if self.report_id != -1:
            dataset_id = Report.objects.get(pk=self.report_id).dataset.id
            dataset = Dataset.objects.get(pk=dataset_id)
            dataset.flag = True
            dataset.save()
            self.auto_export_smb(dataset)
        else:
            self.logger.info('Auto Import somehow failed.')

    def auto_export_smb(self, dataset):
        export_flag = False
        try:
            dataset_id = Report.objects.get(pk=self.report_id).dataset.id
            dataset = Dataset.objects.get(pk=dataset_id)
            
            export_dataset_samba(dataset)

            self.logger.info('Auto-Exported dataset: ' + str(dataset_id))
            export_flag = True
        except Exception as e:
            self.logger.info('Failed to export dataset: {} \nError: {}'.format(str(dataset_id), str(e)))
            export_flag = False
        
        # Logging Export  
        with open(self.logger.handlers[0].baseFilename,'r') as logfile:
            logs = logfile.read()
        report = Report.objects.create(user=self.user,dataset=dataset_id, report_type_id=2, flag=export_flag,comment=logs)
        
    def start(self):
        # scheduler = BackgroundScheduler()
        scheduler = GeventScheduler()

        # Only For Testing 
        # self.auto_import_odk()

        # Randomize job execution time (minute)
        minutes = str(random.randint(0,59))
        hours = str(random.randint(19,23))
        # Starts immediately and schedules for the next run
        if self.scheduled == False:
            scheduler.add_job(self.auto_import_odk, replace_existing=True)
        # if (self.params[4] == "open") or self.scheduled == True:
            # scheduler.add_job(self.auto_import_odk, 'cron', day_of_week="mon-fri", hour=hours, minute=minutes) #, replace_existing=True)        
        scheduler.start()