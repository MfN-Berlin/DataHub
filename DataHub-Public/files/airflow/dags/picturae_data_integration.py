from datetime import datetime, timedelta
from xml.dom.pulldom import default_bufsize
from textwrap import dedent
from airflow.decorators import dag, task
from requests import request
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.models import Variable
import json
import requests


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['majid.vafadar@mfn.berlin'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
    # 'schedule_interval': '@hourly'
}


# @task(task_id=f'sleep_for_{i}')
def test_wf():
    print ('*The test returns okay. workflow is running!*')


with DAG(
    'picturae_data_integration',
    default_args=default_args,
    description='Integrate Picturae Data Pipeline',
    # schedule_interval=timedelta(days=1),
    start_date=datetime(2022, 4, 1),
    catchup=False,
    tags=['odk'],
) as dag:
    task_test_workflow = PythonOperator(
        task_id='test_workflow',
        python_callable=test_wf,
        depends_on_past=False,
        retries=2,
    )
    task_update_easydb = SimpleHttpOperator(
        task_id="update_easydb",
        http_conn_id="datahub_api",
        method="POST",
        endpoint='api/picturaeexport/{}/'.format(1),
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

    task_test_workflow >> task_update_easydb

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
