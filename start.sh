#!/usr/bin/env bash
# Arranca a API (uvicorn) e o frontend (vite dev) em segundo plano, acessíveis a partir de
# outras máquinas da rede: o frontend escuta em todas as interfaces e encaminha `/api` para a
# API, que por omissão só escuta em 127.0.0.1 (não fica exposta diretamente).
#
# Variáveis opcionais: WEB_PORT (5173), API_PORT (8000), API_HOST (127.0.0.1; 0.0.0.0 expõe a
# API diretamente na rede). Parar com ./stop.sh. Logs e PIDs em .run/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"
WEB_PORT="${WEB_PORT:-5173}"
API_PORT="${API_PORT:-8000}"
API_HOST="${API_HOST:-127.0.0.1}"
UVICORN="$ROOT/apps/api/.venv/bin/uvicorn"
VITE="$ROOT/apps/web/node_modules/.bin/vite"

mkdir -p "$RUN_DIR"

is_running() {
  local pid_file="$RUN_DIR/$1.pid"
  [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

port_in_use() {
  ss -ltn "sport = :$1" 2>/dev/null | grep -q LISTEN
}

wait_for() {
  local name="$1" url="$2" log="$3"
  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then
      return 0
    fi
    if ! is_running "$name"; then
      echo "Erro: $name terminou ao arrancar. Últimas linhas de $log:" >&2
      tail -n 20 "$log" >&2
      return 1
    fi
    sleep 0.5
  done
  echo "Erro: $name não respondeu em $url (ver $log)." >&2
  return 1
}

[[ -x "$UVICORN" ]] || { echo "Falta o venv da API: ver apps/api/README.md (python -m venv .venv)." >&2; exit 1; }
[[ -x "$VITE" ]] || { echo "Faltam as dependências do frontend: correr 'pnpm install' na raiz." >&2; exit 1; }

# --- API -----------------------------------------------------------------------------------
if is_running api; then
  echo "API já está a correr (PID $(cat "$RUN_DIR/api.pid"))."
else
  port_in_use "$API_PORT" && { echo "Porta $API_PORT ocupada por outro processo." >&2; exit 1; }
  # setsid: cada serviço fica no seu grupo de processos, para o stop.sh parar também os filhos.
  setsid "$UVICORN" app.main:app --app-dir "$ROOT/apps/api" --host "$API_HOST" --port "$API_PORT" \
    >"$RUN_DIR/api.log" 2>&1 </dev/null &
  echo $! >"$RUN_DIR/api.pid"
  wait_for api "http://127.0.0.1:$API_PORT/health" "$RUN_DIR/api.log"
  echo "API a correr em http://$API_HOST:$API_PORT (PID $(cat "$RUN_DIR/api.pid"))."
fi

# --- Frontend ------------------------------------------------------------------------------
if is_running web; then
  echo "Frontend já está a correr (PID $(cat "$RUN_DIR/web.pid"))."
else
  port_in_use "$WEB_PORT" && { echo "Porta $WEB_PORT ocupada por outro processo." >&2; exit 1; }
  (
    cd "$ROOT/apps/web"
    API_PROXY_TARGET="http://127.0.0.1:$API_PORT" setsid "$VITE" dev --host 0.0.0.0 \
      --port "$WEB_PORT" --strictPort >"$RUN_DIR/web.log" 2>&1 </dev/null &
    echo $! >"$RUN_DIR/web.pid"
  )
  wait_for web "http://127.0.0.1:$WEB_PORT/VCCCircuitLab/" "$RUN_DIR/web.log"
  echo "Frontend a correr (PID $(cat "$RUN_DIR/web.pid"))."
fi

echo
echo "Aceder em:"
echo "  http://localhost:$WEB_PORT/VCCCircuitLab/"
for ip in $(hostname -I 2>/dev/null); do
  [[ "$ip" == *:* ]] && continue
  echo "  http://$ip:$WEB_PORT/VCCCircuitLab/"
done
echo "Logs: $RUN_DIR/api.log e $RUN_DIR/web.log  ·  Parar: ./stop.sh"
