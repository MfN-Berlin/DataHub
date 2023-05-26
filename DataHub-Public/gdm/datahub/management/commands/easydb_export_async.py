from ast import keyword
import logging
import requests
import os
import pathlib
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from datahub.models import Report, Dataset
from django.contrib.auth.models import User
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.gevent import GeventScheduler
from datetime import datetime
import pandas as pd
from PIL import Image
from PIL.ExifTags import TAGS


@transaction.atomic
class Command(BaseCommand):

    easydb_token = ''
    # easydb_url = 'https://media.naturkundemuseum.berlin/api/v1/'
    easydb_url = 'http://192.168.101.174/api/v1/'
    logger = logging.getLogger('operation')
    nuri_prefix = 'http://coll.mfn-berlin.de/u/'
    params = None
    path = None
    report = None
    attachment = None
    dataset_csv = None
    dataste_origin = None
    pool_id = None
    pool_mapper = {'3': '51', '2': '52', '5': '52', '4': '53', '6': '54'}
    keyword_mapper = {'ODK': 9838, 'Picturae': 9839}

    def add_arguments(self, parser):
        # arguments to run the import
        parser.add_argument('user', default='', help='The current user')
        parser.add_argument('path', default='',
                            help='Path of the specific ODK form.')
        parser.add_argument('dataset_id', default='',
                            help='Dataset_id for logging')
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
            # ,headers= headers)

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

    def specify_broker(self, df):
        # Data Enrichment with Specify
        endpoint = 'http://dina.naturkundemuseum.berlin/specify/broker/v1.0/object/'

        genus_list = list()
        family_list = list()
        locality_list = list()
        LongitudeDecimal_list = list()
        LatitudeDecimal_list = list()

        temp_dict = dict()
        object_header = self.filter_dict["object"]

        # Read Object ID one by one
        for cell in df[object_header]:
            obj_number = cell.split('/')[-1]
            # obj_number = 'ZMB_Mam_108435'

            # To avoid multiple queries for several records of the same object
            if obj_number in temp_dict.keys():
                json_specify = temp_dict[obj_number]
            else:
                query = endpoint + obj_number
                response = requests.get(query, timeout=1000)
                if response.status_code == 200:
                    json_specify = json.loads(response.text)
                    if json_specify:
                        self.logger.info('Object {} exists in Specify. json content: {}\n'.format(
                            obj_number, json_specify))
                    else:
                        self.logger.info(
                            'Object {} does not exists in Specify!'.format(obj_number))
                    temp_dict[obj_number] = json_specify
                else:
                    self.logger.error(
                        'Response error in Specify request: {}'.format(response.text))

            genus = ''
            family = ''
            locality_text = ''
            longitude_decimal = ''
            latitude_decimal = ''

            # Add taxonomic lineage and locality
            if json_specify:
                # TODO: if specify value is empty or doesn't exist (the same with locality)
                if 'Genus' in json_specify['data']['determinations'][0]['taxon']:
                    genus = json_specify['data']['determinations'][0]['taxon']['Genus']
                if 'Family' in json_specify['data']['determinations'][0]['taxon']:
                    family = json_specify['data']['determinations'][0]['taxon']['Family']
                # Add gathering locality and GPS data
                if 'locality' in json_specify['data']:
                    locality_text = json_specify['data']['locality']
                    longitude_decimal = locality_text.pop('longitude', '')
                    latitude_decimal = locality_text.pop('latitude', '')

                genus_list.append(genus)
                family_list.append(family)
                locality_list.append(locality_text)
                LongitudeDecimal_list.append(longitude_decimal)
                LatitudeDecimal_list.append(latitude_decimal)

        # Make a temp dataframe with taxonomy info
        df_taxonomy = pd.DataFrame(
            {
                'Genus': genus_list,
                'Family': family_list
            })

        # Make a temp dataframwe with locality info as ABCD v3.0 structure
        df_locality = pd.DataFrame(
            {
                'LocalityText': locality_list,
                'LongitudeDecimal': LongitudeDecimal_list,
                'LatitudeDecimal': LatitudeDecimal_list
            })

        return pd.concat([df, df_taxonomy, df_locality], axis=1)

    def specimen_handler(self, keyword):
        """
        Find specimen in easyDB data model
        """
        # Search by ZMB
        valid_GIN = False
        if 'zmb' in keyword.lower():
            valid_GIN = True
        if 'mb.' in keyword.lower() or 'ma.' in keyword.lower():
            valid_GIN = True
        # Search NURI
        if len(keyword) >= 5:
            valid_GIN = True

        specimen_object = None
        endpoint = self.easydb_url + \
            'search?token={}'.format(self.easydb_token)
        headers = {"Content-Type": "application/json"}
        body = {"offset": 0, "limit": 10, "generate_rights": False,
                "search": [{"type": "complex", "__filter": "SearchInput",
                            "search": [{"type": "match", "mode": "token", "string": keyword, "bool": "must"}]}],
                "format": "standard",
                "sort": [{"field": "_system_object_id", "order": "DESC"}], "objecttypes": ["specimen"]}

        self.logger.info('\nSearch specimen request time stamp: {}'.format(
            self.current_datetime()))
        response = requests.post(endpoint, json=body, headers=headers)
        self.logger.info('- {}'.format(self.current_datetime()))

        # For a valid response, make a specimen json
        if response.status_code == 200:
            if len(response.json()["objects"]) > 0:
                if len(response.json()["objects"]) >= 1:  # TODO: ZMB_Mam_002091
                    self.logger.warn('Several ({}) Specimen found: {}'.format(
                        len(response.json()["objects"]), keyword))
                    for specimen in response.json()["objects"]:
                        if specimen: # in keyword:
                            specimen_object = specimen
            else:
                self.logger.info(
                    '\nNo specimen found for {}, creating a new specimen'.format(keyword))
                if valid_GIN:
                    endpoint = self.easydb_url + \
                        'db/specimen?token={}&format=long'.format(
                            self.easydb_token)
                    headers = {"Content-Type": "application/json"}
                    # Add recent mammals collection
                    new_body = [{
                        "specimen": {
                                "_version": 1,
                                "collection_id": self.nuri_prefix + keyword,
                                "_nested:specimen__taxonidentified": [],
                                "_nested:specimen__gathering": [{"country": "Earth"}],
                                },
                        "_mask": "specimen__all_fields",
                        "_objecttype": "specimen",
                        "_idx_in_objects": 1
                    }]
                    # if 'mam' in keyword.lower():
                    # endpoint += '&collection=8632'
                    # new_body["specimen"]["collection"] = {"_objecttype": "subjectheadings",
                    #     "_mask": "subjectheadings__all_fields",
                    #     "_global_object_id": "8632@63aa8bb3-6981-4c2d-8774-4c8f7931abd0",
                    #     "subjectheadings": {"_id": 112}}

                    self.logger.info('\nCreate specimen request timestamp: {}'.format(
                        self.current_datetime()))
                    response = requests.post(
                        endpoint, json=new_body, headers=headers)
                    self.logger.info('- {}'.format(self.current_datetime()))
                    if response.status_code == 200:
                        specimen_object = response.json()[0]
                    else:
                        self.logger.error("error in specimen response")
                else:
                    self.logger.info(
                        '\n{} is not a valid catalogue number, skipped.'.format(keyword))

            specimen_object["specimen"]["_version"] += 1
            specimen_object["specimen"]["collection_id"] = self.nuri_prefix + keyword

        return specimen_object

    def media_delete(self, media_id, version):
        body = [[media_id, version]]

        endpoint = self.easydb_url + 'db/media?token={}'.format(
            self.easydb_token)
        headers = {"Content-Type": "application/json"}

        self.logger.info('\nCreate media object request timestamp: {}'.format(
            self.current_datetime()))
        response = requests.delete(endpoint, json=body, headers=headers)
        self.logger.info('- {}'.format(self.current_datetime()))

        if response.status_code == 200:           # TODO: write else condition
            self.logger.info('file imported successfully')
        else:
            self.logger.info('Import error: {}'.format(response.text))

    def media_handler(self, file_name, file_path):
        """
        Upload a file as an asset to EasyDB EAS (EasyDB Asset Server)
        """
        media_object = None
        found = False
        media_title = file_name.split('_u_')[-1].split('__', 1)[-1].replace(
            '.jpg', '').replace('.tif', '').replace('.png', '').replace('ODK__', '')

        # Search the existance of the media object
        endpoint = self.easydb_url + \
            'search?token={}'.format(self.easydb_token)
        headers = {"Content-Type": "image/jpeg",
                   "check_for_duplicates": "true"}
        # file_title = file_name.split('u_')[-1].split('.')[-2]
        file_title_list = file_name.split('__')
        # file_title_list[1], file_title_list[2] = file_title_list[2], file_title_list[1]
        file_title = '__'.join(file_title_list)
        body1 = {"search": [{"type": "match", "mode": "wildcard",
                             "fields": ["media.file.original_filename"],
                             "string": file_title, "bool": "must"}],
                 "format": "long",
                 "objecttypes": ["media"]}
        # alternative_file_name = '__'.join(file_name.split('u_')[-1].split('__')[:-1]).replace('__ODK','')
        alternative_file_title = file_name.split('__')[0]
        body2 = {"search": [{"type": "match", "mode": "token",
                            "fields": ["media.file.original_filename"],
                             "string": alternative_file_title, "bool": "must"}],
                 "format": "long",
                 "objecttypes": ["media"]}

        self.logger.info('\nSearch asset request timestamp: {}'.format(
            self.current_datetime()))
        response1 = requests.post(endpoint, json=body1, headers=headers)
        self.logger.info('Search asset response time: {}'.format(
            response1.elapsed.total_seconds()))

        # Iterate over the search result to find the best matching media object
        if response1.status_code == 200:
            asset_object = None
            # Search associated media objects by ZMB & integer & append it
            if len(response1.json()["objects"]) > 0:
                for object_dict in response1.json()["objects"]:
                    if 'media' in object_dict:
                        # Select only media object with file in the same pool
                        # TODO: Take care of the duplicates and other matching objects
                        # and object_dict['media']['_pool']['pool']['_id'] == self.pool_id:
                        if 'file' in object_dict['media']:
                            for media_file in object_dict['media']['file']:
                                if media_title.split('__')[-1] in media_file['original_filename']:
                                    if not found:                                    
                                        # = {'media':object_dict['media']} #['file'][0]
                                        media_object = object_dict
                                        media_object['media']['_version'] += 1
                                        found = True
                                        self.logger.debug('Object found')
                                        if len(media_object['media']['file']) > 0:
                                            media_object['media']["captureequipment"] = media_object[
                                                'media']['file'][0]['technical_metadata']['camera_scanner']
                                    else:
                                        # OVERRIDE FILES for cleaning
                                        media_id = object_dict['media']['_id']
                                        version = object_dict['media']['_version']
                                        self.media_delete(media_id, version)

                                    # break

            # Search similar media objects by ZMB & Photo ID to avoid duplicates
            # self.dataset_csv['meta-instanceID'].where(self.dataset_csv['meta-instanceName'])
            if not found:
                response2 = requests.post(
                    endpoint, json=body2, headers=headers)
                if response2.status_code == 200 and len(response2.json()["objects"]) > 0:
                    for object_dict in response2.json()["objects"]:
                        if 'media' in object_dict and not found:
                            # and object_dict['media']['_pool']['pool']['_id'] == self.pool_id:
                            if 'file' in object_dict['media']:
                                for media_file in object_dict['media']['file']:
                                    if media_title.split('__')[-1] in media_file['original_filename'] and len(media_title.split('__')[-1]) > 6:
                                        self.logger.debug('Object found')
                                        media_object = object_dict
                                        media_object['media']['_version'] += 1
                                        found = True
                                        if len(media_object['media']['file']) > 0:
                                            media_object['media']["captureequipment"] = media_object[
                                                'media']['file'][0]['technical_metadata']['camera_scanner']
                                        break
                                if not found:
                                    for media_file in object_dict['media']['file']:
                                        term2 = '__'.join(
                                            file_title.split('__')[:-1])
                                        if term2 in media_file['original_filename'] and 'ZMB' in media_file['original_filename']:
                                            # extract creation time to compare
                                            # datetime.fromtimestamp(x.stat().st_ctime)
                                            # datetime.strptime(media_file['date_created'],'%Y-%m-%dT%H:%M:%SZ')
                                            x = pathlib.Path(file_path)
                                            y = datetime.fromtimestamp(
                                                x.stat().st_ctime).strftime('%Y-%m-%dT%H:%M:%SZ')
                                            z = media_file['date_created']
                                            if y == z:
                                                self.logger.debug(
                                                    'Object found')
                                                media_object = object_dict
                                                media_object['media']['_version'] += 1
                                                found = True
                                                if len(media_object['media']['file']) > 0:
                                                    media_object['media']["captureequipment"] = media_object[
                                                        'media']['file'][0]['technical_metadata']['camera_scanner']
                                                break

            # Upload new media object
            if not found:
                if self.attachment:
                    self.logger.info(
                        '\nNo existing media found for {}, uploading files'.format(file_name))
                    # Upload the file
                    endpoint = self.easydb_url + 'eas/put?token={}'.format(
                        self.easydb_token)
                    headers = {"Content-Type": "image/jpeg",
                               "check_for_duplicates": "true"}
                    open_file = open(file_path, 'rb')
                    # open_file =   Image.open(file_path, mode='r')
                    body = {"media": (file_name, open_file, "image/jpeg")}

                    self.logger.info('\nCreate asset request timestamp: {}'.format(
                        self.current_datetime()))
                    response = requests.post(
                        endpoint, params=headers, files=body)
                    open_file.close()

                    self.logger.info('- {}'.format(self.current_datetime()))
                    # associate the file to the json
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
                            asset_dict = {
                                "file": [{"_id": asset_id, "preferred": True}]}
                            media_object["media"]["file"] = asset_dict["file"]
                            media_object['media']["captureequipment"] = asset_object['technical_metadata']['camera_scanner']

                        # self.logger.debug(response.text)
                    else:
                        self.logger.warn(response.text)
        else:
            self.logger.error('response error. Not able to query the database {}\n'.format(
                self.current_datetime()))

        # Update title
        if media_object:
            media_titles = media_title.split('__')
            if len(media_titles) > 2:
                media_title = '__'.join(media_titles[-2:])

            media_object["media"]["title"] = {
                "de-DE":  media_title,
                "en-US":  media_title,
            }
        else:
            self.logger.info("Filename {} was not found".format(file_name))

        return media_object

    @staticmethod
    def export_data(self, affiliatedproject_object, filename):
        """ 
        Iterate over files and meta-data and upload them to EasyDB (main iteration function)
        """
        files_path = self.path
        media_dict = None

        # Select the relevant pool in easydb
        self.pool_id = int(self.pool_mapper[self.params[0]])
        # pool_id = 40 # For Test pool

        specimen_object = None
        file_path = files_path + '/' + filename

        # Check existing file & media or create one
        media_object = self.media_handler(filename, file_path)
        media_dict = media_object
        if media_dict:
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

            # Search the associated specimens
            # catalog_no = "http://coll.mfn-berlin.de/u/8c4a07" # None # "087503" ONLY FOR TESTING

            # Extract valid NURI and catalogue number from the filename
            if 'coll.' in filename:
                # Extract NURI from filename
                object_NURI = filename.split('__')[0].replace(
                    '_u_', '/u/').replace('coll.', 'http://coll.')
                # Extract catalogue number from filename
                object_catalog = filename.split('__')[1]
                if 'ODK' in object_catalog and 'ZMB' in object_NURI:
                    object_catalog = object_NURI.split('u/')[-1]
                # Extract storage location from csv
                # object_storage_NURI = x
                # Make the json objects
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
                        }
                    ], }
                    if object_catalog and 'ODK' not in object_catalog:
                        related_object_dict["_nested:media__relatedobjectidentifiers"].append({
                            "relatedobjecttypes": {
                                "_objecttype": "relatedobjecttypes",
                                "_mask": "relatedobjecttypes__all_fields",
                                "_global_object_id": "58599@63aa8bb3-6981-4c2d-8774-4c8f7931abd0",
                                "relatedobjecttypes": {
                                    "_id": 1,
                                    "_version": 2
                                },
                            },
                            "relatedobjectidentifier": object_catalog
                        })

                    # 58599 "_nested:media__relatedobjectidentifiers": [{"relatedobjectidentifier": "coll.mfn-berlin.de_u_b4f21a"}, {"relatedobjectidentifier": "MB.Ma.15130"}]
                    # filename.split('u_')[-1].split('__ODK')[0]
                    catalog_no = object_NURI.split('/')[-1]
                    if catalog_no:
                        # Search or create specimen object
                        specimen_object = self.specimen_handler(catalog_no)
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
                                                         "specimen": {"_id": specimen_id}}
            if related_object_dict:
                media_dict["media"]["_nested:media__relatedobjectidentifiers"] = related_object_dict["_nested:media__relatedobjectidentifiers"]

            if self.origin:
                subjects_dict = {"subject": {
                    "_objecttype": "subjects",
                    "_mask": "subjects__all_fields",
                    "subjects": {"_id": self.keyword_mapper[self.origin]}
                }
                }
                # media_dict["media"]["_nested:media__subjectheadings"] = []
                media_dict["media"]["_nested:media__subjects"] = [
                    subjects_dict]

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
            # else:
            #     self.logger.info('upload failed for {}'.format(filename))
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
        dataset_id = int(options['dataset_id'])
        self.attachment = bool(int(options['attachment']))
        dataset = Dataset.objects.get(pk=dataset_id)
        self.dataset_csv = dataset.CSV
        self.origin = dataset.origin.title
        params = dataset.params

        params = json.loads(params.replace("'", '"'))
        self.params = params
        self.path = options['path']
        user = User.objects.get(username=current_user)
        # csv_filename = str(options['path']).replace('/','_')

        # Export Log id = 2
        self.report = Report.objects.create(user=user,
                                            dataset=dataset_id,
                                            report_type=2,
                                            flag=True,
                                            comment="Began at: " + self.current_datetime() +
                                            "\n" + str(self.params))

        # EasyDB Authentication
        is_auth = self.easydb_auth()
        if is_auth:
            files_path = self.path
            media_dict = None

            # Retrieve ODK Project name from EasyDB affiliated project
            project_name = self.params[2]
            affiliatedproject_object = self.affiliatedproject_handler(
                keyword=project_name)

            if affiliatedproject_object:
                file_list = os.listdir(files_path)

                # Export Data in background
                scheduler = BackgroundScheduler() #max_concurrent_jobs=5)
                scheduler.add_executor('processpool')
                # scheduler = GeventScheduler(max_concurrent_jobs=5)
                for filename in file_list:

                    # scheduler = BackgroundScheduler()
                    scheduler.add_job(self.export_data,
                                      args=[affiliatedproject_object, filename],
                                      replace_existing=True,
                                      id="easypeasy_{}".format(filename.split('__')[-1])
                                      )
                scheduler.start()
                # scheduler.shutdown()
                # self.export_data()
        else:
            self.logger.error(
                'authentication problemo! Export failed!\n------------------------------')

        if self.report:
            return str(self.report.id)
        return str(-1)
