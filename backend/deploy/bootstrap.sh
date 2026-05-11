#!/usr/bin/env bash
# bootstrap.sh — idempotent one-shot provisioner for an Ubuntu 24.04 EC2 host.
# Run once as a sudo user; safe to re-run.
#
#   curl -fsSL https://raw.githubusercontent.com/<org>/<repo>/main/backend/deploy/bootstrap.sh | bash
#
# Produces:
#   - PostgreSQL 16 with role/db `parkreserve`
#   - Caddy reverse proxy (HTTPS via Let's Encrypt)
#   - parkreserve system user + /opt/parkreserve checkout + venv
#   - systemd units for parkreserve-web + postgresql + caddy
#
# Env vars honoured (override at call time):
#   REPO_URL     default https://github.com/CITS5506-group29/parkreserve.git
#   REPO_BRANCH  default main
#   APP_DOMAIN   default "" — if set, rewrites /etc/caddy/Caddyfile in place
#   PG_PASSWORD  default "parkreserve" — change for prod

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/CITS5506-group29/parkreserve.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
APP_DOMAIN="${APP_DOMAIN:-}"
PG_PASSWORD="${PG_PASSWORD:-parkreserve}"
APP_USER="parkreserve"
APP_ROOT="/opt/parkreserve"
APP_DIR="${APP_ROOT}/backend"

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

require_root() {
    if [[ $EUID -ne 0 ]]; then
        exec sudo -E bash "$0" "$@"
    fi
}

require_root "$@"

log "apt: base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    ca-certificates curl git gnupg make \
    build-essential libpq-dev \
    python3.11 python3.11-venv python3.11-dev \
    postgresql-16 postgresql-client-16 \
    debian-keyring debian-archive-keyring apt-transport-https

log "caddy: install from official repo"
if ! command -v caddy >/dev/null 2>&1; then
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
        > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -y
    apt-get install -y caddy
fi

log "app user: ${APP_USER}"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --home "${APP_ROOT}" --shell /usr/sbin/nologin "${APP_USER}"
fi
install -d -o "${APP_USER}" -g "${APP_USER}" "${APP_ROOT}"

log "postgres: role + db"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${APP_USER}') THEN
        CREATE ROLE ${APP_USER} LOGIN PASSWORD '${PG_PASSWORD}';
    END IF;
END
\$\$;

SELECT 'CREATE DATABASE ${APP_USER} OWNER ${APP_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${APP_USER}')
\gexec
SQL

log "source: clone or update"
if [[ ! -d "${APP_ROOT}/.git" ]]; then
    sudo -u "${APP_USER}" git clone --branch "${REPO_BRANCH}" "${REPO_URL}" "${APP_ROOT}"
else
    sudo -u "${APP_USER}" git -C "${APP_ROOT}" fetch --tags origin
    sudo -u "${APP_USER}" git -C "${APP_ROOT}" checkout "${REPO_BRANCH}"
    sudo -u "${APP_USER}" git -C "${APP_ROOT}" pull --ff-only
fi

log "venv + deps"
if [[ ! -d "${APP_DIR}/.venv" ]]; then
    sudo -u "${APP_USER}" python3.11 -m venv "${APP_DIR}/.venv"
fi
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip wheel
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -e "${APP_DIR}"

log "config: .env"
if [[ ! -f "${APP_DIR}/.env" ]]; then
    install -o "${APP_USER}" -g "${APP_USER}" -m 600 /dev/null "${APP_DIR}/.env"
    cat > "${APP_DIR}/.env" <<EOF
DATABASE_URL=postgresql+psycopg://${APP_USER}:${PG_PASSWORD}@localhost:5432/${APP_USER}
MQTT_ENABLED=true
MQTT_HOST=${MQTT_HOST:-localhost}
MQTT_PORT=${MQTT_PORT:-1883}
MQTT_TLS=${MQTT_TLS:-false}
MQTT_USERNAME=${MQTT_USERNAME:-}
MQTT_PASSWORD=${MQTT_PASSWORD:-}
CORS_ORIGINS=${CORS_ORIGINS:-https://${APP_DOMAIN:-localhost}}
JWT_SECRET_KEY=$(openssl rand -hex 32)
EOF
    chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env"
    chmod 600 "${APP_DIR}/.env"
fi

log "migrate"
sudo -u "${APP_USER}" bash -c "cd ${APP_DIR} && set -a && . .env && set +a && .venv/bin/alembic upgrade head"

log "systemd units: parkreserve-web"
install -m 644 "${APP_DIR}/deploy/parkreserve-web.service" \
    /etc/systemd/system/parkreserve-web.service
systemctl daemon-reload
systemctl enable --now parkreserve-web

log "caddy: Caddyfile"
install -m 644 "${APP_DIR}/deploy/Caddyfile" /etc/caddy/Caddyfile
if [[ -n "${APP_DOMAIN}" ]]; then
    sed -i "s|<your-domain>|${APP_DOMAIN}|g" /etc/caddy/Caddyfile
fi
install -d -o caddy -g caddy /var/log/caddy
systemctl enable --now caddy
systemctl reload caddy

log "done"
systemctl --no-pager --full status \
    parkreserve-web caddy postgresql || true

cat <<EOF

Next:
  - Point DNS for '${APP_DOMAIN:-<your domain>}' at this host.
  - Edit /etc/caddy/Caddyfile if you didn't pass APP_DOMAIN, then 'systemctl reload caddy'.
  - Tail logs:
      journalctl -u parkreserve-web       -f
EOF
