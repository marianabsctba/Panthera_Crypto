import { Alert, Button, Group, Modal, SegmentedControl, Select, Stack, Text, TextInput } from "@mantine/core";
import { useState } from "react";

import { detalhe, enviar, useDados } from "../api";
import { AcoesDaLinha, Cabecalho, Carregando, Estado, Painel, Severidade, Tabela } from "../componentes";
import { ha } from "../formato";
import { SEVERIDADES_PARA_ESCOLHA } from "./Alertas";

interface Canal { id: number; nome: string; tipo: string; url: string; severidade_minima: string; ativo: boolean; ultimo_envio_em: string | null; ultimo_erro: string | null }

export function Canais() {
  const { dados, erro, recarregar } = useDados<{ canais: Canal[] }>("/api/canais");
  const [novo, setNovo] = useState(false);
  const [nome, setNome] = useState("");
  const [tipo, setTipo] = useState("ntfy");
  const [url, setUrl] = useState("");
  const [minima, setMinima] = useState<string | null>("alta");
  const [falha, setFalha] = useState<string | null>(null);
  const [aviso, setAviso] = useState<{ cor: string; texto: string } | null>(null);

  const criar = async () => {
    setFalha(null);
    const r = await enviar("/api/canais", { nome, tipo, url, severidade_minima: minima });
    if (!r.ok) { setFalha(await detalhe(r)); return; }
    setNome(""); setUrl(""); setNovo(false);
    recarregar();
  };

  const testar = async (c: Canal) => {
    const r = await enviar(`/api/canais/${c.id}/testar`);
    setAviso(r.ok ? { cor: "green", texto: `Teste enviado para ${c.nome}.` } : { cor: "red", texto: await detalhe(r) });
    recarregar();
  };

  return (
    <>
      <Cabecalho titulo="Avisos" ajuda="Para onde vão os alertas, a partir de qual gravidade. Canal fora do ar recebe de novo mais tarde; o alerta fica registrado de qualquer jeito.">
        <Button variant="filled" onClick={() => setNovo(true)}>Novo canal</Button>
      </Cabecalho>
      {aviso && <Alert color={aviso.cor} variant="light" p="xs" mb="md" withCloseButton onClose={() => setAviso(null)}>{aviso.texto}</Alert>}
      <Painel>
        {!dados ? <Carregando erro={erro} /> : (
          <Tabela
            linhas={dados.canais}
            chave={(c) => c.id}
            vazio="Nenhum canal. Os alertas ficam só na tela."
            colunas={[
              { titulo: "Nome", celula: (c) => c.nome },
              { titulo: "Tipo", celula: (c) => (c.tipo === "ntfy" ? "Celular (ntfy)" : "Webhook") },
              { titulo: "Endereço", celula: (c) => <Text span className="mono" lineClamp={1}>{c.url}</Text> },
              { titulo: "A partir de", celula: (c) => <Severidade valor={c.severidade_minima} /> },
              { titulo: "Último envio", celula: (c) => <Text span size="sm" c="dimmed">{ha(c.ultimo_envio_em)}</Text> },
              { titulo: "Situação", celula: (c) => (!c.ativo ? <Estado tipo="desligado">Desligado</Estado> : c.ultimo_erro ? <Estado tipo="problema">Falhando</Estado> : <Estado tipo="ativo">Ligado</Estado>) },
              { titulo: "", largura: 40, celula: (c) => <AcoesDaLinha rotulo="Ações do canal" itens={[
                { texto: "Mandar um teste", aoClicar: () => testar(c) },
                { texto: c.ativo ? "Desligar" : "Ligar", aoClicar: async () => { await enviar(`/api/canais/${c.id}`, { ativo: !c.ativo }, "PATCH"); recarregar(); } },
                { texto: "Remover", perigo: true, aoClicar: async () => { await enviar(`/api/canais/${c.id}`, undefined, "DELETE"); recarregar(); } },
              ]} /> },
            ]}
          />
        )}
      </Painel>
      <Modal opened={novo} onClose={() => setNovo(false)} title="Novo canal">
        <Stack gap="sm">
          <TextInput label="Nome" value={nome} onChange={(e) => setNome(e.currentTarget.value)} maxLength={80} data-autofocus />
          <SegmentedControl size="xs" value={tipo} onChange={setTipo} data={[{ label: "Celular (ntfy)", value: "ntfy" }, { label: "Webhook", value: "webhook" }]} />
          <TextInput label="Endereço" classNames={{ input: "mono" }} placeholder={tipo === "ntfy" ? "https://ntfy.sua-empresa/alertas-cripto" : "https://sistema/api/webhook"} value={url} onChange={(e) => setUrl(e.currentTarget.value.trim())} maxLength={500} />
          <Select label="Avisar a partir de" data={SEVERIDADES_PARA_ESCOLHA} value={minima} onChange={setMinima} allowDeselect={false} />
          {falha && <Alert color="red" variant="light" p="xs">{falha}</Alert>}
          <Group justify="flex-end">
            <Button variant="subtle" color="gray" onClick={() => setNovo(false)}>Cancelar</Button>
            <Button variant="filled" disabled={!nome.trim() || !url} onClick={criar}>Criar</Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
