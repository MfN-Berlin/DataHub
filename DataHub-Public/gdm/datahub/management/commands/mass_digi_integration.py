import logging
import requests
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from datahub.models import Report, Dataset, Origin
from django.contrib.auth.models import User
import json, csv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.gevent import GeventScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime
import pandas as pd
from io import StringIO, BytesIO
from django.core.files.base import ContentFile, File
from datahub import handlers
from PIL import Image
from PIL.ExifTags import TAGS
import math
import re
import numpy as np
from django.utils import timezone
import hashlib

@transaction.atomic
class Command(BaseCommand):

    easydb_token = ''
    # easydb_url = 'https://media.naturkundemuseum.berlin/api/v1/'
    easydb_url = 'http://192.168.101.174/api/v1/'
    logger_operation = logging.getLogger('operation')
    logger = logging.getLogger('operation') # logging.getLogger('apscheduler').setLevel(logging.DEBUG)
    # handler = handlers.ReportLogHandler()
    # logger.addHandler(handler)

    user = None
    params = None
    path = None
    report = None
    attachment = None
    dataset_json = None
    dataset_origin = 'Picturae'
    dataset_object = None
    pool_id = None
    pool_mapper = {'0': '57'} # Production {'0': '40'} # 
    keyword_mapper = {'ODK': 9838, 'Picturae': 9839, 'Label': 9688}
    filetype_mapper = {'tif':'image/tiff','png': 'image/png', 'jpg': 'image/jpeg'}
    subject_orientation_mapper = {"dorsal": 6, "lateral": 7, "ventral": 8, "frontal": 9, "recto": 20, "verso": 22}

    def add_arguments(self, parser):
        # arguments to run the import
        parser.add_argument('user', default='', help='The current user')
        parser.add_argument('params', default='', nargs='*',
                            help='params of datasets.')
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
            self.logger.error('response.status_code ={} : \n{}'.format(
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
                self.logger.error('response.status_code ={} : \n{}'.format(
                    response.status_code, response.text))
        return False

    def checksum_to_json(self, dataset):
        checksum_path = dataset["link"] + '/' + dataset["dataset"] + '__SHA-256.sum'
        datasets_df = pd.read_csv(checksum_path, sep='\s+', names=["checksum","file_name"])
        metadata_dict = datasets_df.to_dict(orient="records")
        metadata_json = json.dumps(metadata_dict)
        jsons = list()
        for index, row in datasets_df.iterrows():
            if 'json' in row['file_name']:
                jsons.append(row['file_name'])
        merged_dict = dict()
        for j in jsons:
            # Dealing with the rubbish in the metadata
            try:
                # Open ISO-8859-1 files from Picturae
                if self.dataset_origin == 'Picturae' and dataset['creation_date'] < "2023-02-23":
                    # Lars: "The JSON’s delivered so far are all ISO-8859-1."
                    with open(dataset["link"] + '/' + j,'r', encoding='ISO-8859-1') as json_file:  # latin-1 # as an alternative
                        json_obj = json.load(json_file)
                        utf8_valid = str(json_obj).encode(encoding = 'UTF-8', errors = 'strict')
                        merged_dict[j.split('/')[0]] = json_obj
                else:
                    with open(dataset["link"] + '/' + j,'r') as json_file:
                        json_obj = json.load(json_file)
                        utf8_valid = str(json_obj).encode(encoding = 'UTF-8', errors = 'strict')
                        merged_dict[j.split('/')[0]] = json_obj
                for image in merged_dict[j.split('/')[0]]['images']:
                    image_checksums = [item['checksum'] for item in metadata_dict if image['file_name'] in item['file_name']]
                    if len(image_checksums) == 1:
                        image['sha256_checksum'] = image_checksums[0].lower()
            except UnicodeDecodeError:
                self.logger.warn("Non UTF-8 input have found.")
                self.logger.warn("Invalid Dataset name: {}".format(dataset["dataset"]))
                continue
        with open(dataset["link"] + '/' + dataset["dataset"] + '.json', 'w') as merged_file:
            json.dump(merged_dict, merged_file, ensure_ascii=False, indent=4)
  
    def create_dataset(self, id, dataset):        
        # Use checksum file to construct a json
        json_path = dataset["link"] + '/' + dataset["dataset"] + '.json'
        checksum_path = dataset["link"] + '/' + dataset["dataset"] + '__SHA-256.sum'


        if os.path.exists(checksum_path):
            # Check filename if is unicode
            try:
                dataset["dataset"].encode()
                self.checksum_to_json(dataset)
            except UnicodeDecodeError:
                self.logger.warn("Non UTF-8 input have found.")
                self.logger.warn("Invalid Dataset name: {}".format(dataset["dataset"]))                                

            # Create dataset using the concatinated json
            with open(json_path) as json_file:
                json_data = json.load(json_file)
                self.dataset_json = json_data
                dataset_name = json_file.name.split('/')[-1].replace('.json','')
                origin_path = Origin.objects.get(id=2).comment
                file_path = "/media/smb" + origin_path + "/" + dataset["dataset"]
                specimen_count = len(self.dataset_json.keys())
                dataset_stats = {"specimen_count": specimen_count,
                                "specimen_integrated_count": 0,
                                "specimen_problem_count": 0,
                                "image_count": 0, 
                                "image_integrated_count": 0,
                                "image_problem_count": 0
                                }

                # Prepare a CSV of the json
                dfs = list()
                for obj in self.dataset_json:
                    # dfs.append(pd.json_normalize(self.dataset_json[obj], max_level=2, record_path="images", meta=['barcode','grouping_and_rehousing'])) 
                    dfs.append(pd.json_normalize(self.dataset_json[obj], sep='_', errors="ignore"))                
                big_df = pd.concat(dfs, axis=0)                
                buffer = StringIO()
                big_df.to_csv(buffer, index=False, header=True, encoding='utf-8')
                big_df.to_csv(dataset["link"] + '/' + dataset["dataset"] + '.csv', index=False, header=True, encoding='utf-8')                
                buffer.seek(0)
                csv_file = File(file=buffer, name=dataset["dataset"] + ".csv")

                if self.dataset_json:
                    if id == -1:
                        self.dataset_object = Dataset.objects.create(
                                                        JSON=self.dataset_json,
                                                        CSV=csv_file,
                                                        files=file_path,
                                                        params=dataset,
                                                        origin_id = 2,
                                                        stats=dataset_stats,
                                                        integrated=False,
                                                        validated=False,
                                                        datetime=datetime.now(),
                                                        creation_datetime=datetime.strptime(dataset['creation_date'],"%Y-%m-%dT%H:%M:%S"))
                    else:
                        self.dataset_object = Dataset.objects.get(pk=id)
                        self.dataset_object.JSON=self.dataset_json
                        self.dataset_object.CSV=csv_file
                        self.dataset_object.files=file_path
                        self.dataset_object.params=dataset
                        self.dataset_object.origin_id=2
                        self.dataset_object.stats=dataset_stats
                        self.dataset_object.integrated=False
                        self.dataset_object.validated=False
                        self.dataset_object.datetime=datetime.now()
                        self.dataset_object.creation_datetime=datetime.strptime(dataset['creation_date'],"%Y-%m-%dT%H:%M:%S")
                        self.dataset_object.save()
                    self.report.dataset = self.dataset_object
                    self.report.save()
        # TODO: conditations on other cases for generalization
        else:
            self.logger.warn("No checksum for {} found".format(checksum_path))
            
        return self.dataset_object

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
        if 'mfn' in keyword.lower():
            validated = True
        specimen_object = None
        endpoint = self.easydb_url + \
            'search?token={}'.format(self.easydb_token)
        headers = {"Content-Type": "application/json"}
        body = {"offset": 0, "limit": 10, "generate_rights": False, "search": [{"type": "complex", "__filter": "SearchInput",
                                                                                "search": [{"type": "match", "mode": "token", "string": keyword, "bool": "must"}]}], "format": "standard",
                "sort": [{"field": "_system_object_id", "order": "DESC"}], "objecttypes": ["specimen"],  "format": "long"}

        self.logger.info('\nSearch specimen request time stamp: {}'.format(
            self.current_datetime()))
        response = requests.post(endpoint, json=body, headers=headers)
        self.logger.info('- {}'.format(self.current_datetime()))

        if response.status_code == 200:
            found = False
            if len(response.json()["objects"]) > 0:
                self.logger.debug('Specimen found')
                specimen_object = [response.json()["objects"][0]]
                specimen_object[0]["specimen"]['_version'] += 1
                found = True
            else:
                specimen_object = [{
                            "specimen": {
                                "_version": 1,
                                "collection_id": keyword,
                                "collection": {"_objecttype": "subjectheadings",
                                                "_mask": "subjectheadings__all_fields",
                                                "_global_object_id": "135151@63aa8bb3-6981-4c2d-8774-4c8f7931abd0",
                                                "subjectheadings": {"_id": 29164}},
                                "_nested:specimen__gathering": [{"country": "Earth"}]
                            },
                            "_mask": "specimen__all_fields",
                            "_objecttype": "specimen",
                            "_idx_in_objects": 1
                            }]           
            self.logger.info(
                '\nNo specimen found for {}, creating a new specimen'.format(keyword))
            if validated:
                taxonomy = self.dataset_json[json_object]['grouping_and_rehousing']
                higher_taxa = ""
                full_scientific_name = ""
                if taxonomy["family"] or taxonomy["genus"]:
                    higher_taxa = taxonomy["family"] + "\n" + taxonomy["genus"] 
                    specimen_object[0]["specimen"]["_nested:specimen__taxonidentified"] = [{"highertaxa":higher_taxa}]                
                if taxonomy['genus'] and taxonomy["species"]:
                    full_scientific_name = taxonomy["genus"] + ' ' + taxonomy["species"] + ' ' + taxonomy["species_accreditation"]
                    specimen_object[0]["specimen"]["_nested:specimen__taxonidentified"][0]["fullscientificname"] = full_scientific_name
                endpoint = self.easydb_url + \
                    'db/specimen?token={}&format=short'.format(
                        self.easydb_token)
                headers = {"Content-Type": "application/json"}
                self.logger.info('\nCreate specimen request timestamp: {}'.format(
                    self.current_datetime()))
                response = requests.post(
                    endpoint, json=specimen_object, headers=headers)
                self.logger.info('- {}'.format(self.current_datetime()))

                specimen_object = response.json()[0]
            else:
                self.logger.warn(
                    '\n{} is not a valid catalogue number, skipped.'.format(keyword))
        return specimen_object

    def counter(self, stats_count={}):
        dataset_stats = self.dataset_object.stats
        for key, value in stats_count.items():
            if key in dataset_stats:
                dataset_stats[key] += value
            else:
                dataset_stats[key] = value

        self.dataset_object.stats = dataset_stats
        self.dataset_object.save()

    def media_handler(self, file_name, file_path, is_raw):
        """
        Upload a file as an asset to EasyDB EAS (EasyDB Asset Server)
        """
        media_object = {"_mask": "media__simple",
                        "_objecttype": "media",
                        "media": {"_pool": {"pool": {"_id": self.pool_id}},
                                "_version": 1,
                                "file":[]
                        }}
        file_found = False
        media_found = False
        raw_found = False
        skip_media = False
        is_public = False
        filetype = file_name.split('.')[-1]

        # Rename file
        # filename = filename.replace("_raw", "").split("_")
        # image_view = ''
        # if image["type"] == "stack" or image["type"] == "processed_stack":
        #     image_view = image["view"]                        
        # filename.insert(2, image_view)
        # filename[0] = 'mfn_uri_' + json_object
        # media_title =  '__'.join(filename)

        # Search the existance of the media object
        # TODO: consider other file types for DORA
        media_keyword = file_name #.split('.')[:-1][0]
        if is_raw:
            media_keyword = media_keyword.replace("_raw", "")
        endpoint = self.easydb_url + \
            'search?token={}'.format(self.easydb_token)
        headers = {"Content-Type": "image/{}".format(self.filetype_mapper[filetype]),
                   "check_for_duplicates": "true"}
        # body = {"search": [{"type": "match","mode": "token","string": media_keyword,"bool": "must"}],
        #         "format": "long",
        #         "objecttypes": ["media"]}
        body = {"search": [{
                "type": "in",
                "fields": ["media.file.original_filename"],
                "in": [media_keyword],
                "objecttypes": ["media"]}]}


        self.logger.info('\nSearch asset request: {}'.format(file_name))
        response = requests.post(endpoint, json=body, headers=headers)

        # Iterate over the search result to find the best matching object        
        if response.status_code == 200:
            asset_object = None
            if len(response.json()["objects"]) > 0:
                for object_dict in response.json()["objects"]:
                    if 'media' in object_dict:
                        # Select only media object with file in the same pool
                        # TODO: Take care of the duplicates and other matching objects
                        if 'file' in object_dict['media'] and object_dict['media']['_pool']['pool']['_id'] == self.pool_id:
                            for file_dict in object_dict['media']['file']:
                                if media_keyword in file_dict['original_filename']:
                                    media_found = True
                                    self.logger.debug('Object found: {} '.format(file_dict['original_filename']))
                                    media_object = object_dict #  = {'media':object_dict['media']} #['file'][0]
                                    media_object['media']['_version'] += 1
                                if file_name in file_dict['original_filename']:
                                    file_found = True                                    
                                    break
                            if '_nested:media__raw_files' in object_dict['media'] and is_raw:
                                for raw in object_dict['media']['_nested:media__raw_files'][0]['raw_file']:
                                    if file_name in raw['original_filename']:
                                        raw_found = True
                                        break
                            if file_found:
                                break
            if is_raw and not media_found:
                skip_media = True
                self.logger.warn("Possibility of duplication for {} RAW file skipped".format(media_keyword))
                self.counter({"image_problem_count":1})
                self.counter({"image_problem": " no media for raw file " + media_keyword})
            if not file_found and not raw_found and not skip_media:
                self.logger.info(
                    '\nNo existing media found for {}, uploading new file'.format(file_name))
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

                if response.status_code == 200:           
                    self.logger.info('file uploaded successfully')                                           
                    # Get file's ID
                    asset_object = response.json()[0]
                    # TODO: Check for duplicates

                    # Attach the Asset to the associated object                
                    # TODO : what about duplicates?
                    if asset_object:
                        asset_id = asset_object['_id']
                        asset_item = {"_id": asset_id, "preferred": True}

                        # Add raw files as _nested:media__raw_files
                        if not is_raw:
                            # asset_item["preferred"] = True
                            media_object["media"]["file"].append(asset_item)
                        else:
                            asset_id = asset_object['_id']
                            media_object["media"]["_nested:media__raw_files"] = [{"raw_file":[asset_item]}]

                    # self.logger.debug(response.text)
                else:
                    self.logger.warn(file_name + response.text)
                    self.counter({"image_problem_count":1})
                    self.counter({"image_problem": "response error {} for ".format(str(response.status_code)) + file_name})

                    skip_media = True
        else:
            self.logger.warn(file_name + response.status_code + " " + response.text)
            self.counter({"image_problem_count":1})
            self.counter({"image_problem": "response error {} for ".format(str(response.status_code)) + file_name})


        return (media_object, skip_media)

    def validate_data(self, json_object, validator = {'nuri': '^http://coll\.mfn-berlin\.de/u/[0-9a-fA-F]+$',
                                                      'mfn_uri': '^http://(coll\.mfn-berlin\.de/u|www\.digicoll\.info)/[\w/._:]+$'}):      
        for j in json_object:
            if "barcode" in j:
                matched = re.match(validator['nuri'],json_object[j])
                if matched: 
                    json_object[j] = True
                else: 
                    json_object[j] = json_object[j]
            if "drawer_name" in j or \
            "resource_uri" in j or \
            "scan name" in j:
                matched = re.match(validator['mfn_uri'],json_object[j])
                if matched: 
                    json_object[j] = True
                else: 
                    json_object[j] = json_object[j]

            # do some regex
            # validate
        return json_object

    def validate_file(self, filename, file_path, json_object, validation = {}):
        skip_media = False
        try:
            with open(file_path, 'rb') as image_file:
                image_data = image_file.read()
                image = Image.open(image_file)
                # exifdata = image.getexif()

                # for v in validation:            
                # TODO: NURI validation
                # TODO: File name
                if "filename" in validation.keys():
                    # do some regex reg is the first arg
                    matched = re.match(validation['filename'],filename)
                    if matched: 
                        validation['filename'] = True
                    else: 
                        validation['filename'] = filename
                # TODO: Checksum
                if "checksum" in validation.keys():
                    # generate or check checksum
                    checksum_alg = validation['checksum'] 
                    # TODO: validate
                    if checksum_alg == "SHA-256":
                        sha256_generated = None
                        sha256_generated = hashlib.sha256(image_data).hexdigest()
                        sh256_image = [i['sha256_checksum'] for i in self.dataset_json[json_object]['images'] if filename in i['file_name'] ]
                        if sha256_generated == sh256_image[0]:
                            validation['checksum'] = True
                        else:
                            validation['checksum'] = sha256_generated
                            self.counter({"image_problem_count":1})
                            self.counter({" image_problem":"Checksum mismatch {} for {}. ".format(str(sha256_generated),filename)})
                            skip_media = True
                        
                # TODO: File format: png for specimen, tiff for labels
                if "format" in validation.keys():
                    if validation["format"] == image.format:
                        validation["format"] = True 
                    else:
                        validation["format"] = image.format

                # TODO:Colour space: it shows me just RGB
                if "mode" in validation.keys():
                    if validation["mode"] == image.mode:
                        validation["mode"] = True
                    else:
                        validation["mode"] = image.mode  

                # TODO: Bit depth: 24 bit (or 8 bit per colour channel)
                if "bit_depth" in validation.keys():
                    image_array = np.array(image)
                    data_type = str(image_array.dtype)
                    if validation["bit_depth"] == data_type:
                        validation["bit_depth"] = True
                    else:
                        validation["bit_depth"] = data_type

                    # TODO: Ppi for labels 350, we don’t check ppi of specimen’s photo 
                if "dpi" in validation.keys():
                    width_px, height_px = image.size
                    dpi_x, dpi_y = image.info.get("dpi")

                    # Calculate physical dimensions in inches
                    # width_in = width_px / dpi_x
                    # height_in = height_px / dpi_y
                    # # Calculate PPI (pixels per inch)
                    # ppi_x = width_px / width_in
                    # ppi_y = height_px / height_in
                    # Use the geometric mean of PPI in both directions
                    # ppi = math.sqrt(ppi_x * ppi_y)

                    if validation["dpi"] == int(dpi_x):
                        validation["dpi"] = True
                    else:
                        validation["dpi"] = int(dpi_x)
                        
                # TODO: Compression: non
                if "compression" in validation.keys():
                    # generate or check checksum
                    # validate
                    pass                
        except OSError as e:
            self.counter({"image_problem_count":1})
            self.counter({"image_problem":"OS error {} for ".format(str(e)) + filename})
            skip_media = True

        return validation, skip_media
    
    def export_object(self,files_path, affiliatedproject_object, json_object):
        # upload files one by one
        specimen_object = None
        asset_id = None
        object_NURI = None
        object_storage_NURI = None
        related_object_dict = None            

        # Extract valid NURI from the filename
        if self.dataset_json[json_object]:
            object_NURI = self.dataset_json[json_object]['barcode']
            object_storage_NURI = self.dataset_json[json_object]['drawer_name'].replace("_lateral","")
            if object_NURI and self.attachment:
                related_object_dict = {"_nested:media__relatedobjectidentifiers": [
                    {
                        "relatedobjecttypes": {
                            "_objecttype": "relatedobjecttypes",
                            "_mask": "relatedobjecttypes__all_fields",
                            "_global_object_id": "58599@63aa8bb3-6981-4c2d-8774-4c8f7931abd0",
                            "relatedobjecttypes": {
                                "_id": 1
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
                    self.logger.warn(
                        'search query failed for {}'.format(object_NURI))
                    self.counter({"specimen_problem_count":1})
                    self.counter({"specimen_problem":response.text + object_NURI})

            image_list = self.dataset_json[json_object]["images"]
            
            for d in image_list:                
                if d["type"] == "processed_stack":
                    d['order'] = "0"
                if d["type"] == "stack":
                    d['order'] = str(len(image_list))

            image_list = sorted(image_list, key=lambda d: d['order']) 

            # Counter of the images
            self.counter({"image_count":len(image_list)})
            for image in image_list:
                skip_media = False
                filename = image["file_name"]
                file_path = files_path + '/' + filename
                
                # Prepare dict for validation
                image_validators = {'mode':'RGB',
                              'filename':'^[\w-]+_(stacked|processed_stack|label_front|label_back)_\d{4}(_label|_raw)?.(png|tif)$',
                              'checksum':'SHA-256', 'bit_depth':'uint8'}
                if image["type"] == "label":
                    image_validators['dpi'] = 350
                    image_validators['format'] = 'TIFF'
                else:
                    image_validators['format'] = 'PNG'
                # Validate the image, if not validated, skip media upload
                validation_dict, skip_media = self.validate_file(filename, file_path, json_object, image_validators)                
                for el in self.dataset_json[json_object]["images"]:
                    if el['file_name'] == image["file_name"]:
                        el['validation'] = validation_dict
                # Indicate raw files
                is_raw = False
                if image["type"] == "stack":
                    is_raw = True
                
                # Skip image media if attachment false
                if skip_media or not self.attachment: continue
                # Check existing file & media or create one
                media_object, skip_media = self.media_handler(filename, file_path, is_raw)
                if skip_media: continue
                                
                media_dict = media_object

                # Search or create affiliation project
                affiliatedproject_dict = {"project_affiliation": {
                        "_objecttype": "affiliatedproject__name",
                        "_mask": "standard",
                        # "_global_object_id": affiliatedproject_object['_global_object_id'],
                        "affiliatedproject__name": {"_id": affiliatedproject_object['affiliatedproject__name']['_id']}
                }}
                media_dict["media"]["project_affiliation"] = affiliatedproject_dict["project_affiliation"]

                # Attach the specimen to the media object
                if specimen_object:
                    media_dict["media"]["media2specimen"] = {"_objecttype": "specimen",
                                                                "_mask": "specimen__all_fields",
                                                                "_global_object_id": global_object_id,
                                                                "specimen": {"_id": specimen_id}
                                                            }
                if related_object_dict:
                    media_dict["media"]["_nested:media__relatedobjectidentifiers"] = related_object_dict["_nested:media__relatedobjectidentifiers"]

                # Update title
                if media_object and specimen_object:
                    media_title = ''
                    taxonomy = self.dataset_json[json_object]['grouping_and_rehousing']
                    if taxonomy["family"]:
                        media_title = taxonomy["family"]
                    if taxonomy["genus"]:
                        media_title += " " + taxonomy["genus"]
                    if taxonomy["species"]:
                        media_title += " " + taxonomy["species"]
                    if "label" in image["type"]:
                        media_title += " " + "label"
                        media_title += " " + image["side"]
                    if "label" not in image["type"]:
                        media_title += " " + image["view"]
                    media_dict["media"]["title"] = {
                                                    "de-DE":  media_title.replace('.jpg', '').replace('__label.tif', '').replace('.png', ''),
                                                    "en-US":  media_title.replace('.jpg', '').replace('__label.tif', '').replace('.png', ''),
                                                    }
                # Set Keywords: Picturae field
                if self.dataset_origin:
                    subjects_dict1 = {"subject": {
                        "_objecttype": "subjects",
                        "_mask": "subjects__all_fields",
                        "subjects": {"_id": self.keyword_mapper[self.dataset_origin]}
                        }
                    }
                    media_dict["media"]["_nested:media__subjects"] = [subjects_dict1]
                if image["type"] == "label":
                    subjects_dict2 = {"subject": {
                        "_objecttype": "subjects",
                        "_mask": "subjects__all_fields",
                        "subjects": {"_id": self.keyword_mapper['Label']}
                        }
                    }
                    media_dict["media"]["_nested:media__subjects"].append(subjects_dict2)

                # Set subject orientation
                subject_orientation = None
                orientation = None
                if image["type"] == "label":
                    subject_orientation = image["side"]
                    orientation = "label"
                elif image["type"]:
                    subject_orientation = image["view"]
                else:
                    self.logger.warn("subject orientation is missing * * *")

                if subject_orientation:
                    subjectorientation_dict = {
                                                "_objecttype": "subjectorientation",
                                                "_mask": "subjectorientation__all_fields",
                                                "subjectorientation": {"_id": self.subject_orientation_mapper[subject_orientation]}
                                                }
                    media_dict["media"]["subjectorientation"] = subjectorientation_dict
                
                if orientation:
                    orientation_dict =  {
                                        "_objecttype": "orientation",
                                        "_mask": "orientation__all_fields",
                                        "orientation": {"_id": 13}
                                        }                    
                    media_dict["media"]["orientation"] = orientation_dict

                # Copyright and license
                media_dict["media"]["copyright"] = "MfN Berlin, https://ror.org/052d1a351"
                media_dict["media"]["_nested:media__creators"] = [{"creator": "Picturae"}]
                media_dict["media"]["license"] = {"license": {
                                                "_id": 43,
                                                "_version": 1
                                                }}
                # Make Public
                media_dict["_tags"] =  [{"_id": 50}]

                # Make the post request 
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
                    self.counter({"image_integrated_count":1})
                else:                                        
                    body[0]['media']['_version'] += 1                        
                    response = requests.post(endpoint, json=body, headers=headers)
                    if response.status_code == 200:
                        self.logger.info('file imported successfully')
                        self.counter({"image_integrated_count":1})
                    else:
                        self.logger.warn(filename + ' Import error: {}'.format(response.text))
                        self.counter({"image_problem_count":1})
                        self.counter({"image_problem":"response error {} for ".format(str(response.status_code)) + filename})  

    def export_dataset(self):
        """ 
        Iterate over files and meta-data and upload them to EasyDB (main iteration function)
        """
        media_dict = None

        # Select the relevant pool in easydb
        self.pool_id = int(self.pool_mapper['0'])
        # pool_id = 40 # For Test pool

        # Retrieve Project name from EasyDB affiliated project
        project_name = 'PICT-00919' # self.params[2]

        # EasyDB Authentication
        is_auth = self.easydb_auth()
        if is_auth:
            affiliatedproject_object = self.affiliatedproject_handler(
                keyword=project_name)
            if affiliatedproject_object:
                # executors = {
                #             # 'default': ThreadPoolExecutor(20),
                #             'processpool': ProcessPoolExecutor(10)
                #             }
                # job_defaults = {
                #                 "misfire_grace_time":10,"max_instances": 30
                #                 }
                # scheduler2 = BackgroundScheduler(job_defaults=job_defaults, executors=executors)
                # scheduler2.config(job_defaults=job_defaults, executors=executors)
                # scheduler2 = GeventScheduler(executors=executors)
                for json_object in self.dataset_json:
                    files_path = self.path + '/' + json_object
                    
                    validation_json = {'barcode': self.dataset_json[json_object]['barcode'],
                                       'drawer_name': self.dataset_json[json_object]['drawer_name'],
                                       'resource_uri': self.dataset_json[json_object]['grouping_and_rehousing']['resource_uri'],
                                       'scan name': self.dataset_json[json_object]['grouping_and_rehousing']['scan name']
                                       }
                    self.dataset_json[json_object]['validation'] = self.validate_data(validation_json)
                    
                    # Export Linear in the same Thread
                    self.export_object(files_path,affiliatedproject_object,json_object)
                    self.counter({"specimen_integrated_count":1})
                    # Export Async 
                    # scheduler2.add_job(self.export_object,args=[files_path,affiliatedproject_object,json_object],
                                    # replace_existing=True, id="easydb_object_"+json_object)      

                # scheduler2.start()
                

            # TODO: LOGGING
            with open(self.logger.handlers[0].baseFilename, 'r') as logfile:
                logs = logfile.read()

                self.report.comment += ("\n" + logs +
                                        "\n object processed at: " + self.current_datetime())
                self.report.save()

            # Check the integration status
            if self.dataset_object.stats["specimen_count"] == \
                self.dataset_object.stats["specimen_integrated_count"] and \
                self.dataset_object.stats["image_count"] == \
                self.dataset_object.stats["image_integrated_count"]:
                self.dataset_object.integrated = True
            else:
                self.dataset_object.integrated = False
            
            # Check validation status
            valid = 0
            invalid = 0
            for specimen_obj in self.dataset_json:
                if 'validation' in self.dataset_json[specimen_obj]:
                    if self.dataset_json[specimen_obj]['validation']['barcode'] == True:
                        for image_obj in self.dataset_json[specimen_obj]['images']:
                            if "validation" in image_obj:
                                for v in image_obj["validation"]:
                                    if image_obj["validation"][v] != True:
                                        invalid += 1
                                    else:
                                        valid += 1
                else:
                    self.dataset_object.validated = False
                    break

            if invalid == 0:
                self.dataset_object.validated = True
                self.dataset_object.dataset_status.add(3)
            else:
                # self.dataset_object.dataset_status.remove(3)
                self.dataset_object.validated = False

            self.dataset_object.JSON = self.dataset_json
            self.dataset_object.save()

    def current_datetime(self):
        right_now = timezone.now()
        date_time = right_now.strftime("%Y-%m-%dT%H:%M:%S")
        return date_time

    def handle(self, *args, **options):
        # basic funtion to run the management commands, execustes the import scripts and enrichment modules
        current_user = options['user']
        self.attachment = bool(int(options['attachment']))
        self.user = User.objects.get(username=current_user)
        self.params = options['params'] # json.loads(params.replace("'", '"'))
        self.path = "" #options['params']
        import_flag = False        

        # Iterate over list of datasets
        if self.params:
            for dataset_dict in self.params:
                dataset = dataset_dict.replace("'",'"')
                # with open(dataset, encoding='utf-8') as f:
                #     json_data = json.load(f)


                dataset =  json.loads(dataset)
                self.path = dataset["link"]

                self.report = Report.objects.create(user=self.user,   
                                            report_type_id=2,                                                 
                                            flag=True,
                                            comment="Began at: " + self.current_datetime() +
                                            "\n" + str(self.params))
                self.logger_operation.info(" Importing started for {}!\nReport ID: {}".format(self.path ,self.report.id))
                # Create Dataset object if it doesn't exist
                self.dataset_object = None
                id = -1
                dataset_objects = Dataset.objects.filter(files__contains=dataset["dataset"])
                if len(dataset_objects) > 0:
                    self.dataset_object = dataset_objects[0]
                    self.dataset_json = self.dataset_object.JSON
                    dataset_object = self.create_dataset(self.dataset_object.id, dataset)
                else:
                     dataset_object = self.create_dataset(id, dataset)
                if dataset_object:
                    self.report.dataset=dataset_object
                    self.report.save()
                    # self.export_dataset() 
                    scheduler = None
                    if os.environ.get('SMB_PATH'):
                        scheduler = BackgroundScheduler()   
                    else:
                        scheduler = GeventScheduler()                 
                    

                    if True:
                        scheduler.add_job(self.export_dataset,
                                        replace_existing=True, id="easydb_export_"+ self.dataset_object.files.split('/')[-1])
                        # # scheduler.logger()
                        scheduler.start()

                    import_flag = True
                
                with open(self.logger_operation.handlers[0].baseFilename,'r') as logfile:
                    logs = logfile.read()

                self.report.comment += ('\n' + logs + '\nRequest processed at: ' + self.current_datetime())
                self.report.dataset = self.dataset_object
                self.report.flag = import_flag
                self.report.save()

                # Clear the log file for the next time usage
                open(self.logger_operation.handlers[0].baseFilename, "w").close()

        else:
            self.logger_operation.error(
                'authentication problemo! Export failed!\n------------------------------') 
        
        if self.report:
            return str(self.report.id)
        return str(-1)