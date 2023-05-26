# This image is optimized for Django & Pandas
# The orders are important to have quick build

# 1- Base Image
FROM python:3.9-slim-bullseye

# Author MAINTAINER
# LABEL MfN Berlin

# 2- Python Interpreter Flags
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV VIRTUAL_ENV=/gdm/gdm_env
# ARG CACHEBUST

# 3- Compiler & OS libraries
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential libpq-dev curl traceroute \
  && rm -rf /var/lib/apt/lists/*

# 4- User Creation and Activation
COPY ./gdm/requirements.txt /gdm/requirements.txt 
RUN useradd -U app_user && \
  install -d -m 0755 -o app_user -g app_user /gdm/
USER app_user:app_user

# 5- Python Virtual Environment and path (Important) 
RUN python3 -m venv ${VIRTUAL_ENV}
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 6- Install Python libraries in venv 
# (always in one RUN with activate)
RUN . /gdm/gdm_env/bin/activate && \
  /gdm/gdm_env/bin/python3 -m pip install -U pip && \
  pip install --no-cache-dir -r /gdm/requirements.txt 
  
# 7- Code and Directory Setup (always in the end)
WORKDIR /gdm
COPY --chown=app_user:app_user ./gdm /gdm 
COPY --chown=app_user:app_user ./storage /storage
# COPY --chown=app_user:app_user ./smb /smb

# Force no-cache for the next layer
# ARG CACHEBUST=$(time +%s)
# RUN echo "$CACHEBUST"
COPY ./files/wsgi/gunicornconf.py /gdm
COPY ./files/wsgi/uwsgi.ini /gdm
# 8- when using docker-nginx
# EXPOSE 8060




