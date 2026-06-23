#!/bin/sh

set -eu

: "${API_UPSTREAM:?API_UPSTREAM must be configured}"

envsubst '${API_UPSTREAM}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'