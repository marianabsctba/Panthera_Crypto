# Alertas

Cada movimento que toca uma carteira acompanhada passa pelas regras. O que importa vira alerta, e o alerta vai para os canais da organização.

## Regras

| Condição | Gravidade |
|---|---|
| Entrada | Baixa |
| Saída para endereço conferido | Média |
| Saída para endereço fora dos conferidos | Alta |
| Saída acima do limite da carteira | Alta, mesmo para endereço conferido |
| Valor mínimo (até 1.000 satoshis) vindo de endereço parecido com um conferido | Média, como possível envenenamento de endereço |
| Qualquer endereço da outra ponta numa lista de sanções | Crítica, nos dois sentidos |
| Movimento interno, só troco e taxa | Não alerta |

"Parecido" é ter o mesmo começo e o mesmo fim, que é o que as pessoas conferem com os olhos.

O alerta sai com a transação ainda na mempool. É o momento em que ainda dá para agir: mover o que sobrou nas outras carteiras, avisar a exchange de destino, revogar o que precisar.

O que já estava na carteira antes do cadastro entra como ponto de partida e não gera alerta.

## Canais

- **ntfy**: notificação no celular, com prioridade pela gravidade. Pode ser um servidor ntfy próprio.
- **Webhook**: um JSON por alerta, para ligar em sistema de chamados ou qualquer outro.

Cada canal escolhe a gravidade mínima. Canal fora do ar recebe de novo, cada vez mais espaçado, por até 12 tentativas. O alerta fica gravado de qualquer jeito.

A mensagem leva a carteira, o valor, os motivos e a transação. Nunca leva descritor, chave pública estendida nem saldo.

Canal que aponte para endereço interno (127.0.0.1, rede privada, link-local) é recusado. Sem isso, uma organização poderia usar o avisador para alcançar serviços de dentro da instalação.

## Webhook

```json
{
  "origem": "panthera-crypto",
  "alerta": 1234,
  "severidade": "alta",
  "titulo": "Saída da carteira",
  "motivos": ["Destino fora dos endereços conferidos", "Valor acima do limite da carteira"],
  "carteira": "Fria principal",
  "rede": "bitcoin",
  "movimento": {
    "tipo": "saida",
    "transacao": "6e0bc01b0537…",
    "estado": "mempool",
    "valor_sats": 62000000,
    "contrapartes": [{"endereco": "bc1q…", "valor_sats": 62000000}]
  },
  "criado_em": "2026-11-05T15:54:00+00:00"
}
```
