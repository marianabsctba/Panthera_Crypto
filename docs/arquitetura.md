# Arquitetura de referência e próximos passos

## Camadas

```
┌──────────────────────────── Proteção ────────────────────────────┐
│ Multisig 2 de 3 (Sparrow + BitBox02 + Jade + SeedSigner)         │
│ ou Liana com recuperação por prazo                               │
│ Safe em EVM, Rabby para assinar, revoke.cash mensal              │
│ OpenBao para segredos de serviço, Gitleaks no CI                 │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────── Fontes ──────────────────────────────┐
│ Bitcoin Core + Fulcrum + mempool    Geth + Lighthouse            │
│ (descritores só leitura, ZMQ)       OpenZeppelin Monitor         │
│                                     rindexer para eventos        │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────── Panthera ────────────────────────────┐
│ Coletor Panthera Crypto: normaliza, consulta listas, grava JSON  │
│ MISP: listas OFAC, ScamSniffer, indicadores dos incidentes       │
│ Wazuh: regras, alerta, resposta                                  │
│ Panthera Track: chamado aberto pelo alerta                       │
└──────────────────────────────────────────────────────────────────┘
```

## O que o Panthera Crypto escreveria

Quase tudo acima já existe. O que falta e seria código do projeto:

1. **Coletor**: junta ZMQ do Bitcoin Core, WebSocket do mempool e webhook do OpenZeppelin Monitor num formato único e grava para o Wazuh ([formato](integracao-soc.md)).
2. **Cadastro de carteiras por organização**: descritores e endereços só leitura, agenda de endereços conferidos, limites de valor por carteira. Guardado cifrado.
3. **Carga das listas no MISP**: tarefa que baixa a lista OFAC e a do ScamSniffer e atualiza os feeds.
4. **Regras do Wazuh** para os eventos de cripto.
5. **Tela no console do Roar** para as carteiras e os alertas, se fizer sentido juntar.

## Fases

| Fase | Entrega | Pronto quando |
|---|---|---|
| 1 | Bitcoin Core em testnet4 + carteira só leitura + `walletnotify` gravando JSON | Uma transação de teste vira alerta no Wazuh com o valor certo |
| 2 | Agenda de endereços e regra de destino desconhecido, alerta ainda na mempool | Saída para endereço fora da agenda gera alerta de nível alto antes da confirmação |
| 3 | Listas OFAC e ScamSniffer no MISP, consulta pelo coletor | Endereço da lista no destino gera alerta crítico |
| 4 | EVM em Sepolia com OpenZeppelin Monitor: transferências, aprovações ilimitadas e valor zero | Os três tipos viram alerta, testados com contratos de teste próprios |
| 5 | Teste com casos reais reproduzidos do DeFiHackLabs em fork local | As regras disparam nos casos escolhidos |
| 6 | Mainnet, só leitura, para uma organização piloto | Uma semana sem falso positivo crítico |

Testar sempre em testnet e em fork local primeiro. O projeto não toca em chave privada em nenhuma fase.

## Decisões em aberto

- Rodar nó próprio de Ethereum (cerca de 2 TB em SSD) ou começar com RPC de terceiro e aceitar que ele vê os endereços.
- Coletor em Python, como a ingestão do Roar, ou em Go.
- Se as carteiras ficam no banco do Roar, com o isolamento por organização que já existe, ou num banco próprio.
- Licenças: Slither, Echidna, MISP e OpenZeppelin Monitor são AGPL-3.0. Usar como serviço separado não obriga a abrir o código do Panthera, mas modificar e oferecer pela rede obriga a publicar a modificação.
