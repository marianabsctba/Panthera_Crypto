import { createContext, useCallback, useContext, useEffect, useState } from "react";

export interface Eu {
  nome: string;
  email: string;
  organizacao: string;
  fuso?: string;
}

export const ContextoEu = createContext<Eu | null>(null);
export const useEu = () => useContext(ContextoEu)!;

export async function pedir(rota: string, opcoes?: RequestInit) {
  const r = await fetch(rota, { credentials: "same-origin", ...opcoes });
  if (r.status === 401 && rota !== "/api/entrar") {
    window.dispatchEvent(new Event("cripto:sem-sessao"));
    throw new Error("sem sessão");
  }
  return r;
}

export async function ler<T>(rota: string): Promise<T> {
  const r = await pedir(rota);
  if (!r.ok) throw new Error(await detalhe(r));
  return r.json();
}

export async function enviar(rota: string, corpo?: unknown, metodo = "POST") {
  return pedir(rota, {
    method: metodo,
    ...(corpo === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) }),
  });
}

export async function detalhe(r: Response, padrao = "Não foi possível concluir. Tente de novo.") {
  const corpo = await r.json().catch(() => ({}));
  return typeof corpo.detail === "string" ? corpo.detail : padrao;
}

export function useDados<T>(rota: string | null) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(rota !== null);
  const [versao, setVersao] = useState(0);
  const recarregar = useCallback(() => setVersao((v) => v + 1), []);
  useEffect(() => {
    if (rota === null) return;
    let valendo = true;
    setCarregando(true);
    ler<T>(rota)
      .then((d) => { if (valendo) { setDados(d); setErro(null); } })
      .catch((e: Error) => { if (valendo) setErro(e.message); })
      .finally(() => { if (valendo) setCarregando(false); });
    return () => { valendo = false; };
  }, [rota, versao]);
  return { dados, erro, carregando, recarregar };
}

/** Lista longa vem em páginas: cada página pede o que vem antes do último id já mostrado. */
export function usePaginas<T extends { id: number }>(rota: string, chave: string) {
  const [itens, setItens] = useState<T[] | null>(null);
  const [haMais, setHaMais] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  const recarregar = useCallback(() => setVersao((v) => v + 1), []);
  useEffect(() => {
    let valendo = true;
    setItens(null);
    ler<Record<string, unknown>>(rota)
      .then((d) => { if (valendo) { setItens(d[chave] as T[]); setHaMais(Boolean(d.ha_mais)); setErro(null); } })
      .catch((e: Error) => { if (valendo) setErro(e.message); });
    return () => { valendo = false; };
  }, [rota, chave, versao]);
  const mais = async () => {
    if (!itens?.length) return;
    const separador = rota.includes("?") ? "&" : "?";
    const d = await ler<Record<string, unknown>>(`${rota}${separador}antes=${itens[itens.length - 1].id}`);
    setItens([...itens, ...(d[chave] as T[])]);
    setHaMais(Boolean(d.ha_mais));
  };
  return { itens, haMais, erro, mais, recarregar };
}
