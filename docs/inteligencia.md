# Inteligência e rastreio

Saber se um endereço é ruim antes de mandar ou de aceitar valor, e seguir o dinheiro depois de um incidente. Situação conferida em 3 de novembro de 2026.

## Listas de endereços

| Fonte | Licença | Conteúdo |
|---|---|---|
| [ofac-sanctioned-digital-currency-addresses](https://github.com/0xB10C/ofac-sanctioned-digital-currency-addresses) | MIT | Endereços da lista de sanções dos EUA (SDN), extraídos e separados por moeda, atualizados de forma automática |
| [ScamSniffer scam-database](https://github.com/scamsniffer/scam-database) | GPL-3.0 | Domínios e endereços de golpes e drainers em redes EVM |
| [eth-phishing-detect](https://github.com/MetaMask/eth-phishing-detect) | DBAD 1.2 | Lista de domínios de phishing usada pela MetaMask. Licença permissiva, mas incomum: ler antes de redistribuir |

A lista de sanções interessa para conformidade e é a que a polícia e as exchanges usam. As de golpe servem para alertar o usuário, mas têm falso positivo e envelhecem rápido.

Uso no Panthera: carregar essas listas no MISP como feeds e conferir cada endereço de destino e de origem contra elas. O MISP já tem os tipos de atributo `btc` e `xmr` e o objeto `cryptocurrency-transaction`, e o [Panthera Roar](https://github.com/marianabsctba/Panthera_Roar) já traz MISP e listas de contexto.

## Rastreio de fluxo

| Projeto | Licença | Situação |
|---|---|---|
| [GraphSense](https://github.com/graphsense/graphsense-lib) | MIT | Ativo. Agrupa endereços que pertencem à mesma carteira, cruza com etiquetas e mostra o caminho dos fundos em Bitcoin e Ethereum, entre outras. Pesado: precisa de Cassandra e Spark para a rede inteira |
| [BlockSci](https://github.com/citp/BlockSci) | GPL-3.0 | Parado desde 2021, só para pesquisa |

Para incidente pontual, seguir o valor à mão com o explorer próprio (mempool, Otterscan) costuma bastar até chegar a uma exchange. Aí o caminho é a exchange e a polícia, com os hashes das transações e os horários. As ferramentas comerciais de rastreio (Chainalysis, TRM, Elliptic) não são abertas e ficam fora deste levantamento.

## O que guardar de cada incidente

- hash da transação, rede, endereços de origem e de destino, valor e horário;
- como a chave ou a assinatura foi obtida;
- se houve aprovação, qual contrato e quando foi dada.

Isso vira indicador no MISP e ajuda no próximo caso.
