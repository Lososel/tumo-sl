#!/usr/bin/env bash
# Render build (Build Command: bash tools/build_site.sh, Publish directory: ./public).
# Copies only the public files and writes js/config.js from the TEMP_PASSWORD env var,
# so the temporary password never lands in git.
set -euo pipefail
rm -rf public
mkdir public
cp -r index.html favicon.svg favicon-32.png apple-touch-icon.png js data public/
node -e "require('fs').writeFileSync('public/js/config.js', 'window.SITE_CONFIG = ' + JSON.stringify({ tempPassword: (process.env.TEMP_PASSWORD || '').trim() }) + ';\n')"
echo "Built public/ (temporary password: $([ -n "${TEMP_PASSWORD:-}" ] && echo set || echo EMPTY))"
