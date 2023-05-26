FROM nginx:1.21.5


RUN rm /etc/nginx/conf.d/default.conf

RUN useradd -U gdm_user && \
  install -d -m 0755 -o gdm_user -g gdm_user /gdm/
# USER gdm_user:gdm_user

# INSTALL TOOLS
RUN apt-get update \
&& apt-get -y install curl vim

COPY ./files/nginx/airflow.conf /etc/nginx/conf.d/
COPY ./files/nginx/datahub_pro.conf /etc/nginx/conf.d/
# COPY ./files/nginx/datahub_local.conf /etc/nginx/conf.d/
COPY ./files/local/customssl/* /etc/customssl/

# EXPOSE 8060