from datetime import datetime, timedelta
from xml.dom.pulldom import default_bufsize
from textwrap import dedent

from requests import request
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.models import Variable
import json
import requests
from datetime import datetime

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['majid.vafadar@mfn.berlin'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'schedule_interval': '@daily',
    'start_date': datetime(2023, 1, 1),
    'execution_date': datetime(2023, 1, 2, 18, 0, 0)
}

# @task(task_id=f'sleep_for_{i}')
def test_wf():
    print ('*The test is okay. workflow is running!*')

with DAG(
    'odk_data_integration',
    default_args=default_args,
    description='Integrate ODK Data Pipeline',
    catchup=False,
    tags=['odk'],
) as dag:
    task_test_workflow = PythonOperator(
        task_id='test_workflow',
        python_callable=test_wf,
        depends_on_past=False,
        retries=2,
    )
    task_import_odk1 = SimpleHttpOperator(
        task_id="import_odk1",
        http_conn_id="datahub_api",
        method="POST",
        endpoint='api/odkimport/{}/'.format(Variable.get("PROFILING_MICROSLIDES_ZOOLOGIE_V1")),
        # data=json.dumps({"priority": 5}),
        headers={"content-type": "application/x-www-form-urlencoded", 
                "Authorization": "Basic {}".format(Variable.get("datahub_token"))}, 
        auth_type=requests.auth.HTTPBasicAuth,
        # data=Variable.get("Profiling_Microslides_Zoologie_v1.0")
        # response_check=lambda response: response.json()['json']['priority'] == 5,
        # response_filter=lambda response: json.loads(response.text),
        # extra_options: Optional[Dict[str, Any]] = None,
        # log_response: bool = False,
        # auth_type: Type[AuthBase] = HTTPBasicAuth,
    )
    task_import_odk2 = SimpleHttpOperator(
        task_id="import_odk2",
        http_conn_id="datahub_api",
        method="POST",
        endpoint='api/odkimport/{}/'.format(Variable.get("PROFILING_MICROSLIDES_ENTOMOLOGY_V1")),
        headers={"content-type": "application/x-www-form-urlencoded", 
                "Authorization": "Basic {}".format(Variable.get("datahub_token"))}, 
        auth_type=requests.auth.HTTPBasicAuth,
    )
    task_import_odk3 = SimpleHttpOperator(
        task_id="import_odk3",
        http_conn_id="datahub_api",
        method="POST",
        endpoint='api/odkimport/{}/'.format(Variable.get("MAMMALIA_UMZUEGE_V1_7")),
        headers={"content-type": "application/x-www-form-urlencoded", 
                "Authorization": "Basic {}".format(Variable.get("datahub_token"))}, 
        auth_type=requests.auth.HTTPBasicAuth,
    )
    # task_update_data_storage = SimpleHttpOperator(
    #     task_id="update_data_storage",
    #     http_conn_id="datahub_api",
    #     # http_conn_id="datahub_api_ip",
    #     method="GET",
    #     endpoint='api/origin/sambaexport/{}/'.format(),
    #     data=json.dumps({"id": 5}),
    #     headers={"content-type": "application/vnd.api+json", 
    #              "Authorization": "Basic {}".format(Variable.get("datahub_token"))},     
    #     auth_type=requests.auth.HTTPBasicAuth,   
    #     # response_check=lambda response: response.json()['json']['priority'] == 5,
    #     # response_filter=lambda response: json.loads(response.text),
    #     # extra_options: Optional[Dict[str, Any]] = None,
    #     # log_response: bool = False,
    #     # auth_type: Type[AuthBase] = HTTPBasicAuth,
    # )
    task_update_easydb = SimpleHttpOperator(
        task_id="update_easydb",
        http_conn_id="datahub_api",
        method="POST",
        endpoint='api/odkimport/{}/'.format(Variable.get("PROFILING_MICROSLIDES_ZOOLOGIE_V1")),
        # data=json.dumps({"priority": 5}),
        headers={"content-type": "application/x-www-form-urlencoded", 
                "Authorization": "Basic {}".format(Variable.get("datahub_token"))},
        auth_type=requests.auth.HTTPBasicAuth,
        # data=Variable.get("Profiling_Microslides_Zoologie_v1.0")
        # response_check=lambda response: response.json()['json']['priority'] == 5,
        # response_filter=lambda response: json.loads(response.text),
        # extra_options: Optional[Dict[str, Any]] = None,
        # log_response: bool = False,
        # auth_type: Type[AuthBase] = HTTPBasicAuth,
    )
    # task_update_dina = SimpleHttpOperator(
    #     task_id="update_dina",
    #     http_conn_id="datahub_api",
    #     method="POST",
    #     endpoint='api/odkimport/{}/'.format(Variable.get("Profiling_Microslides_Zoologie_v1.0")),
    #     # data=json.dumps({"priority": 5}),
    #     headers={"content-type": "application/x-www-form-urlencoded", 
    #             "Authorization": "Basic {}".format(Variable.get("datahub_token"))}, 
    #     auth_type=requests.auth.HTTPBasicAuth,
    #     # data=Variable.get("Profiling_Microslides_Zoologie_v1.0")
    #     # response_check=lambda response: response.json()['json']['priority'] == 5,
    #     # response_filter=lambda response: json.loads(response.text),
    #     # extra_options: Optional[Dict[str, Any]] = None,
    #     # log_response: bool = False,
    #     # auth_type: Type[AuthBase] = HTTPBasicAuth,
    # )
    # task_notify_team = PythonOperator(
    #     task_id='notify_msteam',
    #     python_callable=test_wf,
    #     depends_on_past=False,
    #     retries=2,
    # )

    task_test_workflow >> task_import_odk1 >> task_import_odk2 >> task_import_odk3 >> task_update_easydb # >> task_notify_team
    # task_test_workflow >> [ task_update_data_storage, task_update_easydb, task_update_dina] >> task_notify_team

task_test_workflow.doc_md = dedent(
    """
#### Task Documentation
You can document your task using the attributes `doc_md` (markdown),
`doc` (plain text), `doc_rst`, `doc_json`, `doc_yaml` which gets
rendered in the UI's Task Instance Details page.
![img](http://montcs.bloomu.edu/~bobmon/Semesters/2012-01/491/import%20soul.png)

"""
)

dag.doc_md = __doc__  # providing that you have a docstring at the beginning of the DAG
dag.doc_md = """
This is a documentation placed anywhere
"""  # otherwise, type it like this

# HTTP_PROXY=http://proxy.mfn.local:8080/
# HTTPS_PROXY=http://proxy.mfn.local:8080/

# scp dags/odk_import.py root@192.168.101.99:/home/majid.vafadar/repository/airflow/dags
