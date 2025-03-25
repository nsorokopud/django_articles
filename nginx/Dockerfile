FROM jonasal/nginx-certbot:5.4.1-nginx1.27.4-alpine

ARG SCHEME
ENV SCHEME=${SCHEME}

COPY ${SCHEME}.conf.template /etc/nginx/templates/default.conf.template
