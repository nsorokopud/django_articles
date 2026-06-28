FROM jonasal/nginx-certbot:6.2.0-nginx1.31.2-alpine

ARG NGINX_TEMPLATE=https

COPY ${NGINX_TEMPLATE}.conf.template /etc/nginx/templates/default.conf.template
