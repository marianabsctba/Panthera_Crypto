# Ameaças

Lista do que costuma levar à perda de criptomoeda, de quem guarda para si e de quem guarda para outros. Para cada uma, o controle que mais ajuda e onde ele está descrito.

| Ameaça | Como acontece | Controle principal | Onde |
|---|---|---|---|
| Perda da seed | Papel perdido, incêndio, a única pessoa que sabia morreu | Backup em metal em dois lugares, multisig, plano de herança | [Custódia](custodia.md) |
| Roubo da seed | Foto no celular, seed digitada em site falso, backup em nuvem | Seed nunca em aparelho conectado, passphrase, multisig | [Custódia](custodia.md) |
| Malware no computador | Troca o endereço copiado (clipper), altera o que a tela mostra | Conferir o endereço na tela da carteira de hardware | [Custódia](custodia.md) |
| Envenenamento de endereço | Golpista manda valor zero de um endereço parecido para aparecer no histórico | Agenda de endereços conferidos, nunca copiar do histórico | [Custódia](custodia.md) |
| Assinatura maliciosa (drainer) | Site pede `permit`, `setApprovalForAll` ou transação disfarçada | Simulação antes de assinar, carteira separada para testar sites | [Contratos e DeFi](contratos-e-defi.md) |
| Aprovação ilimitada esquecida | Contrato aprovado anos atrás é invadido e esvazia a carteira | Revisão periódica e revogação | [Contratos e DeFi](contratos-e-defi.md) |
| Falha no contrato usado | Bug em protocolo DeFi ou ponte entre redes | Análise antes de entrar, limite de exposição por protocolo, alerta de eventos | [Contratos e DeFi](contratos-e-defi.md) |
| Carteira adulterada | Aparelho interceptado, app falso na loja, atualização maliciosa | Comprar direto do fabricante, conferir assinatura do firmware e do app | [Custódia](custodia.md) |
| Conta de exchange invadida | Troca de chip (SIM swap), senha vazada, chave de API com saque | Chave física no login, chave de API só leitura, lista de saque bloqueada | [Monitoramento](monitoramento.md) |
| Chave de servidor vazada | Chave privada em variável de ambiente, em repositório ou em log | Cofre de segredos, varredura de repositório | [Custódia](custodia.md) |
| Coação física | Ameaça para obrigar a transferir | Multisig com chave fora de alcance, prazo de recuperação, discrição | [Custódia](custodia.md) |
| Vigilância e exposição | Saldo associado à pessoa por endereço reutilizado ou consulta em explorer de terceiros | Nó próprio, não reutilizar endereço | [Monitoramento](monitoramento.md) |
| Receber fundos sujos | Valor de origem sancionada ou de golpe cai na carteira | Conferir contra listas antes de aceitar | [Inteligência](inteligencia.md) |

## O que monitoramento resolve e o que não resolve

Em rede pública, transação confirmada não volta. Um alerta de saída serve para:

- descobrir que uma chave vazou e mover o que sobrou nas outras carteiras antes que levem;
- revogar aprovações e avisar a exchange de destino, que às vezes ainda consegue congelar;
- ter registro com horário para a investigação e para a polícia.

Onde existe tempo de espera, o monitoramento vira proteção de fato: em multisig com prazo, em contrato com `timelock` e em cofre com saque atrasado, o alerta chega antes de o dinheiro sair. Por isso a [arquitetura](arquitetura.md) junta as duas coisas.
