# Panthera Crypto

Levantamento de como monitorar e proteger criptomoedas usando só projetos open source. É o ponto de partida do projeto: antes de escrever código, saber o que já existe, o que está vivo e o que tem licença que permite uso livre.

Nada aqui é recomendação de investimento. O foco é segurança: não perder a chave, não assinar o que não devia e saber logo quando algo se mexe.

## Documentos

1. [Ameaças](docs/ameacas.md): o que de fato rouba ou faz perder cripto, e qual controle responde a cada coisa
2. [Custódia](docs/custodia.md): carteiras de hardware e de software, multisig, recuperação com prazo, MPC, backup da seed e chaves de servidor
3. [Monitoramento](docs/monitoramento.md): nó próprio, endereços em modo só leitura e alertas de movimentação em Bitcoin e em redes EVM
4. [Contratos e DeFi](docs/contratos-e-defi.md): análise de contratos, simulação antes de assinar e revogação de aprovações
5. [Inteligência e rastreio](docs/inteligencia.md): listas de sanções e de golpes, análise de fluxo e MISP
6. [Alertas](docs/alertas.md): formato dos eventos, regras e canais de aviso
7. [Arquitetura de referência e próximos passos](docs/arquitetura.md)
8. [Descartados](docs/descartados.md): projetos conhecidos que ficaram de fora por licença ou por estarem parados

## Como foi feito

A lista de projetos e o estado de cada um foram conferidos em 3 de novembro de 2026 pela API do GitHub: licença declarada, data do último push e se o repositório está arquivado. Quando a licença aparecia como "outra" (`NOASSERTION`), o texto foi lido. Projeto sem commit há mais de um ano, ou com licença que proíbe uso comercial, foi para a lista de descartados ou aparece com aviso.

Isso confirma que o projeto existe, está ativo e é aberto. Não confirma que é seguro. Nenhum foi instalado ou testado ainda.

## Resumo

| Necessidade | Escolha principal | Alternativas |
|---|---|---|
| Guardar a chave de quem tem valor relevante | Multisig 2 de 3 com carteiras de fabricantes diferentes | Liana com chave de recuperação por prazo |
| Carteira de hardware | BitBox02, Blockstream Jade, Trezor (firmware) | SeedSigner (sem estado, montada em casa), Keystone, KeepKey |
| Coordenar carteira Bitcoin no computador | Sparrow | Electrum, Specter, Nunchuk, Liana |
| Nó e consultas Bitcoin sem depender de terceiros | Bitcoin Core + Fulcrum ou electrs + mempool | Esplora, BTC RPC Explorer |
| Alerta de movimentação em Bitcoin | Descritor só leitura no Bitcoin Core + ZMQ | Sparrow só leitura, API do mempool próprio |
| Nó EVM | Geth ou Nethermind + Lighthouse | — |
| Alerta de movimentação e eventos em EVM | OpenZeppelin Monitor | rindexer, Ponder |
| Visão da carteira inteira, local | rotki | — |
| Antes de assinar em DeFi | Rabby (simula a transação) | — |
| Aprovações esquecidas | revoke.cash | — |
| Analisar contrato antes de interagir ou publicar | Slither + Aderyn, Foundry, Echidna ou Medusa | Mythril, Halmos |
| Chaves de servidor (API de exchange, assinador) | OpenBao | Web3Signer e Dirk para validadores |
| Listas de endereços ruins | Lista OFAC extraída (0xB10C), ScamSniffer | lista de phishing da MetaMask |
| Rastrear fluxo de fundos | GraphSense | — |
| Avisar quem precisa saber | Coletor próprio com regras, consultando o MISP | ntfy, Telegram, e-mail, webhook |

O ponto mais importante não é ferramenta: a maior parte das perdas vem de seed mal guardada, de assinar transação sem entender e de aprovação ilimitada esquecida. As ferramentas de monitoramento avisam depressa, mas em cadeia pública não há estorno. Proteger vem antes de monitorar.
