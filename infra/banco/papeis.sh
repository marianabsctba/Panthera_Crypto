#!/bin/sh
# Roda uma vez, quando o banco é criado. Cada serviço entra com o próprio papel.
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v senha_api="$CRIPTO_SENHA_API" -v senha_servicos="$CRIPTO_SENHA_SERVICOS" <<'SQL'
CREATE ROLE cripto_api LOGIN PASSWORD :'senha_api';
CREATE ROLE cripto_servicos LOGIN PASSWORD :'senha_servicos';
GRANT CONNECT ON DATABASE cripto TO cripto_api, cripto_servicos;
GRANT USAGE ON SCHEMA public TO cripto_api, cripto_servicos;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO cripto_api, cripto_servicos;
SQL
