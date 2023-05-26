import os
from datetime import datetime
import shutil
from django.conf import settings
from django.contrib import admin
from io import StringIO
from django.core.management import call_command
from io import StringIO
import pandas as pd
import numpy as np
import shutil
from .models import Origin, Dataset, Report
import json
import time
import logging
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.gevent import GeventScheduler
from PIL import Image
import re
import shutil


logger = logging.getLogger('operation')

@admin.action(permissions=['change'])
def export_dataset_samba(dataset):
    # Export CSV
    CSV = dataset.CSV.file
    today = str(datetime.now().date())
    filename = dataset.CSV.name.split(
        '/')[-1].replace('.csv', '__') + today + '.csv'
    dir_name = '0' + dataset.CSV.name.split('/')[-1].replace('.csv', '')[5:]
    export_path = str(settings.MEDIA_ROOT / "smb/10_ODK_Images" /
                      dir_name)  # / str(dataset.id))
    if not os.path.exists(export_path):
        os.makedirs(export_path)
    export_file = export_path + "/{}".format(filename)  # / str(dataset.id))
    if os.path.exists(export_file):
        os.remove(export_file)
    with open(export_file, "wb") as the_file:
        shutil.copyfileobj(CSV, the_file)

    # Export Files
    if dataset.files:
        source_path = dataset.files
        sink_path = export_path + "/files"
        if os.path.exists(sink_path):
            shutil.rmtree(sink_path)  # Use with caution!
        os.makedirs(sink_path)
        for file_name in os.listdir(source_path):
            file_path = source_path + "/" + file_name
            shutil.copy(file_path, sink_path)

@admin.action(permissions=['change'])
def export_dataset_easydb(dataset, user, attachment):
    # Export Files to easydb
    log_id = None
    dataset_id = dataset.id  # queryset.values_list('id', flat=True)
    # CSV = dataset.CSV  # queryset.values_list('csv', flat=True)
    files = dataset.files  # queryset.values_list('files', flat=True)
    if len(files) > 0:
        call_command_out = StringIO()
        # Export with pictures
        call_command('easydb_export', user, files, dataset_id,
                     attachment, stdout=call_command_out)
        log_id = call_command_out.getvalue().split('\n')[0]
    return log_id

@admin.action(permissions=['change'])
def export_dataset_picturae_sample(username):
    # Export picturae dataset to easydb
    # dataset_path = "/home/mjv/Work/archive/smb_data/06_Projekte_Digitalisierung/03_Ext_Mass Digitization Picturae/sampleDelivery220705/coll.mfn-berlin.de_u_24f418"  # queryset.values_list('files', flat=True)
    dataset_path = str(settings.MEDIA_ROOT / 'smb/06_Projekte_Digitalisierung/03_Ext_Mass Digitization Picturae/sampleDelivery220705/coll.mfn-berlin.de_u_24f418')
    attachment = 1
    call_command_out = StringIO()
    call_command('picturae_easydb',username, dataset_path, attachment, stdout=call_command_out)
    log_id = call_command_out.getvalue().split('\n')[0]
    return log_id

def import_picturae(user,path,attachment):
    """
    calls the import function as a management commands for mass_digi_integration.py
    """
    call_command_out = StringIO()
    call_command('mass_digi_integration',user,*path,attachment, stdout=call_command_out)
    return call_command_out.getvalue().split('\n')[0]


@admin.action(permissions=['change'])
def integrate_picturae(request, filtered_datasets, attachment):
    c = 0
    for dataset in filtered_datasets:
        try:
            dataset["dataset"].encode()

            report_id = import_picturae(request.user, [dataset], attachment)
            
            c += 1
            # make the flag True to wait
            flag = True
            while(flag):
                m = 1
                time.sleep(m * 60)
                stats = json.loads((Report.objects.get(pk=report_id)).dataset.stats.replace("'",'"'))
                if (stats["specimen_integrated_count"] / stats["specimen_count"]) > 0.8 or c < 2:
                    flag = False

        except UnicodeDecodeError:
            logger.warning("Invalid Dataset name: {}".format(dataset["dataset"]))
            continue

@admin.action(permissions=['change'])
def export_dataset_picturae(modeladmin, request, queryset):
    # vertical concatination of all selected querysets to merge
    dataset_list = [json.loads(s.params.replace("'",'"')) for s in queryset]
    # Export picturae dataset to easydb
    # dataset_path = "/home/mjv/Work/archive/smb_data/06_Projekte_Digitalisierung/03_Ext_Mass Digitization Picturae/sampleDelivery220705/coll.mfn-berlin.de_u_24f418"  # queryset.values_list('files', flat=True)
    # dataset_path = str(settings.MEDIA_ROOT / 'smb/06_Projekte_Digitalisierung/03_Ext_Mass Digitization Picturae/sampleDelivery220705/coll.mfn-berlin.de_u_24f418')
    picturae_list = list()
    # dataset_path = str(settings.MEDIA_ROOT / 'smb/11_Picturae/01_delivered')
    origin_path = Origin.objects.get(id=2).comment
    local_path = "/run/user/1000/gvfs/smb-share:server=192.168.201.123,share=digi1" + origin_path
    pro_path = str(settings.MEDIA_ROOT / 'smb') + origin_path
    dataset_path = ""
    if os.environ.get('SMB_PATH'):
        dataset_path = local_path #
    else:
        dataset_path = pro_path
    for dataset_obj in dataset_list:
        if 'mfn' in dataset_obj['dataset']:
            file_path = dataset_obj['link']  # dataset_path + '/' + dataset_obj['dataset']
            # checksum_path = file_path + '/' + dataset_obj['dataset'] + '__SHA-256.sum'
            # if not os.path.exists(checksum_path):
            #     continue
            is_imported = ""
            is_integrated = ""
            dataset = Dataset.objects.filter(files__contains=dataset_obj['dataset'])
            if len(dataset) > 0:
                is_imported = "checked"
                if dataset[0].integrated is True:
                    is_integrated = "checked"
                if len(dataset) > 1:
                    logger.warn("Duplicated Dataset has been spotted for {}. ".format(dataset_obj['dataset']))
            # creation_date =  (datetime.datetime.fromtimestamp(os.path.getmtime(checksum_path))).strftime("%Y-%m-%dT%H:%M:%S")            
            # picturae_dict = {"dataset": dataset_obj['dataset'],"link": file_path,"status_imported":is_imported, "status_integrated": is_integrated, "creation_date":creation_date}            
            picturae_list.append(dataset_obj)
    picturae_list = sorted(picturae_list, key=lambda d: d['creation_date']) 

    # job in background
    integration_scheduler = None
    if os.environ.get('SMB_PATH'):
        integration_scheduler = BackgroundScheduler()   
    else:
        integration_scheduler = GeventScheduler()                 
    if len(picturae_list) > 0:
        integration_scheduler.add_job(integrate_picturae,
                        kwargs={"request":request, "filtered_datasets": picturae_list, "attachment": 1},
                        replace_existing=True, id="integrate_easydb_batch" + picturae_list[0]["dataset"])
    # # scheduler.logger()
        integration_scheduler.start()

    # attachment = 1
    # call_command_out = StringIO()
    # call_command('mass_digi_integration',request.user.username, picturae_list, attachment, stdout=call_command_out)
    # log_id = call_command_out.getvalue().split('\n')[0]
    # return log_id

export_dataset_picturae.short_description = "Integrate Picturae Datasets"

# def validate_data(json_object, validator = {'nuri': 'http://coll\.mfn-berlin\.de/[\w/._]+$'}):      
#     for j in json_object:
#         if "barcode" in json_object.keys() or \
#         "drawer_name" in json_object.keys() or \
#         "resource_uri" in json_object.keys() or \
#         "scan name" in json_object.keys():
#             matched = re.match(validator['nuri'],json_object[j])
#             if matched: 
#                 json_object[j] = True
#             else: 
#                 json_object[j] = False

#         # do some regex
#         # validate
#     return json_object

# def validate_file(filename, file_path, validation = {}):
#     # pass
#     image = Image.open(file_path)
#     exifdata = image.getexif()
#     # for v in validation:            
#     # TODO: NURI validation
#     # TODO: File name
#     if "filename" in validation.keys():
#         # do some regex reg is the first arg
#         matched = re.match(validation['filename'],filename)
#         if matched: 
#             validation['filename'] = True
#         else: 
#             validation['filename'] = False
#     # TODO: Checksum
#     if "checksum" in validation.keys():
#         # generate or check checksum
#         checksum_alg = validation['checksum'] 
#         # TODO: validate
#         if checksum_alg:
#             pass
#     # TODO: File format: png for specimen, tiff for labels
#     if "format" in validation.keys():
#         if validation["format"].lower() == image.format.lower():
#             validation["format"] = True
#         else:
#             validation["format"] = False

#         # generate or check checksum
#         # validate
#         pass
#     # TODO:Colour space: it shows me just RGB
#     if "mode" in validation.keys():
#         if validation["mode"] == image.mode:
#             validation["mode"] = True
#         else:
#             validation["mode"] = False  
#         # generate or check checksum
#         # validate
#         pass

#     # TODO: Bit depth: 24 bit (or 8 bit per colour channel)
#     if "bit_depth" in validation.keys():
#         if validation["bit_depth"] == image.mode:
#             validation["bit_depth"] = True
#         else:
#             validation["bit_depth"] = False

#         # generate or check checksum
#         # validate
#         pass

#         # TODO: Ppi for labels 350, we don’t check ppi of specimen’s photo 
#     if "dpi" in validation.keys():
#         width_px, height_px = image.size
#         dpi_x, dpi_y = image.info.get("dpi")

#         # Calculate physical dimensions in inches
#         # width_in = width_px / dpi_x
#         # height_in = height_px / dpi_y
#         # # Calculate PPI (pixels per inch)
#         # ppi_x = width_px / width_in
#         # ppi_y = height_px / height_in
#         # Use the geometric mean of PPI in both directions
#         # ppi = math.sqrt(ppi_x * ppi_y)

#         if validation["dpi"] == dpi_x:
#             validation["dpi"] = True
#         else:
#             validation["dpi"] = False
#         # generate or check checksum
#         # validate
#         pass
    

#     # TODO: Compression: non
#     if "compression" in validation.keys():
#         # generate or check checksum
#         # validate
#         pass
    
#     image.close()
#     return validation

# @admin.action(permissions=['view'])
# def quality_check(queryset):
#     query_list = list()
#     for query in queryset:
#         try:
#             for specimen_obj in query.JSON:
#                 if "validation" in query.JSON[specimen_obj]:
#                     for v in query.JSON[specimen_obj]['validation']:
#                         if query.JSON[specimen_obj]['validation'][v] == False:
#                             stats_dict["specimen_invalid_count"] += 1  
#                             stats_dict["specimen_invalid"] += str({specimen_obj:query.JSON[specimen_obj]['validation']})
#                             break                                         
#                 for image_obj in query.JSON[specimen_obj]['images']:
#                     if "validation" in image_obj:
#                         for v in image_obj["validation"]:
#                             if image_obj["validation"][v] == False:
#                                 stats_dict["image_invalid_count"] += 1
#                                 stats_dict["image_invalid"] += str({image_obj['file_name']:image_obj['validation']})

#                 for image in image_list:
#                     filename = image["file_name"]
#                     file_path = files_path + '/' + filename
                    
#                     image_validators = {'mode':'RGB',
#                                 'filename':'^[\w-]+_(stacked|processed_stack|label)_\d{4}\.(png|tif)$',
#                                 'checksum':'SHA-256'}
#                     if image["type"] == "label":
#                         image_validators['dpi'] = 350
#                         image_validators['format'] = 'tif'
#                     else:
#                         image_validators['format'] = 'png'

#         except:
#             print("Error")



@admin.action(permissions=['view'])
def export_validation_report(queryset):
    query_list = list()
    for query in queryset:
        try:
            stats_dict = dict()
            stats_dict["dataset"] = query.files.split('/')[-1]
            stats_dict["integrated"] = query.integrated
            stats_dict["validated"] = query.validated
            stats_dict["creation_datetime"] = query.creation_datetime
            stats_dict["integration_datetime"] = query.datetime
            stats_dict.update(json.loads(query.stats.replace("'",'"')))
            stats_dict["specimen_invalid_count"] = 0
            stats_dict["image_invalid_count"] = 0
            stats_dict["specimen_invalid"] = ''
            stats_dict["image_invalid"] = ''

            for specimen_obj in query.JSON:
                if "validation" in query.JSON[specimen_obj]:
                    for v in query.JSON[specimen_obj]['validation']:
                        if query.JSON[specimen_obj]['validation'][v] != True:
                            stats_dict["specimen_invalid_count"] += 1  
                            stats_dict["specimen_invalid"] += str({specimen_obj:query.JSON[specimen_obj]['validation'][v]})
                            break                                         
                for image_obj in query.JSON[specimen_obj]['images']:
                    if "validation" in image_obj:
                        for v in image_obj["validation"]:
                            if image_obj["validation"][v] != True:
                                stats_dict["image_invalid_count"] += 1
                                stats_dict["image_invalid"] += str({image_obj['file_name']:image_obj['validation'][v]})
                                break
            query_list.append(stats_dict)
        except:
            print("Error")
    df = pd.DataFrame(query_list)

    buffer = StringIO()
    df.to_csv(buffer, index=False, header=True, encoding='utf-8') # columns=["1.collectionobject.name"]
    # Always go to beginning of the file
    buffer.seek(0)
    return buffer


@admin.action(permissions=['view'])
def export_csv_portal(queryset):
    df = pd.concat(map(pd.read_csv, [s.CSV for s in queryset]), axis=0)
    buffer = StringIO()
    df_select = df[['barcode', 'grouping_and_rehousing_family','grouping_and_rehousing_genus','grouping_and_rehousing_species','grouping_and_rehousing_species_accreditation']]
    df_select['scientific_name'] = np.where(pd.isna(df_select['grouping_and_rehousing_genus']) | pd.isna(df_select['grouping_and_rehousing_species']),
                                            "",
                                            df_select['grouping_and_rehousing_genus'].astype(str) + " " + df_select['grouping_and_rehousing_species'].astype(str)
                                            )
    df_select.loc[pd.isna(df_select['grouping_and_rehousing_genus']) , "scientific_name"] = ""
    df_select.loc[pd.isna(df_select['grouping_and_rehousing_species']) , "scientific_name"] = ""

    df_select['grouping_and_rehousing_species_accreditation'] = np.where(pd.isna(df_select['scientific_name']) | pd.isna(df_select['grouping_and_rehousing_species_accreditation']),
                                                                        df_select['scientific_name'],
                                                                        df_select['scientific_name'].astype(str) + " " + df_select['grouping_and_rehousing_species_accreditation'].astype(str))

    df_select['grouping_and_rehousing_species'] = df_select['scientific_name']
    df_select.drop('scientific_name', axis=1, inplace=True)    
    columns = ['_1.collectionobject.name', '_1_9-determinations,4.taxon.Family', '_1_9-determinations_4.taxon.Genus', '_1_9-determinations_4.taxon.Species', '_1_9-determinations_4.taxon.name']

    df_select.columns = columns
    
    df_select.to_csv(buffer, index=False, header=True, encoding='utf-8')
    # Always go to beginning of the file
    buffer.seek(0)
    return buffer

@admin.action(permissions=['view'])
def export_csv_specify(queryset):
    # vertical concatination of all selected querysets to merge
    df = pd.concat(map(pd.read_csv, [(s.CSV) for s in queryset]), axis=0)
    # df_unique = df.drop_duplicates('meta-instanceName')

    df.to_csv('files/mammals_all.csv', index=False)
    # old lcoations: http://coll.mfn-berlin.de/u/974b6d , http://coll.mfn-berlin.de/u/974b6c
    # http://coll.mfn-berlin.de/u/717c34 , http://coll.mfn-berlin.de/u/717c35

    # Fill in the gap, mark the old storage locations
    olds = ['http://coll.mfn-berlin.de/u/974b6d',
            'http://coll.mfn-berlin.de/u/974b6c',
            'http://coll.mfn-berlin.de/u/717c34',
            'http://coll.mfn-berlin.de/u/717c35']
    news = ['http://coll.mfn-berlin.de/u/974bab',
            'http://coll.mfn-berlin.de/u/974b9b',
            'http://coll.mfn-berlin.de/u/974b95',
            'http://coll.mfn-berlin.de/u/974bca',
            'http://coll.mfn-berlin.de/u/974bcb']
    for x in olds:
        df.loc[df['storage-storage_code'] == x,
               'storage-storage_new_old'] = 'old'
    for x in news:
        df.loc[df['storage-storage_code'] == x,
               'storage-storage_new_old'] = 'new'

    df.loc[df['storage-storage_code'].str.find('http')
           == -1, 'storage-storage_new_old'] = 'old'
    df.loc[df['storage-storage_code'].str.find('ZMB')
           != -1, 'storage-storage_new_old'] = 'old'
    df['image_keywords_images_group'].replace(
        '_overview', '', regex=True, inplace=True)
    df['image_keywords_images_group'].replace(
        '_dorsal', '', regex=True, inplace=True)
    df['image_keywords_images_group'].replace(
        '_lateral', '', regex=True, inplace=True)
    df['image_keywords_images_group'].replace(
        '_ventral', '', regex=True, inplace=True)
    df['image_keywords_images_group'].replace(
        'head_', '', regex=True, inplace=True)
    df['image_keywords_images_group'].replace(
        'skin_', '', regex=True, inplace=True)
    df['image_keywords_images_group'].replace(
        'skull_fragment', 'fragment', regex=True, inplace=True)
    df['image_keywords_images_group'].replace(
        '_', ' ', regex=True, inplace=True)

    # Temp export
    df.to_csv('files/mammals_compiled1.csv', index=False)

    # Find old and new storage location
    df_old = df.loc[df['storage-storage_new_old']
                    == 'old'].reset_index(drop=True)
    df_old.drop_duplicates(subset=[
                           'storage-storage_code', 'object-object_code', 'image_keywords_images_group'], inplace=True)
    df_new = df.loc[df['storage-storage_new_old']
                    == 'new'].reset_index(drop=True)
    df_notnew = df.loc[df['storage-storage_new_old']
                       != 'new'].reset_index(drop=True)
    df_notold = df.loc[df['storage-storage_new_old']
                       != 'old'].reset_index(drop=True)
    df_notold.drop_duplicates(subset=[
                              'storage-storage_code', 'object-object_code', 'image_keywords_images_group'], inplace=True)
    # Perform left join on NURI
    df_merged = df_old.merge(df_notold, how='inner', left_on='object-object_code',
                             right_on='object-object_code', suffixes=('_old', '_new'))
    # df_merged = df_old.merge(df_notold, how='left', left_on=['object-object_code','image_keywords_images_group'], right_on=['object-object_code','image_keywords_images_group'], suffixes=('_old', '_new'))

    # The storage locality is the NURI of the storage location
    df_merged['storage_locality'] = np.where(pd.isna(
        df_merged['storage-storage_code_new']), df_merged['storage-storage_code_old'], df_merged['storage-storage_code_new'])

    # Override empty keywords with newers
    df_merged['image_keywords_images_group_new'] = np.where(pd.isna(
        df_merged['image_keywords_images_group_new']), df_merged['image_keywords_images_group_old'], df_merged['image_keywords_images_group_new'])

    # The history of storage locality
    df_merged['storage_history'] = '{' + '"storage1":' + df_merged['storage-storage_code_old'].astype(str) + \
        ',' + '"storage1_timestamp":' + df_merged['SubmissionDate_old'].astype(str) + \
        ',' + '"storage2":' + df_merged['storage-storage_code_new'].astype(str) + \
        ',' + '"storage2_timestamp":' + \
        df_merged['SubmissionDate_new'].astype(str) + '}'

    # Clean up
    df_merged = df_merged.apply(lambda col: col.replace(
        ',"storage2":nan,"storage2_timestamp":nan', '', regex=True))
    df_merged = df_merged.apply(
        lambda col: col.replace('horns', 'horn', regex=True))
    df_merged['catalog_number'] = df_merged['object-object_code'].str.split(
        'u/', n=1, expand=True)[1]
    df_merged['image_keywords_images_group_old'] = df_merged['image_keywords_images_group_old'].str.split(
        '_', n=1, expand=True)[0]

    # rename and select the output
    keywords = ['skull', 'horns', 'antlers',
                'mandible', 'taxidermy']  # 'label','other']

    df_rename = {'object-object_code': 'object_code',
                 'catalog_number': 'GIN',
                 'storage-storage_code_old': 'storage_code_old',
                 # 'SubmissionDate_old':'SubmissionDate_old',
                 'storage-storage_code_new': 'storage_code_new',
                 # 'SubmissionDate_new':'SubmissionDate_new',
                 # 'image_keywords_images_group_old':'keywords',
                 'image_keywords_images_group_new': 'keywords',
                 'storage_locality': 'storage_locality',
                 'storage_history': 'storage_history'
                 }
    other_columns = []
    df_merged.rename(columns=df_rename, inplace=True)
    # Select proper columns and rows
    df_selected = df_merged[df_rename.values()]
    df_selected = df_selected.drop_duplicates()
    # Save to memory as CSV to download
    buffer = StringIO()
    df_selected.to_csv(buffer, index=False, header=True, encoding='utf-8')
    # Always go to beginning of the file
    buffer.seek(0)
    return buffer

def sample_labels(queryset):
    query_list = list()
    mfn_out_path = "/11_Picturae/02_transcripts/00_mfn_out"  
    mfn_backup_path =   "/11_Picturae/01_backup"  
    pro_path = str(settings.MEDIA_ROOT / 'smb')
    backup_base = str(settings.MEDIA_ROOT / 'backup') + mfn_backup_path
    storage_path = ""
    export_base = ""
    if os.environ.get('SMB_PATH') and os.environ.get('LOCAL_PATH'):
        storage_path = os.environ.get('SMB_PATH')  # os.environ.get('SMB_PATH') 
        export_base = os.environ.get('LOCAL_PATH')
    else:
        storage_path = pro_path
        export_base = pro_path

    for query in queryset:
        try:
        # if True:
            json_object = query.JSON
            dataset_path = query.files.replace('/media/smb','')
            # origin_path = query.origin.comment
            export_path = export_base + mfn_out_path + '/' + dataset_path.split('/')[-1]
            backup_path = backup_base + '/' + dataset_path.split('/')[-1]
            json_path = export_path + '/' + dataset_path.split('/')[-1] + '.json'
            if not os.path.exists(export_path):
                    os.mkdir(export_path)
            # if not os.path.exists(backup_path):
            #         os.mkdir(backup_path)
            print(storage_path + dataset_path, "\n")
            print(backup_path, "\n")
            shutil.copytree(storage_path + dataset_path,backup_path, dirs_exist_ok=True)
            dataset.dataset_status.add(5)
            for specimen_obj in json_object:
                image_list = list()
                for image in json_object[specimen_obj]['images']:
                    specimen_path = storage_path + dataset_path + '/' + specimen_obj
                    image_path = specimen_path + '/' + image['file_name']
                    if image['type'] == 'label':
                        image_path = storage_path + dataset_path + '/' + specimen_obj + '/' + image['file_name']
                        new_path = export_path + '/' + image['file_name']
                        image_list.append(image)
                        if not os.path.isfile(new_path):
                            shutil.copy(image_path, export_path)                
                json_object[specimen_obj]['images'] = image_list
                # remove specimens from datasets
                # backup_dir = backup_path + '/' + specimen_obj
                shutil.rmtree(specimen_path)
            dataset = Dataset.objects.get(id=query.id)
            dataset.dataset_status.add(4)
            dataset.dataset_status.add(5)
            dataset.save()
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_object, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.warning("Operation failed: {}".format(str(e)))
@admin.action(permissions=['change'])
def sample_files(modeladmin, request, queryset):
            # job in background
    integration_scheduler = None
    if os.environ.get('SMB_PATH'):
        integration_scheduler = BackgroundScheduler()   
    else:
        integration_scheduler = GeventScheduler()                 
    if len(queryset) > 0:
        integration_scheduler.add_job(sample_labels,
                        kwargs={"queryset":queryset},
                        replace_existing=True, id="label_export_" + str(queryset[0]))
    # # scheduler.logger()
        integration_scheduler.start()

sample_files.short_description = "Sample Labels"

@admin.action(permissions=['change'])
def rotate_images(modeladmin, request, queryset):    
    # Rotate images to left
    def rotate_90():
        for dataset in queryset:
            # Rotate on spot after renaming! # ONLY FOR SOME DATASETS
            media_path = dataset.files + '/'
            for filename in os.listdir(media_path):
                original_image = Image.open(media_path + filename)
                rotated_image1 = original_image.rotate(90)
                rotated_image1.save(media_path + filename)
                
    # scheduler = BackgroundScheduler()
    scheduler = GeventScheduler()
    scheduler.add_job(rotate_90, replace_existing=True,id="rotate90")
    scheduler.start()

rotate_images.short_description = "Rotate Images To Left"

