from ast import keyword
import logging
import requests
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from datahub.models import Report, Dataset
from django.contrib.auth.models import User
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.gevent import GeventScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime
import pandas as pd


@transaction.atomic
class Command(BaseCommand):

    easydb_token = ''
    # easydb_url = 'https://media.naturkundemuseum.berlin/api/v1/'
    easydb_url = 'http://192.168.101.174/api/v1/'
    logger = logging.getLogger('operation')
    user = None
    params = None
    path = None
    report = None
    attachment = None
    dataset_json = None
    dataset_origin = 'Picturae'
    pool_id = None
    pool_mapper = {'0': '40'}
    keyword_mapper = {'ODK': 9838, 'Picturae': 9839}
    filetype_mapper = {'tif':'image/tiff','png': 'image/png', 'jpg': 'image/jpeg'}

    def add_arguments(self, parser):
        # arguments to run the import
        parser.add_argument('user', default='', help='The current user')
        parser.add_argument('path', default='',
                            help='Path of the specific ODK form.')
        # parser.add_argument('dataset_id', default='',
        #                     help='Dataset_id for logging')
        parser.add_argument('attachment', default=True,
                            help='If has attachments')

    def easydb_auth(self):
        """
        Open a session and authenticate with the token
        """
        endpoint = self.easydb_url + 'session'
        # headers = {'Content-Type':'application/json'}

        self.logger.info('\nSession request timestamp: {}'.format(
            self.current_datetime()))
        response = requests.get(endpoint)  # ,headers=headers)
        self.logger.info('- {}'.format(self.current_datetime()))

        if response.status_code == 200:
            # init easydb token globally
            # TODO: tells us when it is expired
            self.easydb_token = json.loads(response.text)["token"]
        else:
            self.logger.warn('response.status_code ={} : \n{}'.format(
                response.status_code, response.text))

        if self.easydb_token is not None:
            # Authenticate the session
            endpoint = self.easydb_url + 'session/authenticate?method=easydb'
            payload = '&token={}&login={}&password={}'.format(str(self.easydb_token), str(
                os.environ.get("EASYDB_USER")), str(os.environ.get("EASYDB_PASS")))

            self.logger.info('\nAuthentication request timestamp: {}'.format(
                self.current_datetime()))
            response = requests.post(url=endpoint + payload)
            self.logger.info('- {}'.format(self.current_datetime()))

            if response.status_code == 200:
                self.logger.info('done')
                return True
            else:
                self.logger.warn('response.status_code ={} : \n{}'.format(
                    response.status_code, response.text))
        return False

    def create_dataset(self):
        dataset = None
        json_path = self.path + '/' + self.path.split('/')[-1] + '.json'

        with open(json_path) as json_file:
            json_data = json.load(json_file)
            self.dataset_json = json_data
            dataset_name = json_file.name.split('/')[-1].replace('.json','')
        
            if self.dataset_json:
                dataset = Dataset.objects.create(
                                                    JSON=self.dataset_json,
                                                    files=self.path,
                                                    params=dataset_name,
                                                    origin_id = 1)
        return dataset


    def affiliatedproject_handler(self, keyword):
        """
        Search for the corresponding project in EasyDB, if not found create one.
        """
        affiliatedproject_object = None
        endpoint = self.easydb_url + \
            'search?token={}'.format(self.easydb_token)
        headers = {"Content-Type": "application/json"}
        body = {"search": [{"type": "match",
                            "mode": "token",
                            "string": keyword,
                            "bool": "must"
                            }], "format": "standard",
                "objecttypes": [
                                "affiliatedproject__name"
        ]}

        self.logger.info('\nSearch affiliatedproject request timestamp: {}'.format(
            self.current_datetime()))
        response = requests.post(endpoint, json=body, headers=headers)
        self.logger.info('- {}'.format(self.current_datetime()))

        if len(response.json()['objects']) > 0:
            affiliatedproject_object = response.json()['objects'][0]
        else:
            # Create affiliated project in easydb
            self.logger.info(
                "\n\n * The affiliated project was not found. Creating a new project.")
            endpoint = self.easydb_url + \
                'db/affiliatedproject__name?token={}&format=short'.format(
                    self.easydb_token)
            headers = {"Content-Type": "application/json"}
            body = [{"affiliatedproject__name":
                     {
                         "_version": 1,
                         "name": keyword
                     },
                     "_mask": "standard",
                     "_objecttype": "affiliatedproject__name",
                     "_idx_in_objects": 0
                     }]

            self.logger.info('\nCreate affiliatedproject request timestamp: {}'.format(
                self.current_datetime()))
            response = requests.post(endpoint, json=body, headers=headers)
            self.logger.info('- {}'.format(self.current_datetime()))

            affiliatedproject_object = response.json()[0]
        return affiliatedproject_object


    def specimen_handler(self, keyword, json_object):
        """
        Find specimen in easyDB data model
        """
        validated = False
        if 'coll.' in keyword:
            validated = True
        specimen_object = None
        endpoint = self.easydb_url + \
            'search?token={}'.format(self.easydb_token)
        headers = {"Content-Type": "application/json"}
        body = {"offset": 0, "limit": 10, "generate_rights": False, "search": [{"type": "complex", "__filter": "SearchInput",
                                                                                "search": [{"type": "match", "mode": "token", "string": keyword, "bool": "must"}]}], "format": "standard",
                "sort": [{"field": "_system_object_id", "order": "DESC"}], "objecttypes": ["specimen"]}

        self.logger.info('\nSearch specimen request time stamp: {}'.format(
            self.current_datetime()))
        response = requests.post(endpoint, json=body, headers=headers)
        self.logger.info('- {}'.format(self.current_datetime()))

        if response.status_code == 200:
            if len(response.json()["objects"]) > 0:
                self.logger.debug('Specimen found')
                specimen_object = response.json()["objects"][0]
            else:
                self.logger.info(
                    '\nNo specimen found for {}, creating a new specimen'.format(keyword))
                if validated:
                    taxonomy = self.dataset_json[json_object]['grouping_and_rehousing']
                    full_scientific_name = taxonomy['genus'] + ' ' + taxonomy['species'] + ', ' + taxonomy['species_accreditation'] 

                    endpoint = self.easydb_url + \
                        'db/specimen?token={}&format=short'.format(
                            self.easydb_token)
                    headers = {"Content-Type": "application/json"}
                    body = [{
                            "specimen": {
                                "_version": 1,
                                "collection_id": keyword,
                                "collection": {"_objecttype": "subjectheadings",
                                                "_mask": "subjectheadings__all_fields",
                                                "_global_object_id": "135151@63aa8bb3-6981-4c2d-8774-4c8f7931abd0",
                                                "subjectheadings": {"_id": 29164}},
                                "_nested:specimen__taxonidentified": [{"fullscientificname": full_scientific_name}],
                                "_nested:specimen__gathering": [{"country": "Earth"}]                                
                            },
                            "_mask": "specimen__all_fields",
                            "_objecttype": "specimen",
                            "_idx_in_objects": 1
                            }]
                    self.logger.info('\nCreate specimen request timestamp: {}'.format(
                        self.current_datetime()))
                    response = requests.post(
                        endpoint, json=body, headers=headers)
                    self.logger.info('- {}'.format(self.current_datetime()))

                    specimen_object = response.json()[0]
                else:
                    self.logger.info(
                        '\n{} is not a valid catalogue number, skipped.'.format(keyword))
        return specimen_object

    def media_handler(self, file_name, file_path):
        """
        Upload a file as an asset to EasyDB EAS (EasyDB Asset Server)
        """
        media_object = None
        found = False
        filetype = file_name.split('.')[-1]
        # Search the existance of the media object
        endpoint = self.easydb_url + \
            'search?token={}'.format(self.easydb_token)
        headers = {"Content-Type": "image/{}".format(self.filetype_mapper[filetype]),
                   "check_for_duplicates": "true"}
        body = {"search": [{"type": "match","mode": "token","string": file_name,"bool": "must"}],
                "format": "long",
                "objecttypes": ["media"]}

        self.logger.info('\nSearch asset request timestamp: {}'.format(
            self.current_datetime()))
        response = requests.post(endpoint, json=body, headers=headers)
        self.logger.info('- {}'.format(self.current_datetime()))

        # Iterate over the search result to find the best matching object        
        if response.status_code == 200:
            asset_object = None
            if len(response.json()["objects"]) > 0:
                for object_dict in response.json()["objects"]:
                    if 'media' in object_dict:
                        # Select only media object with file in the same pool
                        # TODO: Take care of the duplicates and other matching objects
                        if 'file' in object_dict['media'] and object_dict['media']['_pool']['pool']['_id'] == self.pool_id:                            
                            self.logger.debug('Object found')
                            media_object = object_dict #  = {'media':object_dict['media']} #['file'][0]
                            media_object['media']['_version'] += 1
                            found = True
                            break
            if not found:
                self.logger.info(
                    '\nNo existing media found for {}, uploading files'.format(file_name))
                if self.attachment:
                    # Upload the file
                    endpoint = self.easydb_url + 'eas/put?token={}'.format(
                        self.easydb_token)
                    headers = {"Content-Type": "image/{}".format(self.filetype_mapper[filetype]),
                               "check_for_duplicates": "true"}
                    body = {"media": (file_name, open(
                        file_path, 'rb'), "image/{}".format(self.filetype_mapper[filetype]))}

                    self.logger.info('\nCreate asset request timestamp: {}'.format(
                        self.current_datetime()))
                    response = requests.post(
                        endpoint, params=headers, files=body)
                    self.logger.info('- {}'.format(self.current_datetime()))

                    if response.status_code == 200:           # TODO: write else condition
                        self.logger.info('file uploaded successfully')
                        # Get file's ID
                        asset_object = response.json()[0]
                        # TODO: Check for duplicates
                        # Create Media json
                        media_object = {"_mask": "media__simple",
                                        "_objecttype": "media",
                                        "media": {"_pool": {"pool": {"_id": self.pool_id}},
                                                    "_version": 1,                                        
                                                }}
                        # Attach the Asset to the associated object                
                        # TODO : what about duplicates?
                        if asset_object:
                            asset_id = asset_object['_id']
                            asset_dict = {"file": [{"_id": asset_id ,"preferred": True}]}
                            media_object["media"]["file"] = asset_dict["file"]

                        # self.logger.debug(response.text)
                    else:
                        self.logger.warn(response.text)
        # Update title
        media_object["media"]["title"] = {
                                    "de-DE":  file_name.replace('.jpg', '').replace('.tif', '').replace('.png', ''),
                                    "en-US":  file_name.replace('.jpg', '').replace('.tif', '').replace('.png', ''),
                                        }
        return media_object


    def export_object(self,files_path, affiliatedproject_object, json_object):
        file_list = os.listdir(files_path)
        for filename in file_list:
            specimen_object = None
            file_path = files_path + '/' + filename

            # Check existing file & media or create one
            media_object = self.media_handler(filename, file_path)
            media_dict = media_object

            affiliatedproject_dict = {"project_affiliation": {
                    "_objecttype": "affiliatedproject__name",
                    "_mask": "standard",
                    # "_global_object_id": affiliatedproject_object['_global_object_id'],
                    "affiliatedproject__name": {"_id": affiliatedproject_object['affiliatedproject__name']['_id']}
            }}
            media_dict["media"]["project_affiliation"] = affiliatedproject_dict["project_affiliation"]

            # upload files one by one
            asset_id = None
            object_NURI = None
            object_storage_NURI = None
            related_object_dict = None            
            specimen_object = None

            # Extract valid NURI from the filename
            if self.dataset_json[json_object]:
                object_NURI = self.dataset_json[json_object]['barcode']
                object_storage_NURI = self.dataset_json[json_object]['drawName']
                if object_NURI:
                    related_object_dict = {"_nested:media__relatedobjectidentifiers": [
                        {
                            "relatedobjecttypes": {
                                "_objecttype": "relatedobjecttypes",
                                "_mask": "relatedobjecttypes__all_fields",
                                "_global_object_id": "725526@63aa8bb3-6981-4c2d-8774-4c8f7931abd0",
                                "relatedobjecttypes": {
                                    "_id": 10
                                }
                            },
                            "relatedobjectidentifier": object_NURI
                        },
                        {
                            "relatedobjecttypes": {
                                "_objecttype": "relatedobjecttypes",
                                "_mask": "relatedobjecttypes__all_fields",
                                "_global_object_id": "834936@63aa8bb3-6981-4c2d-8774-4c8f7931abd0",
                                "relatedobjecttypes": {
                                    "_id": 11
                                }
                            },
                            "relatedobjectidentifier": object_storage_NURI
                        }
                    ], }
                    # Search or create specimen object
                    specimen_object = self.specimen_handler(object_NURI, json_object)
                    # TODO: consider several results for specimen with (x) as suffix.
                    if specimen_object:
                        specimen_id = specimen_object["specimen"]["_id"]
                        global_object_id = specimen_object["_global_object_id"]
                    else:
                        self.logger.info(
                            'search query failed for {}'.format(filename))

            if specimen_object:
                media_dict["media"]["media2specimen"] = {"_objecttype": "specimen",
                                                            "_mask": "specimen__all_fields",
                                                            "_global_object_id": global_object_id,
                                                            "specimen": {"_id": specimen_id}
                                                        }
            if related_object_dict:
                media_dict["media"]["_nested:media__relatedobjectidentifiers"] = related_object_dict["_nested:media__relatedobjectidentifiers"]

            if self.dataset_origin:
                subjects_dict = {"subject": {
                    "_objecttype": "subjects",
                    "_mask": "subjects__all_fields",
                    "subjects": {"_id": self.keyword_mapper[self.dataset_origin]}
                    }
                }
                # media_dict["media"]["_nested:media__subjectheadings"] = []
                media_dict["media"]["_nested:media__subjects"] = [subjects_dict]

            body = [media_dict]

            endpoint = self.easydb_url + 'db/media?token={}'.format(
                    self.easydb_token)
            headers = {"Content-Type": "application/json"}

            self.logger.info('\nCreate media object request timestamp: {}'.format(
                self.current_datetime()))
            response = requests.post(endpoint, json=body, headers=headers)
            self.logger.info('- {}'.format(self.current_datetime()))

            if response.status_code == 200:           # TODO: write else condition
                self.logger.info('file imported successfully')
            else:
                self.logger.info('Import error: {}'.format(response.text))



    def export_dataset(self):
        """ 
        Iterate over files and meta-data and upload them to EasyDB (main iteration function)
        """
        media_dict = None

        # Select the relevant pool in easydb
        self.pool_id = int(self.pool_mapper['0'])
        # pool_id = 40 # For Test pool

        # Retrieve Project name from EasyDB affiliated project
        project_name = 'Picturae' # self.params[2]
        affiliatedproject_object = self.affiliatedproject_handler(
            keyword=project_name)
        if affiliatedproject_object:
            executors = {
                        # 'default': ThreadPoolExecutor(20),
                        'processpool': ProcessPoolExecutor(10)
                        }

            # scheduler = BackgroundScheduler(executors=executors)
            scheduler = GeventScheduler(executors=executors)
            for json_object in self.dataset_json:
                files_path = self.path + '/' + json_object

                scheduler.add_job(self.export_object,args=[files_path,affiliatedproject_object,json_object],
                                replace_existing=True, id="easydb_"+json_object)            
            scheduler.start()

        with open(self.logger.handlers[0].baseFilename, 'r') as logfile:
            logs = logfile.read()
            self.report.comment += ("\n" + logs +
                                       "\nEnded at: " + self.current_datetime())
            self.report.save()
        # Clear the log file for the next time usage
        open(self.logger.handlers[0].baseFilename, "w").close()

    def current_datetime(self):
        right_now = datetime.now()
        date_time = right_now.strftime("%d/%m/%Y, %H:%M:%S")
        return date_time

    def handle(self, *args, **options):
        # basic funtion to run the management commands, execustes the import scripts and enrichment modules
        current_user = options['user']
        self.attachment = bool(int(options['attachment']))
        self.user = User.objects.get(username=current_user)
        self.params = "" # json.loads(params.replace("'", '"'))
        self.path = options['path']

        self.report = Report.objects.create(user=self.user,                                                  
                                            flag=True,
                                            comment="Began at: " + self.current_datetime() +
                                            "\n" + str(self.params))


        # EasyDB Authentication
        is_auth = self.easydb_auth()
        if is_auth:

            # Export Data in background
            dataset = self.create_dataset()
            if dataset:
                self.report.dataset=dataset
                self.report.save()

                # self.export_dataset()
                # scheduler = BackgroundScheduler()
                scheduler = GeventScheduler()
                scheduler.add_job(self.export_dataset,
                                replace_existing=True, id="easypeasy_"+dataset.params)
                scheduler.start()

        else:
            self.logger.error(
                'authentication problemo! Export failed!\n------------------------------')
        
        with open(self.logger.handlers[0].baseFilename,'r') as logfile:
                logs = logfile.read()
        # Clear the log file for the next time usage
        open(self.logger.handlers[0].baseFilename, "w").close()

        if self.Report:
            return str(self.report.id)
        return str(-1)
