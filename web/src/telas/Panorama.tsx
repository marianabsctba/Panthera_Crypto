import { Grid, Group, SegmentedControl, SimpleGrid, Stack, Text } from "@mantine/core";
import { useState } from "react";

import { useDados } from "../api";
import { AmostraDeMetal, BarrasMetalicas, Cabecalho, Carregando, Estado, METAIS_DE_SEVERIDADE, Numero, ORDEM_DE_SEVERIDADE, Painel, Ranking, Tabela } from "../componentes";
import { btcCurto, compacto, diaCurto, ha, SERVICOS } from "../formato";
import { SEVERIDADES } from "../tema";
import { GavetaDeAlertas, type FiltroDeAlertas } from "./Alertas";
import { GavetaDeMovimentos, type FiltroDeMovimentos } from "./Movimentos";

interface Dia { dia: string; baixa: number; media: number; alta: number; critica: number }
interface Servico { servico: string; vivas: number; visto_em: string }
interface PanoramaDados {
  carteiras: number;
  saldo_sats: number;
  abertos: Record<string, number>;
  saidas: { total: number; valor: number };
  pendentes: number;
  alertas_por_dia: Dia[];
  por_carteira: { id: number; nome: string; total: number }[];
  servicos: Servico[];
}

export function Panorama() {
  const [dias, setDias] = useState("30");
  const [filtro, setFiltro] = useState<FiltroDeAlertas | null>(null);
  const [movimentos, setMovimentos] = useState<FiltroDeMovimentos | null>(null);
  const { dados, erro } = useDados<PanoramaDados>(`/api/panorama?dias=${dias}`);

  if (!dados) return <><Cabecalho titulo="Panorama" ajuda="" /><Carregando erro={erro} /></>;

  const abertos = ORDEM_DE_SEVERIDADE.reduce((t, s) => t + dados.abertos[s], 0);
  const graves = dados.abertos.critica + dados.abertos.alta;
  // O gráfico só traz dias com alerta: completa com zero, para o silêncio aparecer.
  const presentes = new Map(dados.alertas_por_dia.map((d) => [d.dia, d]));
  const serie = Array.from({ length: Number(dias) }, (_, i) => {
    const dia = new Date(Date.now() - (Number(dias) - 1 - i) * 86400000).toLocaleDateString("sv-SE");
    return { ...(presentes.get(dia) ?? { dia, critica: 0, alta: 0, media: 0, baixa: 0 }), rotulo: diaCurto(dia) };
  });
  const abrir = (rotulo: string, consulta: Record<string, string>) => setFiltro({ rotulo, consulta });

  return (
    <>
      <Cabecalho titulo="Panorama" ajuda="O que está acontecendo com as carteiras acompanhadas: saldo, alertas que esperam alguém e a saúde da leitura da rede.">
        <SegmentedControl size="xs" value={dias} onChange={setDias} data={[{ label: "7 dias", value: "7" }, { label: "30 dias", value: "30" }, { label: "90 dias", value: "90" }]} aria-label="Período" />
      </Cabecalho>

      <Stack gap="md">
        <SimpleGrid cols={{ base: 2, md: 3, lg: 5 }} spacing="md">
          <Numero rotulo="Saldo acompanhado" valor={`${btcCurto(dados.saldo_sats)} BTC`} detalhe={`${dados.carteiras} ${dados.carteiras === 1 ? "carteira" : "carteiras"}`} aoClicar={() => { window.history.pushState(null, "", "/carteiras"); window.dispatchEvent(new PopStateEvent("popstate")); }} />
          <Numero rotulo="Alertas abertos" valor={compacto(abertos)} aoClicar={() => abrir("Alertas abertos", { estado: "abertos" })} />
          <Numero rotulo="Críticos abertos" valor={compacto(dados.abertos.critica)} destaque={dados.abertos.critica ? SEVERIDADES.critica.cor : undefined} detalhe={`${compacto(graves)} altos e críticos`} aoClicar={() => abrir("Alertas críticos abertos", { estado: "abertos", severidade: "critica" })} />
          <Numero rotulo="Saídas no período" valor={compacto(dados.saidas.total)} detalhe={`${btcCurto(dados.saidas.valor)} BTC`} aoClicar={() => setMovimentos({ rotulo: `Saídas dos últimos ${dias} dias`, consulta: { tipo: "saida", dias, novos: "true" } })} />
          <Numero rotulo="Pendentes na rede" valor={compacto(dados.pendentes)} detalhe="ainda sem bloco" aoClicar={() => setMovimentos({ rotulo: "Pendentes na rede", consulta: { estado: "mempool" } })} />
        </SimpleGrid>

        <Painel
          titulo="Alertas por dia"
          acao={<Group gap="md">{ORDEM_DE_SEVERIDADE.map((s) => <AmostraDeMetal key={s} cores={METAIS_DE_SEVERIDADE[s]} rotulo={SEVERIDADES[s].texto} />)}</Group>}
        >
          <BarrasMetalicas
            altura={200}
            dados={serie}
            chave="rotulo"
            empilhado
            series={ORDEM_DE_SEVERIDADE.map((s) => ({ nome: s, rotulo: SEVERIDADES[s].texto, metal: METAIS_DE_SEVERIDADE[s] }))}
            aoClicar={(r) => { const d = serie.find((x) => x.rotulo === r); if (d) abrir(`Alertas de ${r}`, { estado: "todos", dia: d.dia }); }}
          />
        </Painel>

        <Grid gap="md">
          <Grid.Col span={{ base: 12, lg: 6 }}>
            <Painel titulo="Carteiras com alertas abertos">
              <Ranking itens={dados.por_carteira.map((c) => ({ rotulo: c.nome, valor: c.total, chave: String(c.id) }))} vazio="Nenhum alerta aberto." aoClicar={(id, nome) => abrir(`Alertas abertos de ${nome}`, { estado: "abertos", carteira: id })} />
            </Painel>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 6 }}>
            <Painel titulo="Leitura da rede">
              <Tabela
                linhas={dados.servicos}
                chave={(s) => s.servico}
                vazio="Nenhum serviço deu sinal de vida ainda."
                colunas={[
                  { titulo: "Serviço", celula: (s) => SERVICOS[s.servico] ?? s.servico },
                  { titulo: "Situação", celula: (s) => (s.vivas ? <Estado tipo="ativo">{s.vivas === 1 ? "Rodando" : `${s.vivas} cópias`}</Estado> : <Estado tipo="parado">Parado</Estado>) },
                  { titulo: "Último sinal", celula: (s) => <Text span size="sm" c="dimmed">{ha(s.visto_em)}</Text> },
                ]}
              />
            </Painel>
          </Grid.Col>
        </Grid>
      </Stack>

      <GavetaDeAlertas filtro={filtro} aoFechar={() => setFiltro(null)} />
      <GavetaDeMovimentos filtro={movimentos} aoFechar={() => setMovimentos(null)} />
    </>
  );
}
