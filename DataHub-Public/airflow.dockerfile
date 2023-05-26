FROM apache/airflow:2.3.1

USER root

# INSTALL TOOLS
RUN apt-get update \
&& apt-get -y install libaio-dev \
postgresql-client \
ca-certificates \
curl 

#RUN mkdir extra
ENV AIRFLOW_HOME=/opt/airflow

USER airflow

RUN pip install --no-cache-dir  lxml certifi

# COPY --chown=airflow:root test_dag.py ${AIRFLOW_HOME}/dags

COPY --chown=airflow:root ./files/airflow/2.3/airflow.cfg ${AIRFLOW_HOME}/airflow.cfg
# COPY --chown=airflow:root ./files/local/customssl ${AIRFLOW_HOME}/customssl
COPY --chown=airflow:root ./files/airflow/dags ${AIRFLOW_HOME}/dags



# ENV VIRTUAL_ENV=/gdm/gdm_env
