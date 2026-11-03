# Integração com o SOC

Como os eventos de cripto entram no Wazuh e no MISP que o ecossistema Panthera já usa. Nada disso foi testado ainda: é o desenho para a primeira fatia.

## Caminho

```
Bitcoin Core (ZMQ / walletnotify) ─┐
mempool (WebSocket)               ─┼─> coletor Panthera Crypto ─> arquivo JSON ─> agente Wazuh ─> regras ─> alerta
OpenZeppelin Monitor (webhook)    ─┘          │
                                              └─> consulta ao MISP (endereço em lista?)
```

O coletor junta as fontes, normaliza para um formato único, consulta o MISP pelos endereços de origem e de destino e grava uma linha JSON por evento. O agente Wazuh lê o arquivo. Assim o Wazuh não precisa saber de blockchain e o coletor não precisa saber de regra de alerta.

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

## Agente Wazuh

```xml
<localfile>
  <log_format>json</log_format>
  <location>/var/log/panthera-crypto/eventos.json</location>
</localfile>
```

## Regras

```xml
<group name="panthera_crypto,">
  <rule id="100700" level="3">
    <decoded_as>json</decoded_as>
    <field name="origem">panthera-crypto</field>
    <description>Panthera Crypto: evento</description>
  </rule>

  <rule id="100701" level="5">
    <if_sid>100700</if_sid>
    <field name="evento">entrada</field>
    <description>Entrada de $(valor) $(ativo) na carteira $(carteira)</description>
  </rule>

  <rule id="100702" level="8">
    <if_sid>100700</if_sid>
    <field name="evento">saida</field>
    <description>Saída de $(valor) $(ativo) da carteira $(carteira)</description>
  </rule>

  <rule id="100703" level="12">
    <if_sid>100702</if_sid>
    <field name="para_conhecido">false</field>
    <description>Saída da carteira $(carteira) para endereço fora da agenda</description>
  </rule>

  <rule id="100704" level="15">
    <if_sid>100700</if_sid>
    <field name="para_em_lista">\.+</field>
    <description>Movimento envolvendo endereço da lista $(para_em_lista)</description>
  </rule>

  <rule id="100705" level="12">
    <if_sid>100700</if_sid>
    <field name="evento">aprovacao_ilimitada</field>
    <description>Aprovação ilimitada dada pela carteira $(carteira)</description>
  </rule>

  <rule id="100706" level="10">
    <if_sid>100700</if_sid>
    <field name="evento">valor_zero_suspeito</field>
    <description>Possível envenenamento de endereço na carteira $(carteira)</description>
  </rule>
</group>
```

Os números de regra e o caminho do arquivo são provisórios. Antes de usar, conferir a faixa livre de IDs no Panthera Roar.

## Cuidados

- O coletor só tem chaves públicas e descritores só leitura. Nunca chave privada.
- Descritor e xpub revelam todo o histórico da carteira. Tratar como dado sensível: guardar cifrado e restringir por organização, como o Roar já faz com os demais dados.
- O alerta de saída para fora da agenda tem que chegar no estado `mempool`, não só depois de confirmado.
