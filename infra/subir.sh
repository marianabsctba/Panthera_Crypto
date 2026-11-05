#!/bin/bash
# Instala ou atualiza o Panthera Crypto. Rodar o mesmo comando de novo atualiza.
#   sudo bash infra/subir.sh [--rede bitcoin|testnet4|signet|regtest]
set -euo pipefail

BASE=/opt/panthera-crypto
ENV="$BASE/.env"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
REDE=bitcoin

while [ $# -gt 0 ]; do
  case "$1" in
    --rede) REDE="$2"; shift 2 ;;
    *) echo "Opção desconhecida: $1" >&2; exit 1 ;;
  esac
done

case "$REDE" in
  bitcoin) CADEIA=main ;;
  testnet4|signet|regtest) CADEIA="$REDE" ;;
  *) echo "Rede desconhecida: $REDE" >&2; exit 1 ;;
esac

[ "$(id -u)" = 0 ] || { echo "Rode como root ou com sudo." >&2; exit 1; }
command -v docker >/dev/null || { echo "Precisa do Docker." >&2; exit 1; }

install -d -m 0700 "$BASE"
segredo() { head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 40; }
if [ ! -f "$ENV" ]; then
  umask 077
  cat > "$ENV" <<EOF
CRIPTO_SENHA_DONO=$(segredo)
CRIPTO_SENHA_API=$(segredo)
CRIPTO_SENHA_SERVICOS=$(segredo)
CRIPTO_RPC_USUARIO=cripto
CRIPTO_RPC_SENHA=$(segredo)
CRIPTO_FUSO=America/Sao_Paulo
EOF
fi
# A rede pode mudar entre uma execução e outra; os segredos não.
sed -i '/^CRIPTO_REDE=/d; /^CRIPTO_REDE_SERVICO=/d' "$ENV"
printf 'CRIPTO_REDE=%s\nCRIPTO_REDE_SERVICO=%s\n' "$CADEIA" "$REDE" >> "$ENV"

ARQUIVOS=(-f "$RAIZ/infra/docker-compose.yml")
[ "$REDE" = regtest ] && ARQUIVOS+=(-f "$RAIZ/infra/teste.yml")
compor() { CRIPTO_ENV="$ENV" docker compose --project-name panthera-crypto --env-file "$ENV" "${ARQUIVOS[@]}" "$@"; }
compor build
compor up -d
compor ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
echo "Console em http://127.0.0.1:${CRIPTO_PORTA_API:-8740}"
