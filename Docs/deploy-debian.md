# Deploy do backend em Debian com HTTPS

Runbook para publicar a API do VCCCircuitLab (`apps/api`) num servidor Debian,
em contentor Docker não privilegiado, exposta ao exterior apenas por HTTPS.
Complementa `Docs/arquitetura_simulador_circuitos.md` §13 (Deploy e operação)
e o trabalho já concluído em E5-02 (`docker-compose.yml` na raiz).

## 1. Pré-requisitos

- Servidor Debian estável (ex.: Debian 12 "bookworm"), com acesso SSH.
- Docker Engine e o plugin `docker compose` instalados (`docker compose version`
  deve funcionar; não é necessário `docker-compose` standalone).
- Um domínio próprio apontado para o IP público do servidor (registo DNS A/AAAA),
  **ou** uma conta Cloudflare (gratuita) se for usada a alternativa Cloudflare
  Tunnel, que não exige DNS apontado diretamente nem portas públicas abertas.
- Firewall do servidor a bloquear por omissão todas as portas excepto SSH e, se
  aplicável, 80/443 (reverse proxy); a porta 8000 da API **nunca** deve ficar
  acessível publicamente (ver secção 6).

## 2. Preparar o servidor

Copiar apenas o necessário para correr o backend — não é preciso o repositório
inteiro em produção, mas clonar o repositório completo é a forma mais simples
de manter tudo sincronizado:

```bash
sudo mkdir -p /opt/vcccircuitlab
sudo chown "$USER":"$USER" /opt/vcccircuitlab
git clone <url-do-repositorio> /opt/vcccircuitlab
cd /opt/vcccircuitlab
```

Se preferir copiar apenas o indispensável em vez de clonar o repositório
completo, os ficheiros mínimos são `docker-compose.yml` e a pasta `apps/api/`
(com o respetivo `Dockerfile`, `requirements.txt` e `app/`).

## 3. Construir e arrancar o container

O `docker-compose.yml` da raiz já está pronto para produção (trabalho de
E5-02): corre a API como utilizador não privilegiado (uid 10001), sistema de
ficheiros só de leitura, sem capabilities, `no-new-privileges`, limites de
memória/CPU/PIDs, `restart: unless-stopped` e health check (`GET /health`).
A porta só é publicada em `127.0.0.1:${API_PORT:-8000}` — nunca em `0.0.0.0`.

```bash
cd /opt/vcccircuitlab
docker compose up -d --build
docker compose ps        # confirmar estado "healthy"
```

Variáveis opcionais (ficheiro `.env` na raiz, ou exportadas no ambiente):
`API_PORT` (porta local, omissão 8000) e `API_WORKERS` (processos Uvicorn,
omissão 1). Não alterar o `docker-compose.yml` em si — este ficheiro não deve
ser editado para publicar a porta externamente; ver secção 6.

## 4. Expor por HTTPS (reverse proxy)

A API só escuta em `127.0.0.1:8000`; é necessário um reverse proxy HTTPS à
frente para a tornar acessível ao exterior. Duas opções equivalentes — escolher
uma consoante a infraestrutura disponível:

### Opção A — Caddy standalone (HTTPS automático via Let's Encrypt)

Requer o domínio já apontado (DNS) para o IP do servidor e as portas 80/443
abertas no firewall.

1. Instalar o Caddy (repositório oficial, ver
   https://caddyserver.com/docs/install#debian-ubuntu-raspbian).
2. Copiar `deploy/Caddyfile.example` para `/etc/caddy/Caddyfile`, substituindo
   `api.example.pt` pelo domínio real.
3. `sudo systemctl restart caddy` — o Caddy obtém e renova automaticamente o
   certificado TLS.

Ver o ficheiro de exemplo em [`deploy/Caddyfile.example`](../deploy/Caddyfile.example).

### Opção B — Cloudflare Tunnel (sem portas públicas)

Alternativa quando não se quer abrir qualquer porta pública no servidor (útil
atrás de NAT/CGNAT ou por preferência de segurança); requer apenas uma conta
Cloudflare com o domínio gerido por ela.

1. `cloudflared tunnel login`, `cloudflared tunnel create vcccircuitlab-api`,
   `cloudflared tunnel route dns vcccircuitlab-api api.example.pt` (passos
   únicos, feitos uma vez, fora do ficheiro de configuração).
2. Copiar `deploy/cloudflared.example.yml` para `~/.cloudflared/config.yml`,
   substituindo o domínio e o ID do túnel.
3. `sudo cloudflared service install && sudo systemctl enable --now cloudflared`.

Ver o ficheiro de exemplo em
[`deploy/cloudflared.example.yml`](../deploy/cloudflared.example.yml).

Em ambas as opções, o reverse proxy/túnel encaminha para `127.0.0.1:8000`, que
é exactamente a porta publicada pelo `docker-compose.yml`.

## 5. Reinício automático

O reinício automático do container já está coberto por `restart: unless-stopped`
no `docker-compose.yml` (recupera de falhas da aplicação ou do Docker daemon).
Falta garantir que, após um reboot da máquina, o Docker e o `docker compose up`
arrancam sozinhos:

1. Garantir que o serviço Docker arranca no boot:

   ```bash
   sudo systemctl enable docker
   ```

2. Opcionalmente, instalar a unit systemd de exemplo
   [`deploy/vcccircuitlab-api.service`](../deploy/vcccircuitlab-api.service),
   que corre `docker compose up -d` no arranque do sistema e `docker compose
   down` ao parar o serviço (útil para reboots geridos, para além do reinício
   automático já feito pelo próprio Docker):

   ```bash
   sudo cp deploy/vcccircuitlab-api.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now vcccircuitlab-api.service
   ```

   Ajustar `WorkingDirectory`/`ExecStart`/`ExecStop` no ficheiro caso o
   repositório não esteja em `/opt/vcccircuitlab`.

## 6. CORS, rate limiting e outras restrições de rede

Este runbook cobre apenas o deploy e a exposição HTTPS. A configuração de CORS
restrito ao domínio do frontend, rate limiting e limites de tamanho/timeout é
tratada no próximo work-item (E5-04) e não é duplicada aqui — ver
`Docs/arquitetura_simulador_circuitos.md` §13 para o enquadramento.

## 7. Validação pós-deploy

```bash
curl https://<dominio>/health          # deve responder 200 com o estado da API
docker compose logs -f                 # acompanhar logs em tempo real
docker compose ps                      # confirmar estado "healthy" do container
```

Se `curl` falhar, verificar primeiro `docker compose ps` (container a correr e
"healthy") e só depois a configuração do reverse proxy/túnel — isto isola se o
problema está no backend ou na camada HTTPS externa.

## 8. Notas de segurança

- **Nunca publicar a porta 8000 (ou `API_PORT`) publicamente.** O
  `docker-compose.yml` já a liga apenas a `127.0.0.1`; não editar esse ficheiro
  para a expor em `0.0.0.0` ou numa interface pública. Todo o tráfego externo
  deve passar pelo reverse proxy/túnel HTTPS.
- Manter o firewall do servidor fechado a tudo excepto SSH e, na opção Caddy,
  80/443. Na opção Cloudflare Tunnel não é necessário abrir nenhuma porta de
  entrada.
- As variáveis `VITE_*` do frontend (GitHub Pages) **não podem conter
  segredos** — ficam públicas no bundle servido ao browser; `VITE_API_BASE_URL`
  deve apontar apenas para o domínio HTTPS público da API (ver
  `Docs/arquitetura_simulador_circuitos.md` §13, secção "Frontend no GitHub
  Pages").
- Manter o sistema operativo e o Docker atualizados (`apt update && apt
  upgrade`), e rever periodicamente os logs (`docker compose logs`) à procura
  de atividade anómala.
