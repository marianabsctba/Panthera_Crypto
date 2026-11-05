import { Alert, Anchor, Button, Group, SimpleGrid, Stack, Text, TextInput } from "@mantine/core";
import { useState } from "react";

import { ler, useDados } from "../api";
import { Cabecalho, Carregando, Numero, Painel } from "../componentes";
import { ha, numero } from "../formato";

interface Lista { lista: string; fonte: string; total: number; atualizada_em: string | null }

export function Listas() {
  const { dados, erro } = useDados<{ listas: Lista[] }>("/api/listas");
  const [endereco, setEndereco] = useState("");
  const [resultado, setResultado] = useState<{ endereco: string; listas: string | null } | null>(null);

  const consultar = async () => setResultado(await ler(`/api/listas/consultar?endereco=${encodeURIComponent(endereco)}`));

  return (
    <>
      <Cabecalho titulo="Listas" ajuda="Endereços que não se deve tocar. Todo movimento é conferido contra elas, nos dois sentidos, e a lista é atualizada uma vez por dia." />
      <Stack gap="md">
        {!dados ? <Carregando erro={erro} /> : (
          <SimpleGrid cols={{ base: 1, md: 3 }}>
            {dados.listas.map((l) => (
              <Numero key={l.lista} rotulo={l.lista === "OFAC" ? "Sanções dos EUA (OFAC)" : l.lista} valor={numero(l.total)} detalhe={`endereços Bitcoin, atualizada ${ha(l.atualizada_em)}`} />
            ))}
          </SimpleGrid>
        )}
        <Painel titulo="Consultar um endereço">
          <Stack gap="sm">
            <Group gap="sm" align="flex-end">
              <TextInput w={480} classNames={{ input: "mono" }} placeholder="Endereço" value={endereco} onChange={(e) => { setEndereco(e.currentTarget.value.trim()); setResultado(null); }}
                onKeyDown={(e) => { if (e.key === "Enter" && endereco) consultar(); }} aria-label="Endereço para consultar" />
              <Button disabled={!endereco} onClick={consultar}>Consultar</Button>
            </Group>
            {resultado && (resultado.listas
              ? <Alert color="red" variant="light" p="xs">Está na lista {resultado.listas}. Não mande nem aceite valor deste endereço.</Alert>
              : <Text size="sm" c="dimmed">Não está em nenhuma lista. Isso não quer dizer que seja seguro.</Text>)}
          </Stack>
        </Painel>
        {dados && (
          <Text size="xs" c="dimmed">
            Fonte: {dados.listas.map((l) => <Anchor key={l.lista} href={l.fonte} target="_blank" rel="noreferrer" size="xs">{l.lista}</Anchor>)}
          </Text>
        )}
      </Stack>
    </>
  );
}
