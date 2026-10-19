#!/bin/sh
# Health check periódico da API do VCCCircuitLab (E5-05), executado pelo
# vcccircuitlab-healthcheck.timer. Escreve no journal (stdout/stderr da unit).
#
# - GET /health falha (processo não responde): reinicia o container da API.
# - GET /health/ready falha (MongoDB indisponível): apenas regista um aviso —
#   reiniciar a API não resolve uma base de dados em baixo.
#
# Variáveis: API_URL (por omissão http://127.0.0.1:8000), COMPOSE_FILE
# (por omissão /opt/vcccircuitlab/docker-compose.yml).
set -u

API_URL="${API_URL:-http://127.0.0.1:8000}"
COMPOSE_FILE="${COMPOSE_FILE:-/opt/vcccircuitlab/docker-compose.yml}"

check() {
    curl --silent --show-error --fail --max-time 5 --output /dev/null "$API_URL$1"
}

if ! check /health; then
    echo "ERRO: $API_URL/health não respondeu; a reiniciar o serviço api" >&2
    docker compose -f "$COMPOSE_FILE" restart api
    exit 1
fi

if ! check /health/ready; then
    echo "AVISO: $API_URL/health/ready falhou (MongoDB indisponível?)" >&2
    exit 0
fi

echo "OK"
