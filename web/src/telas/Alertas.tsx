import { Alert, Button, Drawer, Group, SegmentedControl, Select, SimpleGrid, Stack, Text, Textarea } from "@mantine/core";
import { useState } from "react";

import { detalhe, enviar, useDados, usePaginas } from "../api";
import { Busca, Cabecalho, Carregando, Codigo, Data, Estado, MaisLinhas, Numero, Painel, Severidade, Tabela, Valor } from "../componentes";
import { REDES, TIPOS } from "../formato";
import { SEVERIDADES } from "../tema";

export interface AlertaDaLista {
  id: number; severidade: string; titulo: string; motivos: string[]; criado_em: string; tratado_em: string | null;
  carteira: string; rede: string; tipo: string | null; valor_sats: number | null; estado: string | null; transacao: string | null;
}
interface Contraparte { endereco: string; valor_sats?: number; rotulo: string | null; lista: string | null }
interface AlertaCompleto extends AlertaDaLista {
  taxa_sats: number | null; contrapartes: Contraparte[] | null; visto_em: string | null; confirmada_em: string | null; bloco: number | null;
  tratado_por: string | null; nota: string | null;
}

export const SEVERIDADES_PARA_ESCOLHA = Object.entries(SEVERIDADES).map(([value, s]) => ({ value, label: s.texto }));

export function EstadoDaTransacao({ estado }: { estado: string | null }) {
  if (!estado) return <Text span size="sm" c="dimmed">-</Text>;
  return <Estado tipo={estado}>{estado === "mempool" ? "Pendente" : "Confirmada"}</Estado>;
}

export const colunasDeAlerta = [
  { titulo: "Quando", celula: (a: AlertaDaLista) => <Data valor={a.criado_em} /> },
  { titulo: "Severidade", celula: (a: AlertaDaLista) => <Severidade valor={a.severidade} /> },
  { titulo: "Alerta", celula: (a: AlertaDaLista) => <><Text size="sm">{a.titulo}</Text><Text size="xs" c="dimmed" lineClamp={1}>{a.motivos[0]}</Text></> },
  { titulo: "Carteira", celula: (a: AlertaDaLista) => a.carteira },
  { titulo: "Valor", alinhar: "right" as const, celula: (a: AlertaDaLista) => (a.valor_sats === null ? "-" : <Valor sats={a.valor_sats} sinal={a.tipo ?? undefined} />) },
  { titulo: "Transação", celula: (a: AlertaDaLista) => <EstadoDaTransacao estado={a.estado} /> },
];

export function GavetaDoAlerta({ id, aoFechar, aoMudar }: { id: number | null; aoFechar: () => void; aoMudar?: () => void }) {
  const { dados, erro, recarregar } = useDados<AlertaCompleto>(id === null ? null : `/api/alertas/${id}`);
  const [nota, setNota] = useState("");
  const [falha, setFalha] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const tratar = async () => {
    setEnviando(true);
    const r = await enviar(`/api/alertas/${id}/tratar`, { nota }).finally(() => setEnviando(false));
    if (!r.ok) { setFalha(await detalhe(r)); return; }
    setNota("");
    recarregar();
    aoMudar?.();
  };

  return (
    <Drawer opened={id !== null} onClose={() => { setFalha(null); aoFechar(); }} title={dados?.titulo ?? "Alerta"} size="xl">
      {!dados || dados.id !== id ? <Carregando erro={erro} /> : (
        <Stack gap="md">
          <Group gap="lg">
            <Severidade valor={dados.severidade} />
            <Data valor={dados.criado_em} />
            <Text size="sm" c="dimmed">{dados.carteira} · {REDES[dados.rede] ?? dados.rede}</Text>
          </Group>
          <Painel titulo="Por que">
            <Stack gap={4}>{dados.motivos.map((m) => <Text key={m} size="sm" style={{ overflowWrap: "anywhere" }}>{m}</Text>)}</Stack>
          </Painel>
          {dados.transacao && (
            <>
              <SimpleGrid cols={{ base: 1, sm: 3 }}>
                <Numero rotulo={TIPOS[dados.tipo ?? ""] ?? "Valor"} valor={<Valor sats={dados.valor_sats} sinal={dados.tipo ?? undefined} />} />
                <Numero rotulo="Taxa" valor={dados.taxa_sats === null ? "-" : <Valor sats={dados.taxa_sats} />} />
                <Numero rotulo="Transação" valor={<EstadoDaTransacao estado={dados.estado} />} detalhe={dados.bloco ? `bloco ${dados.bloco.toLocaleString("pt-BR")}` : "ainda sem bloco"} />
              </SimpleGrid>
              <Painel titulo="Transação"><Codigo valor={dados.transacao} /></Painel>
              <Painel titulo={dados.tipo === "entrada" ? "De onde veio" : "Para onde foi"}>
                <Tabela
                  linhas={dados.contrapartes ?? []}
                  chave={(c) => c.endereco}
                  vazio="A origem não pôde ser identificada."
                  colunas={[
                    { titulo: "Endereço", celula: (c) => <Codigo valor={c.endereco} /> },
                    { titulo: "Conferido como", celula: (c) => c.rotulo ?? <Text span size="sm" c="dimmed">Não conferido</Text> },
                    { titulo: "Lista", celula: (c) => (c.lista ? <Text span size="sm" fw={600} style={{ color: SEVERIDADES.critica.cor }}>{c.lista}</Text> : "-") },
                    ...(dados.tipo === "saida" ? [{ titulo: "Valor", alinhar: "right" as const, celula: (c: Contraparte) => <Valor sats={c.valor_sats} /> }] : []),
                  ]}
                />
              </Painel>
            </>
          )}
          {dados.tratado_em ? (
            <Alert color="gray" variant="light" title={`Tratado por ${dados.tratado_por ?? "-"}`}>
              <Stack gap={4}><Data valor={dados.tratado_em} />{dados.nota && <Text size="sm">{dados.nota}</Text>}</Stack>
            </Alert>
          ) : (
            <Painel titulo="Tratar">
              <Stack gap="sm">
                <Textarea placeholder="O que foi conferido (opcional)" value={nota} onChange={(e) => setNota(e.currentTarget.value)} autosize minRows={2} maxLength={2000} />
                {falha && <Alert color="red" variant="light" p="xs">{falha}</Alert>}
                <Group justify="flex-end"><Button variant="filled" loading={enviando} onClick={tratar}>Marcar como tratado</Button></Group>
              </Stack>
            </Painel>
          )}
        </Stack>
      )}
    </Drawer>
  );
}

export interface FiltroDeAlertas { rotulo: string; consulta: Record<string, string> }

/** Todo número que conta alertas abre aqui exatamente os alertas que ele conta. */
export function GavetaDeAlertas({ filtro, aoFechar }: { filtro: FiltroDeAlertas | null; aoFechar: () => void }) {
  const [aberto, setAberto] = useState<number | null>(null);
  const consulta = new URLSearchParams(filtro?.consulta ?? {}).toString();
  return (
    <>
      <Drawer opened={filtro !== null} onClose={aoFechar} title={filtro?.rotulo ?? ""} size="60%">
        {filtro && <ListaDeAlertas rota={`/api/alertas?${consulta}`} aoAbrir={setAberto} />}
      </Drawer>
      <GavetaDoAlerta id={aberto} aoFechar={() => setAberto(null)} />
    </>
  );
}

function ListaDeAlertas({ rota, aoAbrir }: { rota: string; aoAbrir: (id: number) => void }) {
  const { itens, haMais, erro, mais } = usePaginas<AlertaDaLista>(rota, "alertas");
  if (!itens) return <Carregando erro={erro} />;
  return (
    <>
      <Tabela linhas={itens} chave={(a) => a.id} vazio="Nenhum alerta." aoClicarLinha={(a) => aoAbrir(a.id)} colunas={colunasDeAlerta} />
      <MaisLinhas haMais={haMais} aoPedir={mais} />
    </>
  );
}

export function Alertas() {
  const [estado, setEstado] = useState("abertos");
  const [severidade, setSeveridade] = useState<string | null>(null);
  const [carteira, setCarteira] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [aberto, setAberto] = useState<number | null>(null);
  const { dados: carteiras } = useDados<{ carteiras: { id: number; nome: string }[] }>("/api/carteiras");
  const consulta = new URLSearchParams({ estado, ...(severidade ? { severidade } : {}), ...(carteira ? { carteira } : {}), ...(busca ? { busca } : {}) });
  const { itens, haMais, erro, mais, recarregar } = usePaginas<AlertaDaLista>(`/api/alertas?${consulta}`, "alertas");

  return (
    <>
      <Cabecalho titulo="Alertas" ajuda="Cada movimento que merece atenção. Saída para endereço não conferido e endereço em lista vêm primeiro na gravidade." />
      <Group mb="md" gap="sm">
        <Busca valor={busca} aoMudar={setBusca} dica="Transação, endereço ou título" />
        <SegmentedControl size="xs" value={estado} onChange={setEstado} data={[{ label: "Abertos", value: "abertos" }, { label: "Tratados", value: "tratados" }, { label: "Todos", value: "todos" }]} aria-label="Situação" />
        <Select size="xs" w={150} placeholder="Severidade" clearable data={SEVERIDADES_PARA_ESCOLHA} value={severidade} onChange={setSeveridade} aria-label="Severidade" />
        <Select size="xs" w={200} placeholder="Carteira" clearable searchable data={(carteiras?.carteiras ?? []).map((c) => ({ value: String(c.id), label: c.nome }))} value={carteira} onChange={setCarteira} aria-label="Carteira" />
      </Group>
      <Painel>
        {!itens ? <Carregando erro={erro} /> : (
          <>
            <Tabela linhas={itens} chave={(a) => a.id} vazio={estado === "abertos" ? "Nenhum alerta aberto." : "Nenhum alerta."} aoClicarLinha={(a) => setAberto(a.id)} colunas={colunasDeAlerta} />
            <MaisLinhas haMais={haMais} aoPedir={mais} />
          </>
        )}
      </Painel>
      <GavetaDoAlerta id={aberto} aoFechar={() => setAberto(null)} aoMudar={recarregar} />
    </>
  );
}
