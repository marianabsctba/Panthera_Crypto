import { Alert, Button, Card, Center, Image, PasswordInput, Stack, Text, TextInput, Title } from "@mantine/core";
import { useState, type FormEvent } from "react";

import { detalhe, enviar } from "./api";

export function Entrada({ aoEntrar }: { aoEntrar: () => void }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const entrar = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    const r = await enviar("/api/entrar", { email, senha }).finally(() => setEnviando(false));
    setSenha("");
    if (!r.ok) {
      setErro(await detalhe(r, "Não foi possível entrar."));
      return;
    }
    aoEntrar();
  };

  return (
    <Center h="100%" p="md" style={{ background: "radial-gradient(circle at 50% 0%, #2a0a1d 0%, var(--mantine-color-dark-8) 55%)" }}>
      <Card w={360} p="xl">
        <form onSubmit={entrar} noValidate>
          <Stack gap="md">
            <Stack gap={6} align="center">
              <Image src="/estatico/pantera.webp" alt="" w={64} h={64} radius="md" />
              <Title order={1}>Panthera Crypto</Title>
            </Stack>
            <TextInput label="E-mail" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.currentTarget.value)} autoFocus />
            <PasswordInput label="Senha" autoComplete="current-password" value={senha} onChange={(e) => setSenha(e.currentTarget.value)} />
            {erro && <Alert color="red" variant="light" p="xs"><Text size="sm">{erro}</Text></Alert>}
            <Button type="submit" variant="filled" loading={enviando} disabled={!email.trim() || !senha} fullWidth>Entrar</Button>
            <div className="assinatura assinatura-centro">Powered by<b>Mariana BS</b></div>
          </Stack>
        </form>
      </Card>
    </Center>
  );
}
