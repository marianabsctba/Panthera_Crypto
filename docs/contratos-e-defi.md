# Contratos e DeFi

Para quem usa protocolos em redes EVM e para quem escreve contratos. Situação de cada projeto conferida em 3 de novembro de 2026.

## Antes de assinar

A maior parte do roubo em DeFi não vem de bug em contrato, vem de a própria vítima assinar. As defesas, em ordem de impacto:

1. **Carteira separada para sites novos.** Uma carteira quente com pouco valor para testar. O valor fica em outra, que só assina com protocolos conhecidos.
2. **Simulação.** [Rabby](https://github.com/RabbyHub/Rabby) (MIT) simula a transação e mostra o que sai e o que entra antes de assinar. Assinatura de mensagem (`permit`, `Permit2`, ordens) também precisa ser lida: não move nada na hora, mas autoriza mover depois.
3. **Desconfiar de aprovação ilimitada.** Aprovar só o valor da operação.
4. **Assinar na carteira de hardware e ler a tela.** Se a carteira mostra "assinatura cega" (só um hash), não assinar.

## Aprovações esquecidas

[revoke.cash](https://github.com/RevokeCash/revoke.cash) (MIT): lista todas as aprovações dadas por um endereço, em várias redes, e permite revogar. Pode rodar localmente a partir do código.

Rotina sugerida: revisar todo mês e depois de qualquer notícia de invasão de protocolo. O [monitoramento](monitoramento.md) avisa quando surge aprovação nova, o que fecha o ciclo.

## Analisar contrato

Para quem publica contrato, ou para olhar um protocolo antes de colocar valor.

| Projeto | Licença | Tipo | Observação |
|---|---|---|---|
| [Slither](https://github.com/crytic/slither) | AGPL-3.0 | Análise estática | Rápido, roda em todo commit. O primeiro a usar |
| [Aderyn](https://github.com/Cyfrin/aderyn) | GPL-3.0 | Análise estática | Em Rust, complementa o Slither |
| [Foundry](https://github.com/foundry-rs/foundry) | Apache-2.0 | Testes e fuzz | Testes em Solidity, fuzz e testes de invariantes, e cópia da rede real (fork) para testar contra o estado de verdade |
| [Echidna](https://github.com/crytic/echidna) | AGPL-3.0 | Fuzz por propriedades | Procura sequência de chamadas que quebra uma regra escrita |
| [Medusa](https://github.com/crytic/medusa) | AGPL-3.0 | Fuzz por propriedades | Sucessor do Echidna em Go, paralelo |
| [Mythril](https://github.com/ConsenSysDiligence/mythril) | MIT | Execução simbólica | Sem commit desde abril de 2026, ainda útil |
| [Halmos](https://github.com/a16z/halmos) | AGPL-3.0 | Verificação simbólica dos testes do Foundry | Sem commit desde agosto de 2025, usar com cuidado |
| [OpenZeppelin Contracts](https://github.com/OpenZeppelin/openzeppelin-contracts) | MIT | Biblioteca | Usar peças prontas e auditadas em vez de escrever do zero |
| [DeFiHackLabs](https://github.com/SunWeb3Sec/DeFiHackLabs) | Apache-2.0 | Base de casos | Reprodução em Foundry de centenas de invasões reais. Serve para treinar e para testar regras de detecção |

Ferramenta nenhuma substitui auditoria por gente para contrato que guarda valor de terceiros. A ordem razoável é: Slither e Aderyn no CI, testes de invariantes com Foundry ou Medusa, auditoria externa, programa de recompensa por falhas e só então dinheiro de verdade.

## Olhar um protocolo antes de entrar

Sem auditar, dá para conferir:

- se o código está verificado (Sourcify) e se é o mesmo que foi auditado;
- quem pode trocar o contrato: uma chave só, um multisig, um `timelock` com quantos dias;
- há quanto tempo está no ar e quanto valor guarda, porque valor alto há muito tempo é um teste involuntário;
- se já foi invadido e como respondeu.

E limitar a exposição: nenhum protocolo com mais do que a parte da carteira que a pessoa aceita perder.
