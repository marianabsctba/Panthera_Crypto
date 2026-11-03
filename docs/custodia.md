# Custódia

Como guardar a chave. Situação de cada projeto conferida em 3 de novembro de 2026.

## Carteiras de hardware

A carteira de hardware guarda a chave fora do computador e mostra na própria tela o que vai ser assinado. É ela que derrota malware no computador, desde que a pessoa confira o endereço e o valor na tela do aparelho.

| Projeto | Licença | Observação |
|---|---|---|
| [Trezor](https://github.com/trezor/trezor-firmware) (firmware) | GPL-3.0 no núcleo, LGPL-3.0 e MIT em partes | Firmware aberto. O app Trezor Suite tem licença própria e não é open source, ver [descartados](descartados.md). Funciona com Sparrow e Electrum |
| [BitBox02](https://github.com/BitBoxSwiss/bitbox02-firmware) | Apache-2.0 | Firmware e app ([bitbox-wallet-app](https://github.com/BitBoxSwiss/bitbox-wallet-app)) abertos. Tem versão só Bitcoin |
| [Blockstream Jade](https://github.com/Blockstream/Jade) | MIT | Pode guardar a seed protegida por um servidor de PIN que a própria pessoa hospeda |
| [SeedSigner](https://github.com/SeedSigner/seedsigner) | MIT | Montada em casa com Raspberry Pi Zero. Não guarda nada: a seed entra por QR a cada uso. Boa para multisig |
| [Keystone 3](https://github.com/KeystoneHQ/keystone3-firmware) | MIT | Sem cabo e sem rádio, só QR. Várias redes |
| [KeepKey](https://github.com/keepkey/keepkey-firmware) | LGPL-3.0 | Ativo, mas com bem menos atividade que os acima |

Coldcard é muito usada em Bitcoin, mas a licença é MIT com a cláusula Commons Clause, o que a torna código disponível e não open source. Ficou nos [descartados](descartados.md) por esse critério, não por falta de qualidade.

Regras de compra e uso:

- comprar direto do fabricante, nunca usado nem em marketplace;
- conferir a assinatura do firmware e do app antes de instalar;
- gerar a seed no próprio aparelho, nunca aceitar seed que veio na caixa;
- usar fabricantes diferentes em multisig, para que uma falha de um não comprometa o todo.

## Carteiras de software

Servem como coordenadoras: montam a transação, mostram saldo e histórico e mandam para a carteira de hardware assinar. Também funcionam em modo só leitura, sem chave nenhuma, o que é a base do [monitoramento](monitoramento.md).

| Projeto | Licença | Uso |
|---|---|---|
| [Sparrow](https://github.com/sparrowwallet/sparrow) | Apache-2.0 | Bitcoin no computador. Melhor opção para multisig, conecta no nó próprio |
| [Electrum](https://github.com/spesmilo/electrum) | MIT | Bitcoin, a mais antiga em uso. Tem versão para Android |
| [Liana](https://github.com/wizardsardine/liana) | BSD-3-Clause | Bitcoin com caminho de recuperação que só abre depois de um prazo sem movimento. Resolve herança e perda de chave sem confiar em terceiro |
| [Specter Desktop](https://github.com/cryptoadvance/specter-desktop) | MIT | Bitcoin multisig ligado ao Bitcoin Core |
| [Nunchuk](https://github.com/nunchuk-io/nunchuk-desktop) | GPL-3.0 | Multisig com app de celular |
| [Wasabi](https://github.com/WalletWasabi/WalletWasabi) | MIT | Bitcoin com foco em privacidade |
| [BlueWallet](https://github.com/BlueWallet/BlueWallet) | MIT | Bitcoin no celular, inclusive só leitura |
| [Blockstream Green](https://github.com/Blockstream/green_qt) | GPL-3.0 | Bitcoin e Liquid, com opção de 2 de 2 com prazo |
| [Rabby](https://github.com/RabbyHub/Rabby) | MIT | Redes EVM. Simula a transação e mostra o que vai sair antes de assinar |
| [Safe](https://github.com/safe-global/safe-wallet-monorepo) | GPL-3.0 (app), LGPL-3.0 ([contratos](https://github.com/safe-fndn/safe-smart-account)) | Multisig em redes EVM, feito por contrato |

## Multisig e recuperação com prazo

Para valor que dói perder, a recomendação é multisig 2 de 3:

- três chaves em três aparelhos de fabricantes diferentes;
- guardadas em três lugares diferentes;
- qualquer duas movem, e perder uma não perde nada;
- o arquivo de configuração (descritor, com as três chaves públicas) tem cópia junto de cada chave, porque sem ele as seeds sozinhas não reconstroem a carteira.

O Liana troca parte dessa complexidade por tempo: uma chave do dia a dia e uma ou mais chaves de recuperação que só valem depois de, por exemplo, seis meses sem movimento. Serve para herança e para quem não quer guardar três aparelhos.

Em redes EVM, o equivalente é o Safe. Ele é um contrato, então o risco de bug no contrato soma ao resto, e cada rede tem o próprio endereço.

## MPC

Bibliotecas de MPC dividem a chave entre várias partes sem que ela exista inteira em lugar nenhum. São para quem constrói custódia para terceiros, não para uso pessoal.

| Projeto | Licença | Observação |
|---|---|---|
| [cb-mpc](https://github.com/coinbase/cb-mpc) | MIT | Da Coinbase, ativo |
| [tss-lib](https://github.com/bnb-chain/tss-lib) | MIT | Em Go, usada em várias pontes |
| [mpc-lib](https://github.com/fireblocks/mpc-lib) | GPL-3.0 | Da Fireblocks |
| [multi-party-sig](https://github.com/taurushq-io/multi-party-sig) | Apache-2.0 | Sem commit desde setembro de 2025 |

Implementação própria de MPC tem histórico ruim de falhas graves. Se o Panthera precisar disso, usar uma dessas e contratar auditoria.

## Backup da seed

- Placa de metal gravada ou com letras de encaixe, nunca só papel.
- Passphrase (a "25ª palavra" do BIP39) protege contra quem achar a seed, mas vira mais uma coisa para não perder. Guardar separada da seed.
- SLIP-39 (Shamir), aceito pela Trezor, divide a seed em partes, por exemplo 3 de 5. É alternativa ao multisig quando há um aparelho só, mas a seed volta a existir inteira na hora de recuperar.
- Nunca fotografar, digitar em computador, guardar em gerenciador de senhas na nuvem ou mandar por mensagem.
- Testar a recuperação uma vez, com valor pequeno, antes de colocar o valor grande.

## Chaves de servidor

Quando um sistema precisa assinar sozinho (carteira quente de uma plataforma, validador, robô com chave de API de exchange), a chave fica no servidor e o risco muda.

| Projeto | Licença | Uso |
|---|---|---|
| [OpenBao](https://github.com/openbao/openbao) | MPL-2.0 | Cofre de segredos derivado do Vault antes da troca de licença. Guarda chave de API e segredos de serviço |
| [Web3Signer](https://github.com/Consensys-Incorporated/web3signer) | Apache-2.0 | Assinador remoto para validadores Ethereum, com proteção contra assinatura dupla |
| [Dirk](https://github.com/attestantio/dirk) | Apache-2.0 | Assinador distribuído para validadores, com limiar |
| [Gitleaks](https://github.com/gitleaks/gitleaks) | MIT | Procura chave privada e seed esquecida em repositório |
| [TruffleHog](https://github.com/trufflesecurity/trufflehog) | AGPL-3.0 | O mesmo, e confere se a chave achada ainda vale |

Regras:

- carteira quente com o mínimo necessário, reabastecida a partir da fria por processo com aprovação humana;
- chave de API de exchange sem permissão de saque, ou com lista fechada de endereços de saque;
- chave privada nunca em variável de ambiente, imagem de contêiner ou log.
