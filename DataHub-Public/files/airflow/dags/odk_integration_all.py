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


def create_dag(dag_id,
                schedule,
                dag_number,
                default_args,
                conf):

    # @task(task_id=f'sleep_for_{i}')
    def test_wf():
        print('x')

    with DAG(
        dag_id,
        default_args=default_args,
        description='Downloads ODK submissions of an ODK form',
        schedule_interval=schedule,
        # start_date=datetime(2022, 4, 1),
        catchup=False,
        tags=['odk'],
    ) as dag:
        @task
        def task1(x):
            PythonOperator(
            task_id='test_wf',
            python_callable=test_wf,
            depends_on_past=False,
            retries=2,
            )
            print('task1 done')
        @task
        def task2(x):
            SimpleHttpOperator(
                task_id="test_connection",
                http_conn_id="datahub_api",
                method="GET",
                endpoint='api/origin',
                # data=json.dumps({"priority": 5}),
                headers={"content-type": "application/vnd.api+json",
                        "Authorization": "Basic {}".format(Variable.get("datahub_token"))},
                # response_check=lambda response: response.json()['json']['priority'] == 5,
                # response_filter=lambda response: json.loads(response.text),
                # extra_options: Optional[Dict[str, Any]] = None,
                # log_response: bool = False,
                # auth_type: Type[AuthBase] = HTTPBasicAuth,
            )
            print('task2 done')
        @task
        def task3(x):
            SimpleHttpOperator(
                task_id="extract_odk",
                http_conn_id="datahub_api",
                method="POST",
                endpoint='api/odkimport/{}/'.format(conf),
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
            print('task3 done')
        task3(task2(task1))

    task1.doc_md = dedent(
        """\
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

    # scp dags/odk_integration.py root@192.168.101.99:/home/majid.vafadar/repository/airflow/dags


# build a dag for each number in range(10)
variables = dict()
variables['Profiling_Microslides_Zoologie_v1'] = (
    Variable.get("Profiling_Microslides_Zoologie_v1"))
variables['Profiling_Microslides_Entomology_v1'] = (
    Variable.get("Profiling_Microslides_Entomology_v1"))

c = 0
for n in variables:
    c += 1
    dag_id = 'odk_integration_{}'.format(str(n))
    start_date = datetime(2022, 8, 1)
    default_args = {
        'owner': 'airflow',
        'depends_on_past': False,
        'email': ['majid.vafadar@mfn.berlin'],
        'email_on_failure': True,
        'email_on_retry': False,
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
        'start_date': datetime(2022, 8, 1),
        # 'schedule_interval': '@hourly'
    }

    schedule = '@hourly'
    dag_number = c
    conf = variables[n]

    @dag(dag_id=dag_id, start_date=start_date)
    def create_all_dag():
        create_dag(dag_id, schedule, dag_number, default_args, conf)
    
    globals()[dag_id] = create_all_dag()
