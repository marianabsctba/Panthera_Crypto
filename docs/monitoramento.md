# Monitoramento

Saber o que acontece com os endereços sem expor quem é o dono e sem depender de serviço de terceiro. Situação de cada projeto conferida em 3 de novembro de 2026.

## Por que nó próprio

Consultar saldo num explorer público entrega ao explorer a lista de endereços e o IP de quem consulta. Para monitorar carteiras de clientes, isso vaza o mapa inteiro. Com nó próprio, as consultas não saem da casa e o alerta não depende da API de alguém.

## Bitcoin

| Projeto | Licença | Papel |
|---|---|---|
| [Bitcoin Core](https://github.com/bitcoin/bitcoin) | MIT | O nó. Valida tudo sozinho. Carteira de descritores só leitura recebe as chaves públicas e acompanha os endereços |
| [Fulcrum](https://github.com/cculianu/Fulcrum) | GPL-3.0 | Servidor Electrum rápido sobre o Bitcoin Core, para Sparrow, Electrum e BlueWallet consultarem o nó próprio |
| [electrs](https://github.com/romanz/electrs) | MIT | O mesmo papel, mais leve em disco |
| [mempool](https://github.com/mempool/mempool) | AGPL-3.0 | Explorer e API própria, com WebSocket que avisa quando um endereço acompanhado recebe ou envia |
| [Esplora](https://github.com/Blockstream/esplora) | MIT | Explorer e API da Blockstream |
| [BTC RPC Explorer](https://github.com/janoside/btc-rpc-explorer) | MIT | Explorer simples direto no RPC. Sem commit desde fevereiro de 2026 |
| [peer-observer](https://github.com/peer-observer/peer-observer) | MIT | Observa o comportamento dos pares do nó. Útil para quem opera nó em produção e quer ver ataques à rede |
| [BTCPay Server](https://github.com/btcpayserver/btcpayserver) | MIT | Recebimento de pagamentos sem intermediário, com notificação por webhook |

Como montar o alerta em Bitcoin:

1. Importar no Bitcoin Core o descritor só leitura de cada carteira (`importdescriptors` numa carteira criada com `disable_private_keys`).
2. Assinar as notificações ZMQ do nó (`zmqpubrawtx` e `zmqpubhashblock`) ou usar o `walletnotify`, que roda um comando a cada transação que toca a carteira.
3. Para cada evento, separar entrada e saída, calcular o valor e mandar para o SOC no formato de [integração](integracao-soc.md).
4. Alertar já na transação vista na mempool, antes da confirmação: é o momento em que ainda há algo a fazer, como uma transação concorrente com taxa maior se a saída foi indevida e a carteira ainda tem outra chave.

Para quem não quer escrever o passo 3, a API WebSocket do mempool próprio faz o acompanhamento por endereço.

Lightning tem os próprios nós ([LND](https://github.com/lightningnetwork/lnd), MIT; [Core Lightning](https://github.com/ElementsProject/lightning), BSD-MIT; [Eclair](https://github.com/ACINQ/eclair), Apache-2.0) e o próprio risco: o nó é carteira quente por natureza. Monitorar canais fechados à força e saldo dos canais. [LNbits](https://github.com/lnbits/lnbits) (MIT) organiza contas sobre um nó.

Distribuições prontas para rodar tudo isso em casa: [RaspiBlitz](https://github.com/raspiblitz/raspiblitz) (MIT) e [StartOS](https://github.com/Start9Labs/start-technologies) (MIT). Umbrel ficou nos [descartados](descartados.md) pela licença.

## Redes EVM (Ethereum e compatíveis)

| Projeto | Licença | Papel |
|---|---|---|
| [Geth](https://github.com/ethereum/go-ethereum) | LGPL-3.0 | Cliente de execução mais usado |
| [Nethermind](https://github.com/NethermindEth/nethermind) | GPL-3.0 | Cliente de execução alternativo, bom para diversidade |
| [Lighthouse](https://github.com/sigp/lighthouse) | Apache-2.0 | Cliente de consenso, necessário junto com o de execução |
| [OpenZeppelin Monitor](https://github.com/OpenZeppelin/openzeppelin-monitor) | AGPL-3.0 | Acompanha endereços, transferências e eventos de contrato em várias redes e dispara webhook, Slack, Telegram, e-mail ou script. É a peça principal |
| [rindexer](https://github.com/joshstevens19/rindexer) | MIT | Indexa eventos de contratos para Postgres por configuração, sem código |
| [Ponder](https://github.com/ponder-sh/ponder) | MIT | Indexador em TypeScript, para lógica própria |
| [Otterscan](https://github.com/otterscan/otterscan) | MIT | Explorer local sobre Erigon ou Reth. Sem commit desde fevereiro de 2026 |
| [Sourcify](https://github.com/argotorg/sourcify) | MIT | Verifica que o código-fonte publicado corresponde ao contrato na rede |

O que acompanhar em EVM, além de entrada e saída de valor:

- `Approval` e `ApprovalForAll` emitidos pelos endereços acompanhados, porque é o primeiro passo de um drainer;
- mudança de dono, de implementação (proxy) ou de parâmetros nos contratos em que há dinheiro aplicado;
- transferência de valor zero vinda de endereço parecido, que é envenenamento de endereço;
- saída de valor grande do contrato do protocolo usado, que costuma ser o primeiro sinal de invasão.

Rodar nó completo de cada rede custa disco e manutenção. Um meio-termo aceitável é nó próprio para Ethereum e Bitcoin e RPC de terceiro para redes menores, sabendo que esse terceiro vê os endereços consultados.

## Visão da carteira inteira

[rotki](https://github.com/rotki/rotki) (AGPL-3.0) junta saldo e histórico de várias redes e exchanges num banco local, criptografado, sem mandar nada para servidor dele. Serve para conferência e para imposto. Não é ferramenta de alerta.

## Exchanges

O monitoramento de conta em exchange depende da API de cada uma, e nenhuma é open source. O que dá para fazer:

- chave de API só leitura para puxar saldo e saques;
- alerta quando o saldo cai sem saque autorizado ou quando aparece endereço novo na lista de saque;
- rotki já lê várias exchanges e pode ser a fonte.
