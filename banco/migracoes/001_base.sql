-- Valores sempre em satoshis, inteiros: dinheiro não passa por ponto flutuante.
-- Tabelas que crescem sem parar são particionadas por hash: a partição certa é achada pela chave, sem varrer as outras.

CREATE FUNCTION cripto_organizacao_atual() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('cripto.organizacao', true), '')::uuid $$;

CREATE TABLE organizacoes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nome text NOT NULL UNIQUE,
  criada_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE usuarios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organizacao_id uuid NOT NULL REFERENCES organizacoes(id) ON DELETE CASCADE,
  email text NOT NULL UNIQUE,
  nome text NOT NULL,
  senha text NOT NULL,
  criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessoes (
  token text PRIMARY KEY,
  usuario_id uuid NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  expira_em timestamptz NOT NULL
);
CREATE INDEX ON sessoes (expira_em);

-- Só a parte pública. A API recusa descritor com chave privada.
CREATE TABLE carteiras (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  organizacao_id uuid NOT NULL REFERENCES organizacoes(id) ON DELETE CASCADE,
  nome text NOT NULL,
  rede text NOT NULL CHECK (rede IN ('bitcoin', 'testnet4', 'signet', 'regtest')),
  descritor text,
  limite_sats bigint CHECK (limite_sats > 0),
  -- Carteira nova lê o histórico uma vez; depois disso só o fluxo do nó.
  estado text NOT NULL DEFAULT 'historico' CHECK (estado IN ('historico', 'acompanhando')),
  sincronizada_em timestamptz,
  criada_em timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organizacao_id, nome)
);
CREATE INDEX ON carteiras (organizacao_id);

-- O mesmo endereço pode estar em carteiras de organizações diferentes.
CREATE TABLE enderecos (
  endereco text NOT NULL,
  carteira_id bigint NOT NULL REFERENCES carteiras(id) ON DELETE CASCADE,
  organizacao_id uuid NOT NULL,
  rede text NOT NULL,
  ramo smallint,
  indice integer,
  usado boolean NOT NULL DEFAULT false,
  PRIMARY KEY (endereco, carteira_id)
) PARTITION BY HASH (endereco);
CREATE INDEX ON enderecos (carteira_id, ramo, indice);

-- Saídas não gastas dos endereços acompanhados: é o que permite reconhecer um gasto sem perguntar a ninguém.
CREATE TABLE saidas (
  rede text NOT NULL,
  transacao text NOT NULL,
  posicao integer NOT NULL,
  carteira_id bigint NOT NULL REFERENCES carteiras(id) ON DELETE CASCADE,
  organizacao_id uuid NOT NULL,
  endereco text NOT NULL,
  valor_sats bigint NOT NULL,
  gasta_por text,
  PRIMARY KEY (rede, transacao, posicao, carteira_id)
) PARTITION BY HASH (transacao);
CREATE INDEX ON saidas (carteira_id) WHERE gasta_por IS NULL;

CREATE TABLE movimentos (
  organizacao_id uuid NOT NULL,
  id bigint GENERATED ALWAYS AS IDENTITY,
  carteira_id bigint NOT NULL REFERENCES carteiras(id) ON DELETE CASCADE,
  transacao text NOT NULL,
  tipo text NOT NULL CHECK (tipo IN ('entrada', 'saida', 'interno')),
  valor_sats bigint NOT NULL,
  taxa_sats bigint,
  contrapartes jsonb NOT NULL DEFAULT '[]',
  estado text NOT NULL CHECK (estado IN ('mempool', 'confirmada')),
  bloco integer,
  historico boolean NOT NULL DEFAULT false,
  visto_em timestamptz NOT NULL DEFAULT now(),
  confirmada_em timestamptz,
  PRIMARY KEY (organizacao_id, id),
  UNIQUE (organizacao_id, carteira_id, transacao)
) PARTITION BY HASH (organizacao_id);
CREATE INDEX ON movimentos (organizacao_id, visto_em DESC);
CREATE INDEX ON movimentos (organizacao_id, carteira_id, visto_em DESC);
CREATE INDEX ON movimentos (bloco) WHERE bloco IS NOT NULL;
CREATE INDEX ON movimentos (organizacao_id, transacao);
-- Busca por endereço da outra ponta sem varrer a tabela.
CREATE INDEX ON movimentos USING gin (contrapartes jsonb_path_ops);

CREATE TABLE alertas (
  organizacao_id uuid NOT NULL,
  id bigint GENERATED ALWAYS AS IDENTITY,
  carteira_id bigint NOT NULL REFERENCES carteiras(id) ON DELETE CASCADE,
  movimento_id bigint,
  severidade text NOT NULL CHECK (severidade IN ('critica', 'alta', 'media', 'baixa')),
  titulo text NOT NULL,
  motivos jsonb NOT NULL DEFAULT '[]',
  criado_em timestamptz NOT NULL DEFAULT now(),
  tratado_em timestamptz,
  tratado_por text,
  nota text,
  PRIMARY KEY (organizacao_id, id)
) PARTITION BY HASH (organizacao_id);
CREATE INDEX ON alertas (organizacao_id, criado_em DESC);
CREATE INDEX ON alertas (organizacao_id, severidade) WHERE tratado_em IS NULL;
CREATE INDEX ON alertas (organizacao_id, movimento_id);

DO $$
BEGIN
  FOR i IN 0..15 LOOP
    EXECUTE format('CREATE TABLE enderecos_%s PARTITION OF enderecos FOR VALUES WITH (MODULUS 16, REMAINDER %s)', i, i);
    EXECUTE format('CREATE TABLE saidas_%s PARTITION OF saidas FOR VALUES WITH (MODULUS 16, REMAINDER %s)', i, i);
    EXECUTE format('CREATE TABLE movimentos_%s PARTITION OF movimentos FOR VALUES WITH (MODULUS 16, REMAINDER %s)', i, i);
    EXECUTE format('CREATE TABLE alertas_%s PARTITION OF alertas FOR VALUES WITH (MODULUS 16, REMAINDER %s)', i, i);
  END LOOP;
END $$;

-- Endereços que a organização conferiu: saída para fora desta agenda é o alerta que mais importa.
CREATE TABLE agenda (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  organizacao_id uuid NOT NULL REFERENCES organizacoes(id) ON DELETE CASCADE,
  endereco text NOT NULL,
  rotulo text NOT NULL,
  criado_em timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organizacao_id, endereco)
);

-- Listas públicas valem para todas as organizações.
CREATE TABLE listas (
  endereco text NOT NULL,
  lista text NOT NULL,
  PRIMARY KEY (endereco, lista)
);

CREATE TABLE listas_atualizacao (
  lista text PRIMARY KEY,
  total integer NOT NULL,
  atualizada_em timestamptz NOT NULL
);

CREATE TABLE canais (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  organizacao_id uuid NOT NULL REFERENCES organizacoes(id) ON DELETE CASCADE,
  nome text NOT NULL,
  tipo text NOT NULL CHECK (tipo IN ('ntfy', 'webhook')),
  url text NOT NULL,
  severidade_minima text NOT NULL DEFAULT 'alta' CHECK (severidade_minima IN ('critica', 'alta', 'media', 'baixa')),
  ativo boolean NOT NULL DEFAULT true,
  ultimo_envio_em timestamptz,
  ultimo_erro text
);
CREATE INDEX ON canais (organizacao_id);

-- Filas. Cada serviço pega um lote com FOR UPDATE SKIP LOCKED: quantas cópias rodarem, nenhuma pega o mesmo item.

-- Transação que tocou algum endereço acompanhado, já com as entradas resolvidas.
CREATE TABLE fila_transacoes (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  rede text NOT NULL,
  transacao text NOT NULL,
  carteiras bigint[] NOT NULL,
  dados jsonb NOT NULL,
  historico boolean NOT NULL DEFAULT false,
  tentativas integer NOT NULL DEFAULT 0,
  disponivel_em timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON fila_transacoes (disponivel_em);

CREATE TABLE fila_envios (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  organizacao_id uuid NOT NULL,
  alerta_id bigint NOT NULL,
  canal_id bigint NOT NULL REFERENCES canais(id) ON DELETE CASCADE,
  tentativas integer NOT NULL DEFAULT 0,
  disponivel_em timestamptz NOT NULL DEFAULT now(),
  erro text
);
CREATE INDEX ON fila_envios (disponivel_em);

-- Trabalho pesado e raro: ler o histórico de carteira nova, abrir folga de endereços.
CREATE TABLE fila_tarefas (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tipo text NOT NULL CHECK (tipo IN ('historico', 'folga')),
  carteira_id bigint NOT NULL REFERENCES carteiras(id) ON DELETE CASCADE,
  tentativas integer NOT NULL DEFAULT 0,
  disponivel_em timestamptz NOT NULL DEFAULT now(),
  erro text,
  UNIQUE (tipo, carteira_id)
);
CREATE INDEX ON fila_tarefas (disponivel_em);

-- Último bloco lido em cada rede, para continuar de onde parou e perceber reorganização.
CREATE TABLE blocos (
  rede text NOT NULL,
  altura integer NOT NULL,
  hash text NOT NULL,
  lido_em timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (rede, altura)
);

-- Cada serviço avisa que está vivo; a tela mostra quem parou.
CREATE TABLE servicos (
  nome text PRIMARY KEY,
  visto_em timestamptz NOT NULL DEFAULT now(),
  detalhe jsonb NOT NULL DEFAULT '{}'
);

-- A API só enxerga a organização da sessão. Os serviços de fundo atravessam organizações e não passam por aqui.
DO $$
DECLARE tabela text;
BEGIN
  FOREACH tabela IN ARRAY ARRAY['organizacoes', 'carteiras', 'enderecos', 'saidas', 'movimentos', 'alertas', 'agenda', 'canais'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tabela);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tabela);
  END LOOP;
END $$;
CREATE POLICY isolamento ON organizacoes TO cripto_api USING (id = cripto_organizacao_atual());
CREATE POLICY isolamento ON carteiras TO cripto_api USING (organizacao_id = cripto_organizacao_atual()) WITH CHECK (organizacao_id = cripto_organizacao_atual());
CREATE POLICY isolamento ON enderecos TO cripto_api USING (organizacao_id = cripto_organizacao_atual()) WITH CHECK (organizacao_id = cripto_organizacao_atual());
CREATE POLICY isolamento ON saidas TO cripto_api USING (organizacao_id = cripto_organizacao_atual());
CREATE POLICY isolamento ON movimentos TO cripto_api USING (organizacao_id = cripto_organizacao_atual());
CREATE POLICY isolamento ON alertas TO cripto_api USING (organizacao_id = cripto_organizacao_atual());
CREATE POLICY isolamento ON agenda TO cripto_api USING (organizacao_id = cripto_organizacao_atual()) WITH CHECK (organizacao_id = cripto_organizacao_atual());
CREATE POLICY isolamento ON canais TO cripto_api USING (organizacao_id = cripto_organizacao_atual()) WITH CHECK (organizacao_id = cripto_organizacao_atual());
CREATE POLICY servicos ON organizacoes TO cripto_servicos USING (true) WITH CHECK (true);
CREATE POLICY servicos ON carteiras TO cripto_servicos USING (true) WITH CHECK (true);
CREATE POLICY servicos ON enderecos TO cripto_servicos USING (true) WITH CHECK (true);
CREATE POLICY servicos ON saidas TO cripto_servicos USING (true) WITH CHECK (true);
CREATE POLICY servicos ON movimentos TO cripto_servicos USING (true) WITH CHECK (true);
CREATE POLICY servicos ON alertas TO cripto_servicos USING (true) WITH CHECK (true);
CREATE POLICY servicos ON agenda TO cripto_servicos USING (true) WITH CHECK (true);
CREATE POLICY servicos ON canais TO cripto_servicos USING (true) WITH CHECK (true);

GRANT SELECT ON organizacoes TO cripto_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON sessoes TO cripto_api;
GRANT SELECT ON usuarios TO cripto_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON carteiras, agenda, canais TO cripto_api;
GRANT SELECT, INSERT ON enderecos TO cripto_api;
GRANT SELECT ON saidas, movimentos, listas, listas_atualizacao, servicos TO cripto_api;
GRANT SELECT, UPDATE (tratado_em, tratado_por, nota) ON alertas TO cripto_api;
GRANT INSERT ON fila_tarefas TO cripto_api;
GRANT UPDATE (tentativas, disponivel_em) ON fila_tarefas TO cripto_api;
GRANT SELECT ON fila_tarefas TO cripto_api;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cripto_servicos;
GRANT EXECUTE ON FUNCTION cripto_organizacao_atual() TO cripto_api, cripto_servicos;
