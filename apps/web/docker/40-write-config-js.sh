#!/bin/sh
# Runs from the nginx image's entrypoint: point the built app at the API.
set -e
target=/usr/share/nginx/html/config.js
# Escape backslashes and quotes so the value stays a JS string literal.
value=$(printf '%s' "${API_BASE_URL:-}" | sed 's/\\/\\\\/g; s/"/\\"/g')
printf 'window.__API_BASE__ = "%s";\n' "$value" > "$target"
echo "config.js: API base = ${API_BASE_URL:-<build-time default>}"
