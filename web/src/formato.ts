export const numero = (v: number | string | null | undefined) => (v === null || v === undefined ? "-" : Number(v).toLocaleString("pt-BR"));

export function compacto(v: number) {
  return v.toLocaleString("pt-BR", { notation: v >= 10000 ? "compact" : "standard", maximumFractionDigits: 1 });
}

/** Valor em BTC a partir de satoshis, sempre com as oito casas: quem confere valor confere até o fim. */
export function btc(sats: number | string | null | undefined) {
  if (sats === null || sats === undefined) return "-";
  const n = Number(sats);
  const inteiro = Math.trunc(Math.abs(n) / 1e8);
  const fracao = String(Math.abs(n) % 1e8).padStart(8, "0");
  return `${n < 0 ? "-" : ""}${inteiro.toLocaleString("pt-BR")},${fracao}`;
}

/** Para números grandes de painel: sem as casas que não cabem. */
export function btcCurto(sats: number) {
  const v = sats / 1e8;
  return v.toLocaleString("pt-BR", { maximumFractionDigits: v >= 100 ? 2 : v >= 0.0001 || v === 0 ? 4 : 8 });
}

export function quando(valor: string | null | undefined, fuso?: string) {
  if (!valor) return "-";
  return new Date(valor).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: fuso });
}

export function diaCurto(valor: string) {
  const [, mes, dia] = valor.slice(0, 10).split("-");
  return `${dia}/${mes}`;
}

export function ha(valor: string | null | undefined) {
  if (!valor) return "nunca";
  const segundos = Math.round((Date.now() - new Date(valor).getTime()) / 1000);
  if (segundos < 60) return "agora";
  if (segundos < 3600) return `há ${Math.round(segundos / 60)} min`;
  if (segundos < 172800) return `há ${Math.round(segundos / 3600)} h`;
  return `há ${Math.round(segundos / 86400)} dias`;
}

export const REDES: Record<string, string> = { bitcoin: "Bitcoin", testnet4: "Testnet4", signet: "Signet", regtest: "Regtest" };
export const TIPOS: Record<string, string> = { entrada: "Entrada", saida: "Saída", interno: "Interno" };
export const SERVICOS: Record<string, string> = {
  avaliador: "Avaliação", avisador: "Avisos", tarefas: "Partida de carteiras", manutencao: "Manutenção",
  "ingestor-bitcoin": "Leitura da rede Bitcoin", "ingestor-testnet4": "Leitura da Testnet4", "ingestor-signet": "Leitura da Signet", "ingestor-regtest": "Leitura da Regtest",
};
