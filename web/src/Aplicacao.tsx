import { Alert, AppShell, Avatar, Box, Burger, Center, Group, Loader, Menu, ScrollArea, Text, UnstyledButton } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconAddressBook, IconAlertTriangle, IconArrowsExchange, IconBell, IconChartHistogram, IconChevronDown, IconListCheck, IconLogout, IconWallet } from "@tabler/icons-react";
import { Component, useEffect, useState, type ComponentType, type ReactNode } from "react";

import { ContextoEu, enviar, ler, type Eu } from "./api";
import { Entrada } from "./Entrada";
import { Agenda } from "./telas/Agenda";
import { Alertas } from "./telas/Alertas";
import { Canais } from "./telas/Canais";
import { Carteiras } from "./telas/Carteiras";
import { Listas } from "./telas/Listas";
import { Movimentos } from "./telas/Movimentos";
import { Panorama } from "./telas/Panorama";

interface Item { id: string; rotulo: string; icone: ComponentType<{ size?: number; stroke?: number }>; tela: ComponentType }

const GRUPOS: { titulo: string; itens: Item[] }[] = [
  { titulo: "Monitorar", itens: [
    { id: "panorama", rotulo: "Panorama", icone: IconChartHistogram, tela: Panorama },
    { id: "alertas", rotulo: "Alertas", icone: IconAlertTriangle, tela: Alertas },
    { id: "movimentos", rotulo: "Movimentos", icone: IconArrowsExchange, tela: Movimentos },
  ] },
  { titulo: "Proteger", itens: [
    { id: "carteiras", rotulo: "Carteiras", icone: IconWallet, tela: Carteiras },
    { id: "conferidos", rotulo: "Endereços conferidos", icone: IconAddressBook, tela: Agenda },
    { id: "listas", rotulo: "Listas", icone: IconListCheck, tela: Listas },
  ] },
  { titulo: "Administrar", itens: [
    { id: "avisos", rotulo: "Avisos", icone: IconBell, tela: Canais },
  ] },
];

const TELAS = GRUPOS.flatMap((g) => g.itens);

/** Um erro em uma tela não pode derrubar o menu nem as outras telas. */
class ProtecaoDaTela extends Component<{ children: ReactNode; chave: string }, { erro: boolean }> {
  state = { erro: false };

  static getDerivedStateFromError() {
    return { erro: true };
  }

  componentDidUpdate(anterior: { chave: string }) {
    if (anterior.chave !== this.props.chave && this.state.erro) this.setState({ erro: false });
  }

  render() {
    if (!this.state.erro) return this.props.children;
    return <Alert color="red" variant="light" title="Esta tela encontrou um erro">Recarregue a página. Se continuar, as outras telas seguem funcionando.</Alert>;
  }
}

const vistaDaUrl = () => window.location.pathname.split("/")[1] || "panorama";

export function Aplicacao() {
  const [eu, setEu] = useState<Eu | null>(null);
  const [fase, setFase] = useState<"carregando" | "entrada" | "dentro">("carregando");
  const [vista, setVista] = useState(vistaDaUrl);
  const [aberto, { toggle, close }] = useDisclosure();

  const abrir = () => ler<Eu>("/api/eu").then((d) => { setEu(d); setFase("dentro"); }).catch(() => {});

  useEffect(() => {
    const semSessao = () => { setEu(null); setFase("entrada"); };
    const voltar = () => setVista(vistaDaUrl());
    window.addEventListener("cripto:sem-sessao", semSessao);
    window.addEventListener("popstate", voltar);
    abrir();
    return () => {
      window.removeEventListener("cripto:sem-sessao", semSessao);
      window.removeEventListener("popstate", voltar);
    };
  }, []);

  if (fase === "entrada") return <Entrada aoEntrar={abrir} />;
  if (!eu) return <Center h="100%"><Loader color="gray" size="sm" /></Center>;

  const atual = TELAS.find((i) => i.id === vista) ?? TELAS[0];
  const Tela = atual.tela;

  const ir = (i: Item) => {
    window.history.pushState(null, "", `/${i.id}`);
    setVista(i.id);
    close();
  };

  const sair = async () => {
    await enviar("/api/sair");
    setEu(null);
    setFase("entrada");
  };

  return (
    <ContextoEu.Provider value={eu}>
      <AppShell header={{ height: 48 }} navbar={{ width: 224, breakpoint: "sm", collapsed: { mobile: !aberto } }} padding="lg">
        <AppShell.Header className="barra-metal">
          <Group h="100%" px="md" justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap">
              <Burger opened={aberto} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Abrir o menu" />
              <Avatar src="/estatico/pantera.webp" size={24} radius="sm" alt="" />
              <Text fw={600} size="sm">Panthera Crypto</Text>
              <Text size="sm" visibleFrom="sm" style={{ opacity: 0.85 }}>{eu.organizacao}</Text>
            </Group>
            <Menu position="bottom-end" shadow="md">
              <Menu.Target>
                <UnstyledButton aria-label="Menu da conta">
                  <Group gap={6} wrap="nowrap">
                    <Avatar size={24} radius="xl" color="dark" variant="filled" name={eu.nome} />
                    <Text size="sm" visibleFrom="sm">{eu.nome}</Text>
                    <IconChevronDown size={14} />
                  </Group>
                </UnstyledButton>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>{eu.email}</Menu.Label>
                <Menu.Item fz="sm" leftSection={<IconLogout size={14} />} onClick={sair}>Sair</Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </AppShell.Header>

        <AppShell.Navbar style={{ background: "var(--mantine-color-dark-7)", borderColor: "var(--roar-borda)" }}>
          <ScrollArea style={{ flex: 1 }} px={8} pb={8} component="nav" aria-label="Seções">
            {GRUPOS.map((g) => (
              <Box key={g.titulo}>
                <div className="menu-grupo">{g.titulo}</div>
                {g.itens.map((i) => {
                  const Icone = i.icone;
                  return (
                    <button key={i.id} type="button" className="menu-item" aria-current={atual.id === i.id ? "page" : undefined} onClick={() => ir(i)}>
                      <Icone size={16} stroke={1.6} />
                      <span>{i.rotulo}</span>
                    </button>
                  );
                })}
              </Box>
            ))}
          </ScrollArea>
          <div className="assinatura">Powered by<b>Mariana BS</b></div>
        </AppShell.Navbar>

        <AppShell.Main style={{ background: "var(--mantine-color-dark-8)" }}>
          <Box maw={1400} mx="auto">
            <ProtecaoDaTela chave={atual.id}><Tela /></ProtecaoDaTela>
          </Box>
        </AppShell.Main>
      </AppShell>
    </ContextoEu.Provider>
  );
}
