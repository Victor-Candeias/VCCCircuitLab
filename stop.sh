#!/usr/bin/env bash
# Para o frontend e a API arrancados com ./start.sh (usa os PIDs em .run/).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"

stop_service() {
  local name="$1" label="$2"
  local pid_file="$RUN_DIR/$name.pid"
  if [[ ! -f "$pid_file" ]]; then
    echo "$label não está a correr."
    return
  fi
  local pid
  pid="$(cat "$pid_file")"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "$label não está a correr (PID $pid já terminou)."
    rm -f "$pid_file"
    return
  fi
  # O start.sh usa setsid: o PID é também o grupo de processos, que inclui os filhos.
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
  fi
  rm -f "$pid_file"
  echo "$label parado (PID $pid)."
}

stop_service web "Frontend"
stop_service api "API"
