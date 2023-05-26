from ast import keyword
from datetime import datetime  # , timezone
import os.path
import os
from posixpath import split
from django.conf import settings
from django.core.management.base import BaseCommand
import logging
# import subprocess
import requests
from zipfile import ZipFile
import pandas as pd
from io import StringIO, BytesIO
from datahub.models import Dataset, Report, Origin
from django.contrib.auth.models import User
from django.core.files.base import ContentFile, File
from django.utils import timezone
import json
import shutil
from django.db import transaction


@transaction.atomic
class Command(BaseCommand):

    # url_odk = 'https://odkcentral.naturkundemuseum.berlin/'
    url_odk = 'http://192.168.101.94/'
    url_dina = ''
    filter_dict = None
    projectId = None
    xmlFormId = None
    odk_token = {}
    origin = None

    csv_type = "original"
    # operation_type  = "manual"
    odk_unwanted_columns = ['KEY', 'SubmitterID',
                            'DeviceID', 'Edits', 'FormVersion', 'SubmitterName']
    logger = logging.getLogger('operation')
    logging.getLogger('apscheduler').setLevel(logging.DEBUG)

    def add_arguments(self, parser):
        # arguments to run the import
        parser.add_argument('user', default='', help='The current user')
        parser.add_argument('params', default='', nargs='*',
                            help='Path of the specific ODK form.')
        parser.add_argument('csv_type', default='original', choices=[
                            'original', 'merged', 'attachment'], help='Type of Import')

    def init_global(self, params, csv_type):
        self.csv_type = csv_type
        self.odk_auth()
        # settings_path = settings.MEDIA_ROOT / "settings" / "project_filter.json"
        project_filters = Origin.objects.filter(title="ODK")
        if project_filters:
            filters = json.loads(project_filters[0].comment)
            self.projectId = params[0]
            self.xmlFormId = params[3]
            self.params = params
            self.logger.debug('init: {}'.format(self.xmlFormId))

            # Read the xml to find filters
            for filter in filters:
                if str(filter["projectId"]) == self.projectId and filter["xmlFormId"] == self.xmlFormId:
                    self.filter_dict = filter
                    break
            if self.filter_dict is None:
                self.logger.warn(
                    'Initiation Failed! The filter_dict is empty. Please edit project_filter.json file related to this form!')

    def odk_auth(self):
        """
        A Session Authentication with ODK endpoints, expires in 24h
        """
        endpoint = self.url_odk + 'v1/sessions'
        headers = {'Content-Type': 'application/json'}
        body = {"email": str(os.environ.get("ODK_USER")),
                "password": str(os.environ.get("ODK_PASS"))}

        response = requests.post(endpoint, data=json.dumps(
            body), headers=headers)  # "/etc/customssl/fullchain.pem"
        if response.status_code == 200:
            # TODO: tells us when it is expired
            token = json.loads(response.text)["token"]
            self.odk_token = {"Authorization": "Bearer {}".format(token)}

    def specify_query(self, df):
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

    def rename_files(self, df, path):
        endpoint = self.url_odk + 'v1/projects/' + \
            path + '/submissions.csv.zip?attachments=true'
        storage_path = str(settings.MEDIA_ROOT / "temp")
        headers = {'Content-Type': 'application/zip'}

        # find fields with images
        df_columns = list(df.columns.values)
        df_images = [s for s in df_columns if "image" in s.lower()]
        df_images += [s for s in df_columns if "photo" in s.lower()]
        # self.logger.debug(str(set(df_images)))

    def import_data(self, params, csv_filename):
        df_output = None
        attachment = False
        if self.csv_type == 'attachment':
            attachment = True
        df_flat = None
        df_attachments = None
        df_original = None
        # filters = '&$filter=year(__system/submissionDate) eq 2021 and  month(__system/submissionDate) eq 9 and day(__system/submissionDate) eq 20'
        endpoint = self.url_odk + 'v1/projects/{}/forms/{}/submissions.csv.zip?attachments={}{}'.format(
            params[0], params[3], (str(attachment)).lower(), '')  # filters
        headers = {'Content-Type': 'application/zip'}
        headers.update(self.odk_token)
        
        # Prepare path and check existing zip files
        storage_path = str(settings.MEDIA_ROOT / "temp")
        the_storage_path = storage_path + "/" + csv_filename
        zip_path = the_storage_path + '.zip'
        zip_file = None
        new_path = str(settings.MEDIA_ROOT / "dataset" /
                       "image") + "/" + csv_filename
        # using previous downloads in tmp
        if os.path.exists(zip_path):
            try:
                zip_file = ZipFile(zip_path)
                self.logger.info(
                    'Zip file already exists in temp. Skipping download! Zip: ' + zip_path)
                # TODO: check the last submition date to make sure.
            except Exception as e:
                self.logger.warn(
                    'Existing zip file error: {} \n'.format(str(e)))
                os.remove(zip_path)
        else:
            # Download Request
            response = requests.get(endpoint, headers=headers, stream=True)
            if response.status_code == 200:           # TODO: write else condition
                # download chunks
                chunk_size = 1024*1024*4  # 4 MB #*1024 # 1 GB
                            
                if not os.path.exists(zip_path):
                    self.logger.info("zip path: {}".format(zip_path))
                    try:
                        with open(zip_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=chunk_size):
                                f.write(chunk)

                        zip_file = ZipFile(zip_path)
                        self.logger.debug('Zip file downloaded: {}\n'.format(zip_path))
                    except Exception as e:
                        self.logger.warn('Zip download error: {} \n'.format(str(e)))
            else:
                self.logger.error('Response Error: {}'.format(response.text))

        df_list = list()
        media_list = list()
        has_media = False
        if zip_file:
            self.logger.debug('# objects in the zip: {}\n'.format(
                len(zip_file.namelist())))
            for name in zip_file.namelist():
                if 'csv' in name:
                    data = BytesIO(zip_file.read(name))
                    df = pd.read_csv(data)
                    # df['KEY'][0]
                    df_list.append(df)
                if 'media/' in name and has_media == False:
                    has_media = True
        
            if has_media == False and self.csv_type == 'attachment':
                self.csv_type = "merged"
            if self.csv_type == 'attachment':
                if os.path.exists(the_storage_path):
                    shutil.rmtree(the_storage_path, ignore_errors=True)
                os.mkdir(the_storage_path)
                zip_file.extractall(the_storage_path)
                del zip_file  # Important

            # Reorder CSVs as Dataframe on parents
            df_order = list()
            for dfx in df_list:
                if len(dfx.index) > 0:
                    df_level = dfx['KEY'][0].count('/')
                    df_order.append(df_level)
                else:
                    df_order.append(len(df_list)-1)
            df_list = [df_list[i] for i in df_order]

            # Merge Dfs with their parents and image details #(piece of art)
            if df_list:
                df_original = df_list[0]
                # Drop the rejected records [Rejected are not dropped so we can use them later]
                # df_original = df_original[df_original['ReviewState']
                #                         != 'rejected']
                df_original = df_original.apply(
                    lambda col: col.replace('Specimen ', '', regex=True))
                df_flat = df_original
                df_attachments = df_original
                # Merge the rest of dfs with the original
                for df_ in df_list[1:]:
                    # Ignore empty dfs
                    if len(df_.index) > 0:
                        # find foreign keys
                        parents = df_['KEY'][0].split('/')
                        df_.name = parents[-1].split('[')[0]
                        # add suffix to columns for prepare for merge
                        suffix = '_' + df_.name
                        df_ = df_.add_suffix(suffix)
                        pk = 'KEY'
                        if len(parents) > 1:
                            # Find the parent key
                            pk_suffix = parents[-2].split('[')[0]
                            # TODO: Investigate these cases
                            if pk_suffix.find(':') == -1:
                                pk = pk + '_' + pk_suffix
                        df_flat = df_flat.merge(
                            df_, how='left', left_on=pk, right_on='PARENT_KEY'+suffix)
                        df_attachments = df_attachments.merge(
                            df_, how='inner', left_on=pk, right_on='PARENT_KEY'+suffix)

            # find fields with images
            if self.csv_type == 'attachment':
                filenames = list()
                filename_list = list()
                # filters the columns with filename info
                if "filenames" in self.filter_dict:
                    filename_list = self.filter_dict["filenames"]
                else:
                    self.logger.warn(
                        "filenames are not defined in project filter json file in setting directory")
                # Iterate over filename groups to make one list
                dynamic_section = list()
                static_section = dict()
                object_column = self.filter_dict["object"]
                
                for filename in filename_list:
                    for section in filename:
                        if '#' not in section:
                            dynamic_section.append(section)
                        else:
                            static_section[filename.index(
                                section)] = section.replace('#', '')

                    # Make a new df from dynamic sections of the filename
                    dynamic_section = [s for s in filename if "#" not in s]
                    new_df = df_attachments[dynamic_section]

                    # Add static sections of the filename to df
                    for section in static_section:
                        new_df.insert(
                            section, static_section[section], static_section[section])

                    # Drop duplication from hirarchy structure
                    # IMPORTANT [DESIGN LIMTATION FOR 3 LAYER HIRARCHY DATA STRUCTURE FOR ATTACHMENTS. MAX=2]
                    cols = new_df.columns.values
                    new_df.drop_duplicates(
                        subset=dynamic_section, inplace=True)               # TODO: Copy Warning     
                    concat_df = df_attachments.copy()
                    concat_df.drop_duplicates(
                        subset=dynamic_section, inplace=True)
                    # Clean up
                    new_df[object_column].replace('Specimen ', '',regex=True, inplace=True)  # TODO: Copy Warning
                    new_df[object_column].replace('http://', '',regex=True, inplace=True)  # TODO: Copy Warning
                    new_df[object_column].replace('https://', '',regex=True, inplace=True)  # TODO: Copy Warning
                    new_df.replace('/', '_',regex=True, inplace=True)

                    # Add primary NURI column
                    # JOIN the columns to construct a full filename
                    filename_col = new_df[cols[0]].astype(str)
                    for col in cols[1:]:
                        filename_col += '__' + new_df[col].astype(str)
                    # Extend the list of filenames

                    concat_df.insert(0, 'filename', filename_col)
                    # Drop nans and repeated filenames
                    self.logger.debug(str(concat_df.shape))
                    # concat_df = concat_df.apply(lambda col: col.replace('nan__',''))
                    # TODO: make sure about the order of the following two lines
                    # concat_df.drop_duplicates()
                    # concat_df = concat_df[concat_df['filename'].str.contains(
                    #     "__nan") == False]
                    concat_df['filename'].replace('__nan', '',regex=True, inplace=True)
                    self.logger.debug(str(concat_df.shape))
                    # list of lists
                    filenames.append(concat_df)

                # Concat all dataframes together and drop duplicate rows
                filename_df = (pd.concat(filenames))
                # Reset index of the new df
                filename_df.reset_index(drop=True, inplace=True)
                # Delete records with empty filenames or without image extentions
                filename_df.drop(filename_df[filename_df['filename'].str.contains('.jpg|.tif|.png') == False].index, inplace=True)
                self.logger.debug("How many files: {}".format(len(filename_df.index)))

                # filenames rename to the new filename list
                for df_index in filename_df.index:                    
                    media_path = the_storage_path + "/media/"
                    filename = filename_df['filename'][df_index]
                    old_filename = filename.split("__")[-1]
                    # Delete rejected files
                    if str(filename_df.loc[df_index, 'ReviewState']).lower() == ('rejected'):
                        os.remove(media_path + old_filename)
                        continue
                    if '.jpg' in filename.lower() or '.tif' in filename.lower() or '.png' in filename.lower():                        
                        os.rename(media_path + old_filename,
                                media_path + filename)                            
                # TODO : Rejected records still have files
        
            if self.csv_type == 'merged':
                df_output = df_flat
            elif self.csv_type == 'attachment':
                df_output = filename_df.sort_values(
                    by="SubmissionDate", ignore_index=True)
            else:
                df_output = df_original

            # Drop rejected and ODK unwated columns 
            df_output = df_output[df_output['ReviewState'] != 'rejected']
            to_go_list = list()
            df_columns = list(df_output.columns.values)
            for unwanted in self.odk_unwanted_columns:
                to_go_list += [s for s in df_columns if unwanted in s]
            self.logger.debug('unwanted columns: {}'.format(str(to_go_list)))
            df_output.drop(to_go_list, axis=1, inplace=True)

        return df_output

    def save_dataset(self, user, filename, df):
        # Store a CSV object in memroy storage with buffer
        buffer = StringIO()
        df.to_csv(buffer, index=False, header=True, encoding='utf-8')
        # df_flat.to_csv(storage_path + csv_filename + ".csv",index=False,header = True, encoding='utf-8')
        buffer.seek(0)
        csv_file = File(file=buffer, name=filename + ".csv")
        # Save into the database if not exist
        queryset = Dataset.objects.order_by(
            '-datetime').filter(params=self.params)

        dataset = None
        if queryset:
            dataset = queryset[0]
            # lastSubmission = dataset.params.split("/")[-1]

        else:
            dataset = Dataset()
        dataset.CSV.delete()
        dataset.CSV = csv_file
        dataset.CSV.name = filename + ".csv"
        dataset.params = self.params
        dataset.origin_id = 1
        dataset.save()
        if dataset.id:
            return dataset.id
        return -1


    def current_datetime(self):
        right_now = datetime.now()
        date_time = right_now.strftime("%d/%m/%Y, %H:%M:%S")
        return date_time


    def handle(self, *args, **options):
        # basic funtion to run the management commands, execustes the import scripts and enrichment modules
        current_user = User.objects.get(username=options['user'])
        params = options['params']
        csv_filename = params[1].split(
            ' ')[0] + '_' + params[2].replace("/", "_").replace(" ", "_")
        import_flag = False
        # Init global vars
        self.init_global(options['params'], options['csv_type'])

        # create log record
        report = Report.objects.create(user=current_user,
                                        report_type_id=1,
                                        flag=import_flag,
                                        comment= "Began at: " + 
                                        self.current_datetime() +
                                        "\n" + str(params))

        # IMPORT CSV
        df_flat = self.import_data(options['params'], csv_filename)

        # Save data in the model
        dataset_id = -1

        if df_flat is not None:
            dataset_id = self.save_dataset(current_user, csv_filename, df_flat)

            # Attachments storage management from temp to media root
            storage_path = str(settings.MEDIA_ROOT / "temp")
            temp_dir = storage_path + "/" + csv_filename
            temp_path = temp_dir + "/media/"
            image_path = str(settings.MEDIA_ROOT / "dataset" / "image")
            new_path = str(settings.MEDIA_ROOT / "dataset" /
                           "image") + "/" + str(dataset_id)

            if self.csv_type == 'attachment':
                shutil.rmtree(new_path, ignore_errors=True)
                # os.makedirs(new_path)
                shutil.move(temp_path, image_path)
                os.rename(image_path + "/media",
                          image_path + "/" + str(dataset_id))
                shutil.rmtree(temp_dir, ignore_errors=True)
                dataset = Dataset.objects.get(id=dataset_id)
                dataset.files = new_path
                dataset.save()
            os.remove(temp_dir + ".zip") # TODO: undo this!

        # self.rename_files(df_flat)

        if dataset_id == -1:
            self.logger.error(
                "Error in importing {} An error occured".format(csv_filename))
            import_flag = False
            dataset_id = None
            # return -1
        else:
            self.logger.debug(
                "Import of the form {} is finished successfully!\n * * * * * * * * * *".format(csv_filename))
            self.logger.debug(str(dataset_id))
            import_flag = True
            # return dataset_id
        # Open Log file to store the content in the log model
        with open(self.logger.handlers[0].baseFilename, 'r') as logfile:
            logs = logfile.read()
        report.comment += ('\n' + logs + '\nEnded at: ' + self.current_datetime())
        report.dataset_id = dataset_id
        report.flag = import_flag
        report.save()

        # Clear the log file for the next time usage
        open(self.logger.handlers[0].baseFilename, "w").close()
        if report:
            return str(report.id)
        return str(-1)
