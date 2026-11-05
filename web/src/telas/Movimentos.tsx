import { Drawer, Group, Select, SimpleGrid, Stack, Text } from "@mantine/core";
import { useState } from "react";

import { useDados, usePaginas } from "../api";
import { Busca, Cabecalho, Carregando, Codigo, Data, MaisLinhas, Numero, Painel, Tabela, Valor } from "../componentes";
import { TIPOS } from "../formato";
import { EstadoDaTransacao, GavetaDoAlerta } from "./Alertas";

export interface Movimento {
  id: number; carteira: string; carteira_id: number; rede: string; transacao: string; tipo: string; valor_sats: number; taxa_sats: number | null;
  contrapartes: { endereco: string; valor_sats?: number }[]; estado: string; bloco: number | null; historico: boolean; visto_em: string; alerta_id: number | null;
}

export const colunasDeMovimento = [
  { titulo: "Quando", celula: (m: Movimento) => <Data valor={m.visto_em} /> },
  { titulo: "Carteira", celula: (m: Movimento) => m.carteira },
  { titulo: "Tipo", celula: (m: Movimento) => <>{TIPOS[m.tipo]}{m.historico && <Text size="xs" c="dimmed">antes do cadastro</Text>}</> },
  { titulo: "Valor", alinhar: "right" as const, celula: (m: Movimento) => <Valor sats={m.valor_sats} sinal={m.tipo} /> },
  { titulo: "Outra ponta", celula: (m: Movimento) => (m.contrapartes[0] ? <Codigo valor={m.contrapartes[0].endereco} curto /> : <Text span size="sm" c="dimmed">-</Text>) },
  { titulo: "Transação", celula: (m: Movimento) => <EstadoDaTransacao estado={m.estado} /> },
];

export function GavetaDoMovimento({ movimento, aoFechar }: { movimento: Movimento | null; aoFechar: () => void }) {
  return (
    <Drawer opened={movimento !== null} onClose={aoFechar} title={movimento ? `${TIPOS[movimento.tipo]} em ${movimento.carteira}` : ""} size="xl">
      {movimento && (
        <Stack gap="md">
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <Numero rotulo="Valor" valor={<Valor sats={movimento.valor_sats} sinal={movimento.tipo} />} />
            <Numero rotulo="Taxa" valor={movimento.taxa_sats === null ? "-" : <Valor sats={movimento.taxa_sats} />} />
            <Numero rotulo="Transação" valor={<EstadoDaTransacao estado={movimento.estado} />} detalhe={movimento.bloco ? `bloco ${movimento.bloco.toLocaleString("pt-BR")}` : "ainda sem bloco"} />
          </SimpleGrid>
          <Painel titulo="Transação"><Codigo valor={movimento.transacao} /></Painel>
          <Painel titulo={movimento.tipo === "entrada" ? "De onde veio" : "Para onde foi"}>
            <Tabela linhas={movimento.contrapartes} chave={(c) => c.endereco} vazio="Nenhuma outra ponta identificada."
              colunas={[{ titulo: "Endereço", celula: (c) => <Codigo valor={c.endereco} /> }, ...(movimento.tipo === "saida" ? [{ titulo: "Valor", alinhar: "right" as const, celula: (c: { valor_sats?: number }) => <Valor sats={c.valor_sats} /> }] : [])]} />
          </Painel>
        </Stack>
      )}
    </Drawer>
  );
}

export interface FiltroDeMovimentos { rotulo: string; consulta: Record<string, string> }

/** Os números de movimento do panorama abrem aqui exatamente o que contam. */
export function GavetaDeMovimentos({ filtro, aoFechar }: { filtro: FiltroDeMovimentos | null; aoFechar: () => void }) {
  const [alerta, setAlerta] = useState<number | null>(null);
  const [movimento, setMovimento] = useState<Movimento | null>(null);
  return (
    <>
      <Drawer opened={filtro !== null} onClose={aoFechar} title={filtro?.rotulo ?? ""} size="60%">
        {filtro && <ListaDeMovimentos rota={`/api/movimentos?${new URLSearchParams(filtro.consulta)}`} aoAbrir={(m) => (m.alerta_id ? setAlerta(m.alerta_id) : setMovimento(m))} />}
      </Drawer>
      <GavetaDoAlerta id={alerta} aoFechar={() => setAlerta(null)} />
      <GavetaDoMovimento movimento={movimento} aoFechar={() => setMovimento(null)} />
    </>
  );
}

function ListaDeMovimentos({ rota, aoAbrir }: { rota: string; aoAbrir: (m: Movimento) => void }) {
  const { itens, haMais, erro, mais } = usePaginas<Movimento>(rota, "movimentos");
  if (!itens) return <Carregando erro={erro} />;
  return <><Tabela linhas={itens} chave={(m) => m.id} vazio="Nenhum movimento." aoClicarLinha={aoAbrir} colunas={colunasDeMovimento} /><MaisLinhas haMais={haMais} aoPedir={mais} /></>;
}

export function Movimentos() {
  const [tipo, setTipo] = useState<string | null>(null);
  const [estado, setEstado] = useState<string | null>(null);
  const [carteira, setCarteira] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [alerta, setAlerta] = useState<number | null>(null);
  const [movimento, setMovimento] = useState<Movimento | null>(null);
  const { dados: carteiras } = useDados<{ carteiras: { id: number; nome: string }[] }>("/api/carteiras");
  const consulta = new URLSearchParams({ ...(tipo ? { tipo } : {}), ...(estado ? { estado } : {}), ...(carteira ? { carteira } : {}), ...(busca ? { busca } : {}) });
  const { itens, haMais, erro, mais } = usePaginas<Movimento>(`/api/movimentos?${consulta}`, "movimentos");

  return (
    <>
      <Cabecalho titulo="Movimentos" ajuda="Tudo que entrou e saiu das carteiras acompanhadas, já com o troco descontado. A busca aceita a transação ou o endereço da outra ponta, inteiros." />
      <Group mb="md" gap="sm">
        <Busca valor={busca} aoMudar={setBusca} dica="Transação ou endereço" />
        <Select size="xs" w={130} placeholder="Tipo" clearable data={Object.entries(TIPOS).map(([value, label]) => ({ value, label }))} value={tipo} onChange={setTipo} aria-label="Tipo" />
        <Select size="xs" w={150} placeholder="Transação" clearable data={[{ value: "mempool", label: "Pendente" }, { value: "confirmada", label: "Confirmada" }]} value={estado} onChange={setEstado} aria-label="Situação da transação" />
        <Select size="xs" w={200} placeholder="Carteira" clearable searchable data={(carteiras?.carteiras ?? []).map((c) => ({ value: String(c.id), label: c.nome }))} value={carteira} onChange={setCarteira} aria-label="Carteira" />
      </Group>
      <Painel>
        {!itens ? <Carregando erro={erro} /> : (
          <>
            <Tabela linhas={itens} chave={(m) => m.id} vazio="Nenhum movimento." aoClicarLinha={(m) => (m.alerta_id ? setAlerta(m.alerta_id) : setMovimento(m))} colunas={colunasDeMovimento} />
            <MaisLinhas haMais={haMais} aoPedir={mais} />
          </>
        )}
      </Painel>
      <GavetaDoAlerta id={alerta} aoFechar={() => setAlerta(null)} />
      <GavetaDoMovimento movimento={movimento} aoFechar={() => setMovimento(null)} />
    </>
  );
}
