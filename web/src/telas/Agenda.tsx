import { Alert, Button, Group, Modal, Stack, Text, TextInput } from "@mantine/core";
import { useState } from "react";

import { detalhe, enviar, useDados } from "../api";
import { AcoesDaLinha, Cabecalho, Carregando, Codigo, Data, Painel, Tabela } from "../componentes";
import { SEVERIDADES } from "../tema";

interface Conferido { id: number; endereco: string; rotulo: string; criado_em: string; lista: string | null }

export function Agenda() {
  const { dados, erro, recarregar } = useDados<{ enderecos: Conferido[] }>("/api/agenda");
  const [novo, setNovo] = useState(false);
  const [endereco, setEndereco] = useState("");
  const [rotulo, setRotulo] = useState("");
  const [falha, setFalha] = useState<string | null>(null);

  const conferir = async () => {
    setFalha(null);
    const r = await enviar("/api/agenda", { endereco, rotulo });
    if (!r.ok) { setFalha(await detalhe(r)); return; }
    setEndereco(""); setRotulo(""); setNovo(false);
    recarregar();
  };

  return (
    <>
      <Cabecalho titulo="Endereços conferidos" ajuda="Destinos que alguém da organização conferiu fora do computador, por um segundo canal. Saída para qualquer outro endereço vira alerta alto.">
        <Button variant="filled" onClick={() => setNovo(true)}>Conferir endereço</Button>
      </Cabecalho>
      <Painel>
        {!dados ? <Carregando erro={erro} /> : (
          <Tabela
            linhas={dados.enderecos}
            chave={(e) => e.id}
            vazio="Nenhum endereço conferido. Sem eles, toda saída vira alerta alto."
            colunas={[
              { titulo: "Conferido como", celula: (e) => e.rotulo },
              { titulo: "Endereço", celula: (e) => <Codigo valor={e.endereco} /> },
              { titulo: "Lista", celula: (e) => (e.lista ? <Text span size="sm" fw={600} style={{ color: SEVERIDADES.critica.cor }}>{e.lista}</Text> : "-") },
              { titulo: "Desde", celula: (e) => <Data valor={e.criado_em} /> },
              { titulo: "", largura: 40, celula: (e) => <AcoesDaLinha rotulo="Ações do endereço" itens={[
                { texto: "Remover", perigo: true, aoClicar: async () => { await enviar(`/api/agenda/${e.id}`, undefined, "DELETE"); recarregar(); } },
              ]} /> },
            ]}
          />
        )}
      </Painel>
      <Modal opened={novo} onClose={() => setNovo(false)} title="Conferir endereço">
        <Stack gap="sm">
          <TextInput label="Conferido como" placeholder="Exchange, conta da empresa" value={rotulo} onChange={(e) => setRotulo(e.currentTarget.value)} maxLength={120} data-autofocus />
          <TextInput label="Endereço" classNames={{ input: "mono" }} value={endereco} onChange={(e) => setEndereco(e.currentTarget.value.trim())} maxLength={120} />
          <Text size="xs" c="dimmed">Confira o endereço inteiro com quem vai receber, por telefone ou pessoalmente. Não copie do histórico de transações.</Text>
          {falha && <Alert color="red" variant="light" p="xs">{falha}</Alert>}
          <Group justify="flex-end">
            <Button variant="subtle" color="gray" onClick={() => setNovo(false)}>Cancelar</Button>
            <Button variant="filled" disabled={!endereco || !rotulo.trim()} onClick={conferir}>Conferir</Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
