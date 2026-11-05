import { Alert, Button, Drawer, Group, Modal, NumberInput, SegmentedControl, Select, SimpleGrid, Stack, Tabs, Text, Textarea, TextInput } from "@mantine/core";
import { useState } from "react";

import { detalhe, enviar, useDados, usePaginas } from "../api";
import { AcoesDaLinha, Cabecalho, Carregando, Codigo, Data, Estado, MaisLinhas, Numero, Painel, Tabela, Valor } from "../componentes";
import { btc, btcCurto, numero, REDES } from "../formato";
import { colunasDeAlerta, GavetaDoAlerta, type AlertaDaLista } from "./Alertas";
import { colunasDeMovimento, GavetaDoMovimento, type Movimento } from "./Movimentos";

interface Carteira {
  id: number; nome: string; rede: string; limite_sats: number | null; estado: string; sincronizada_em: string | null; criada_em: string;
  tem_descritor: boolean; saldo_sats: number; enderecos: number; usados: number; alertas_abertos: number;
}
interface Detalhe {
  id: number; nome: string; rede: string; descritor: string | null; limite_sats: number | null; estado: string; sincronizada_em: string | null;
  enderecos: { endereco: string; ramo: number | null; indice: number | null; usado: boolean; saldo_sats: number }[];
}

const OPCOES_DE_REDE = Object.entries(REDES).map(([value, label]) => ({ value, label }));
const paraSats = (v: number | string) => (v === "" || v === null ? null : Math.round(Number(v) * 1e8));

function NovaCarteira({ aberta, aoFechar, aoCriar }: { aberta: boolean; aoFechar: () => void; aoCriar: () => void }) {
  const [nome, setNome] = useState("");
  const [rede, setRede] = useState<string | null>("bitcoin");
  const [forma, setForma] = useState("descritor");
  const [texto, setTexto] = useState("");
  const [limite, setLimite] = useState<number | string>("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const criar = async () => {
    setErro(null);
    setEnviando(true);
    const corpo = forma === "descritor"
      ? { nome, rede, descritor: texto, limite_sats: paraSats(limite) }
      : { nome, rede, enderecos: texto.split(/[\s,;]+/).filter(Boolean), limite_sats: paraSats(limite) };
    const r = await enviar("/api/carteiras", corpo).finally(() => setEnviando(false));
    if (!r.ok) { setErro(await detalhe(r)); return; }
    setNome(""); setTexto(""); setLimite("");
    aoCriar();
  };

  return (
    <Modal opened={aberta} onClose={aoFechar} title="Nova carteira" size="lg">
      <Stack gap="sm">
        <Group grow>
          <TextInput label="Nome" value={nome} onChange={(e) => setNome(e.currentTarget.value)} maxLength={80} data-autofocus />
          <Select label="Rede" data={OPCOES_DE_REDE} value={rede} onChange={setRede} allowDeselect={false} />
        </Group>
        <SegmentedControl size="xs" value={forma} onChange={setForma} data={[{ label: "Descritor", value: "descritor" }, { label: "Endereços avulsos", value: "enderecos" }]} />
        <Textarea
          label={forma === "descritor" ? "Descritor só leitura" : "Endereços, um por linha"}
          description={forma === "descritor" ? "Exporte do Sparrow, do Electrum ou da carteira de hardware. Só a parte pública: descritor com chave privada é recusado." : undefined}
          classNames={{ input: "mono" }} autosize minRows={3} maxRows={8} value={texto} onChange={(e) => setTexto(e.currentTarget.value)}
          placeholder={forma === "descritor" ? "wpkh([a1b2c3d4/84h/0h/0h]xpub6C.../<0;1>/*)" : "bc1q..."}
        />
        <NumberInput label="Limite por saída, em BTC" description="Saída acima disso sobe para alta, mesmo para endereço conferido." value={limite} onChange={setLimite} min={0} decimalScale={8} decimalSeparator="," thousandSeparator="." allowNegative={false} />
        {erro && <Alert color="red" variant="light" p="xs">{erro}</Alert>}
        <Group justify="flex-end">
          <Button variant="subtle" color="gray" onClick={aoFechar}>Cancelar</Button>
          <Button variant="filled" loading={enviando} disabled={!nome.trim() || !texto.trim()} onClick={criar}>Acompanhar</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function Limite({ carteira, aoFechar, aoMudar }: { carteira: Carteira | null; aoFechar: () => void; aoMudar: () => void }) {
  const [valor, setValor] = useState<number | string>("");
  const [erro, setErro] = useState<string | null>(null);
  const salvar = async () => {
    const r = await enviar(`/api/carteiras/${carteira!.id}`, { limite_sats: paraSats(valor) ?? 0 }, "PATCH");
    if (!r.ok) { setErro(await detalhe(r)); return; }
    aoMudar();
  };
  return (
    <Modal opened={carteira !== null} onClose={aoFechar} title={`Limite de ${carteira?.nome ?? ""}`}>
      <Stack gap="sm">
        <NumberInput label="Limite por saída, em BTC" description="Deixe vazio para não ter limite." value={valor} onChange={setValor} min={0} decimalScale={8} decimalSeparator="," thousandSeparator="." allowNegative={false} placeholder={carteira?.limite_sats ? btc(carteira.limite_sats) : "Sem limite"} data-autofocus />
        {erro && <Alert color="red" variant="light" p="xs">{erro}</Alert>}
        <Group justify="flex-end">
          <Button variant="subtle" color="gray" onClick={aoFechar}>Cancelar</Button>
          <Button variant="filled" onClick={salvar}>Salvar</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function GavetaDaCarteira({ id, aoFechar }: { id: number | null; aoFechar: () => void }) {
  const { dados, erro } = useDados<Detalhe>(id === null ? null : `/api/carteiras/${id}`);
  const [alerta, setAlerta] = useState<number | null>(null);
  const [movimento, setMovimento] = useState<Movimento | null>(null);
  const saldo = dados?.enderecos.reduce((t, e) => t + Number(e.saldo_sats), 0) ?? 0;
  return (
    <>
      <Drawer opened={id !== null} onClose={aoFechar} title={dados?.nome ?? "Carteira"} size="70%">
        {!dados || dados.id !== id ? <Carregando erro={erro} /> : (
          <Tabs defaultValue="resumo">
            <Tabs.List mb="md">
              <Tabs.Tab value="resumo">Resumo</Tabs.Tab>
              <Tabs.Tab value="enderecos">Endereços</Tabs.Tab>
              <Tabs.Tab value="movimentos">Movimentos</Tabs.Tab>
              <Tabs.Tab value="alertas">Alertas</Tabs.Tab>
            </Tabs.List>
            <Tabs.Panel value="resumo">
              <Stack gap="md">
                <SimpleGrid cols={{ base: 1, sm: 3 }}>
                  <Numero rotulo="Saldo" valor={`${btcCurto(saldo)} BTC`} />
                  <Numero rotulo="Limite por saída" valor={dados.limite_sats ? `${btcCurto(dados.limite_sats)} BTC` : "Sem limite"} />
                  <Numero rotulo="Rede" valor={REDES[dados.rede] ?? dados.rede} detalhe={dados.estado === "historico" ? "lendo o ponto de partida" : `acompanhando desde ${dados.sincronizada_em ? new Date(dados.sincronizada_em).toLocaleDateString("pt-BR") : "-"}`} />
                </SimpleGrid>
                {dados.descritor && <Painel titulo="Descritor"><Codigo valor={dados.descritor} /></Painel>}
              </Stack>
            </Tabs.Panel>
            <Tabs.Panel value="enderecos">
              <Tabela
                linhas={dados.enderecos}
                chave={(e) => e.endereco}
                vazio="Nenhum endereço."
                colunas={[
                  { titulo: "Endereço", celula: (e) => <Codigo valor={e.endereco} /> },
                  { titulo: "Caminho", celula: (e) => (e.ramo === null ? "avulso" : `${e.ramo === 0 ? "receber" : e.ramo === 1 ? "troco" : `ramo ${e.ramo}`} / ${e.indice}`) },
                  { titulo: "Uso", celula: (e) => (e.usado ? "Usado" : <Text span size="sm" c="dimmed">Sem uso</Text>) },
                  { titulo: "Saldo", alinhar: "right", celula: (e) => <Valor sats={e.saldo_sats} /> },
                ]}
              />
            </Tabs.Panel>
            <Tabs.Panel value="movimentos"><ListaDaCarteira<Movimento> rota={`/api/movimentos?carteira=${id}`} chave="movimentos" colunas={colunasDeMovimento} aoAbrir={(m) => (m.alerta_id ? setAlerta(m.alerta_id) : setMovimento(m))} /></Tabs.Panel>
            <Tabs.Panel value="alertas"><ListaDaCarteira<AlertaDaLista> rota={`/api/alertas?estado=todos&carteira=${id}`} chave="alertas" colunas={colunasDeAlerta} aoAbrir={(a) => setAlerta(a.id)} /></Tabs.Panel>
          </Tabs>
        )}
      </Drawer>
      <GavetaDoAlerta id={alerta} aoFechar={() => setAlerta(null)} />
      <GavetaDoMovimento movimento={movimento} aoFechar={() => setMovimento(null)} />
    </>
  );
}

function ListaDaCarteira<T extends { id: number }>({ rota, chave, colunas, aoAbrir }: { rota: string; chave: string; colunas: { titulo: string; celula: (l: T) => React.ReactNode; alinhar?: "right" }[]; aoAbrir: (l: T) => void }) {
  const { itens, haMais, erro, mais } = usePaginas<T>(rota, chave);
  if (!itens) return <Carregando erro={erro} />;
  return <><Tabela linhas={itens} chave={(l) => l.id} vazio="Nada ainda." aoClicarLinha={aoAbrir} colunas={colunas} /><MaisLinhas haMais={haMais} aoPedir={mais} /></>;
}

export function Carteiras() {
  const { dados, erro, recarregar } = useDados<{ carteiras: Carteira[] }>("/api/carteiras");
  const [nova, setNova] = useState(false);
  const [aberta, setAberta] = useState<number | null>(null);
  const [limite, setLimite] = useState<Carteira | null>(null);
  const [remover, setRemover] = useState<Carteira | null>(null);

  const confirmarRemocao = async () => {
    await enviar(`/api/carteiras/${remover!.id}`, undefined, "DELETE");
    setRemover(null);
    recarregar();
  };

  return (
    <>
      <Cabecalho titulo="Carteiras" ajuda="Carteiras acompanhadas só com a parte pública. Nada aqui assina ou move valor.">
        <Button variant="filled" onClick={() => setNova(true)}>Nova carteira</Button>
      </Cabecalho>
      <Painel>
        {!dados ? <Carregando erro={erro} /> : (
          <Tabela
            linhas={dados.carteiras}
            chave={(c) => c.id}
            vazio="Nenhuma carteira ainda."
            aoClicarLinha={(c) => setAberta(c.id)}
            colunas={[
              { titulo: "Nome", celula: (c) => c.nome },
              { titulo: "Rede", celula: (c) => REDES[c.rede] ?? c.rede },
              { titulo: "Saldo", alinhar: "right", celula: (c) => <Valor sats={c.saldo_sats} /> },
              { titulo: "Endereços usados", alinhar: "right", celula: (c) => `${numero(c.usados)} de ${numero(c.enderecos)}` },
              { titulo: "Alertas abertos", alinhar: "right", celula: (c) => numero(c.alertas_abertos) },
              { titulo: "Situação", celula: (c) => (c.estado === "acompanhando" ? <Estado tipo="acompanhando">Acompanhando</Estado> : <Estado tipo="historico">Lendo o ponto de partida</Estado>) },
              { titulo: "Cadastrada", celula: (c) => <Data valor={c.criada_em} /> },
              { titulo: "", largura: 40, celula: (c) => <AcoesDaLinha rotulo="Ações da carteira" itens={[
                { texto: "Abrir", aoClicar: () => setAberta(c.id) },
                { texto: "Mudar o limite", aoClicar: () => setLimite(c) },
                { texto: "Parar de acompanhar", perigo: true, aoClicar: () => setRemover(c) },
              ]} /> },
            ]}
          />
        )}
      </Painel>
      <NovaCarteira aberta={nova} aoFechar={() => setNova(false)} aoCriar={() => { setNova(false); recarregar(); }} />
      <Limite carteira={limite} aoFechar={() => setLimite(null)} aoMudar={() => { setLimite(null); recarregar(); }} />
      <GavetaDaCarteira id={aberta} aoFechar={() => setAberta(null)} />
      <Modal opened={remover !== null} onClose={() => setRemover(null)} title="Parar de acompanhar">
        <Stack gap="sm">
          <Text size="sm">Os movimentos e alertas de <b>{remover?.nome}</b> saem do Panthera. A carteira em si não muda.</Text>
          <Group justify="flex-end">
            <Button variant="subtle" color="gray" onClick={() => setRemover(null)}>Cancelar</Button>
            <Button color="red" onClick={confirmarRemocao}>Parar de acompanhar</Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
