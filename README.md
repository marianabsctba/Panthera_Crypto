# Panthera Crypto

Monitoramento de carteiras de criptomoeda com open source, para muitas organizações ao mesmo tempo. Acompanha carteiras só pela parte pública, avisa quando o dinheiro se mexe e confere cada movimento contra os endereços conferidos e as listas de sanções. Nada aqui assina ou move valor.

**Powered by Mariana BS**

**Estado:** em construção. Pronto: Bitcoin (rede principal, testnet4, signet e regtest), carteiras por descritor ou endereços avulsos, alertas, canais de aviso e a console. Redes EVM vêm depois. A arquitetura e o que falta estão em [docs/arquitetura.md](docs/arquitetura.md).

## Como funciona

O nó Bitcoin próprio entrega cada transação e cada bloco uma vez, e o Panthera casa tudo de uma vez com os endereços de todas as organizações. O custo segue o volume da rede, não o número de endereços acompanhados. Nenhum endereço é consultado em serviço de terceiros.

## Instalar

Requer Linux com Docker, rodando como root ou com `sudo`. Na rede principal, o nó precisa de cerca de 800 GB em SSD e alguns dias para baixar a cadeia.

```bash
sudo bash infra/subir.sh --rede bitcoin
```

Os segredos ficam em `/opt/panthera-crypto/.env`. Rodar o mesmo comando de novo atualiza. Para mais vazão, mais cópias do avaliador e do avisador:

```bash
sudo docker compose -p panthera-crypto --env-file /opt/panthera-crypto/.env -f infra/docker-compose.yml up -d --scale avaliador=4 --scale avisador=2
```

Para criar uma organização e o primeiro acesso (a senha aparece uma vez só):

```bash
sudo docker compose -p panthera-crypto --env-file /opt/panthera-crypto/.env -f infra/docker-compose.yml run --rm api python -m cripto_api.contas criar --organizacao "Acme" --email pessoa@exemplo.test --nome "Pessoa"
```

## Ambiente de teste

Em regtest, com um nó de verdade e um banco de teste criado do zero a cada rodada.

```bash
sudo bash infra/subir.sh --rede regtest
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
sudo sh -c 'set -a; . /opt/panthera-crypto/.env; set +a; .venv/bin/python -m pytest testes'
```

Para ver a tela com dados de exemplo (o acesso fica em `/opt/panthera-crypto/demonstracao.txt`):

```bash
sudo docker compose -p panthera-crypto --env-file /opt/panthera-crypto/.env -f infra/docker-compose.yml run --rm -T -e CRIPTO_DEMONSTRACAO=- api python -m cripto_api.demonstracao | sudo install -m 600 /dev/stdin /opt/panthera-crypto/demonstracao.txt
```

A console fica em `http://127.0.0.1:8740`.

## Documentos

1. [Arquitetura](docs/arquitetura.md): o caminho de uma transação, por que assim e onde aperta primeiro
2. [Alertas](docs/alertas.md): regras, canais e o formato do webhook
3. [Ameaças](docs/ameacas.md): o que de fato rouba ou faz perder cripto, e qual controle responde a cada coisa
4. [Custódia](docs/custodia.md): carteiras de hardware e de software, multisig, recuperação com prazo, MPC, backup da seed e chaves de servidor
5. [Monitoramento](docs/monitoramento.md): levantamento de nós, explorers e monitores open source, em Bitcoin e em redes EVM
6. [Contratos e DeFi](docs/contratos-e-defi.md): análise de contratos, simulação antes de assinar e revogação de aprovações
7. [Inteligência e rastreio](docs/inteligencia.md): listas de sanções e de golpes, análise de fluxo e MISP
8. [Descartados](docs/descartados.md): projetos conhecidos que ficaram de fora por licença ou por estarem parados
9. [Padrão da console](web/DESIGN.md)

O levantamento de projetos foi conferido em 3 de novembro de 2026 pela API do GitHub: licença, último commit e se o repositório está arquivado. Isso confirma que o projeto existe, está ativo e é aberto, não que é seguro.

Nada aqui é recomendação de investimento. A maior parte das perdas vem de seed mal guardada, de assinar transação sem entender e de aprovação esquecida. Em cadeia pública não há estorno: proteger vem antes de monitorar.

## Licença

[AGPL-3.0](LICENSE). A fonte da assinatura, Mr De Haviland, é distribuída sob a [SIL Open Font License](api/cripto_api/estatico/fontes/OFL-MrDeHaviland.txt).
