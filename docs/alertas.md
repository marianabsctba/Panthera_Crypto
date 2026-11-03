# Alertas

Como os eventos de cripto viram alerta. Nada disso foi testado ainda: é o desenho para a primeira fatia.

## Caminho

```
Bitcoin Core (ZMQ / walletnotify) ─┐
mempool (WebSocket)               ─┼─> coletor Panthera Crypto ─> regras ─> webhook, Telegram, e-mail
OpenZeppelin Monitor (webhook)    ─┘          │
                                              └─> consulta ao MISP (endereço em lista?)
```

O coletor junta as fontes, normaliza para um formato único, consulta o MISP pelos endereços de origem e de destino, aplica as regras e manda o alerta. Cada evento também é gravado numa linha JSON, para histórico e para quem quiser ligar outro sistema depois.

## Formato do evento

```json
{
  "origem": "panthera-crypto",
  "evento": "saida",
  "rede": "bitcoin",
  "carteira": "fria-principal",
  "organizacao": "cliente-exemplo",
  "transacao": "b6f6...e1a0",
  "estado": "mempool",
  "ativo": "BTC",
  "valor": "0.25000000",
  "valor_brl": "152340.00",
  "de": ["bc1q..."],
  "para": ["bc1p..."],
  "para_conhecido": false,
  "para_em_lista": "",
  "visto_em": "2026-11-03T10:15:00Z"
}
```

Valores de `evento`: `entrada`, `saida`, `aprovacao`, `aprovacao_ilimitada`, `valor_zero_suspeito`, `mudanca_contrato`, `saldo_exchange_caiu`.

`para_conhecido` diz se o destino está na agenda de endereços conferidos da carteira. `para_em_lista` traz o nome da lista do MISP em que o endereço apareceu, ou vazio.

## Regras

| Condição | Gravidade |
|---|---|
| Entrada | Informativa |
| Saída para endereço da agenda | Média |
| Saída para endereço fora da agenda | Alta |
| Saída acima do limite da carteira | Alta |
| Aprovação ilimitada | Alta |
| Valor zero de endereço parecido com um da agenda | Média, com aviso de envenenamento de endereço |
| Mudança de dono ou de implementação em contrato com valor aplicado | Alta |
| Qualquer endereço envolvido aparece em lista do MISP | Crítica |

Os limites e a agenda ficam no cadastro de cada carteira. As regras ficam no coletor, em arquivo de configuração, não espalhadas pelas fontes: o OpenZeppelin Monitor e o mempool só avisam que algo aconteceu.

## Canais

- Webhook genérico, para ligar em qualquer sistema.
- Telegram e e-mail para pessoas.
- [ntfy](https://github.com/binwiederhier/ntfy) (Apache-2.0) para notificação no celular sem depender de serviço de terceiro.

Alerta alto e crítico vai para pessoa na hora. Médio e informativo podem ir num resumo.

## Cuidados

- O coletor só tem chaves públicas e descritores só leitura. Nunca chave privada.
- Descritor e xpub revelam todo o histórico da carteira. Tratar como dado sensível: guardar cifrado e separado por organização.
- O alerta de saída para fora da agenda tem que sair no estado `mempool`, não só depois de confirmado.
- Mensagem de alerta não leva descritor nem saldo total, só o evento.
