# Arquitetura

O desenho parte de uma regra: o custo de acompanhar não pode crescer com o número de endereços. Uma organização com dez carteiras e uma plataforma com um milhão de carteiras de clientes usam o mesmo caminho.

## Caminho de uma transação

```
                 ZMQ (rawtx, hashblock)            consulta em lote
Bitcoin Core ───────────────────────────▶ ingestor ──────────────────▶ Postgres
 (nó próprio)        RPC (blocos, origem)   │  uma cópia ativa por rede      │
                                            ▼                                │
                                     fila_transacoes                         │
                                            │  FOR UPDATE SKIP LOCKED        │
                                            ▼                                │
                                  avaliador (N cópias) ── regras ── alertas ─┤
                                            │                                │
                                            ▼                                │
                                       fila_envios                           │
                                            │                                │
                                            ▼                                │
                                  avisador (N cópias) ── ntfy, webhook       │
                                                                             │
                     API (N processos, sem estado) ◀── console ◀─────────────┘
```

1. **Ingestor.** Recebe cada transação da mempool e cada bloco pelo ZMQ do nó. Junta as transações em lotes de até 500 ou meio segundo e casa todas as saídas de uma vez com a tabela de endereços acompanhados (`endereco = ANY(...)`), de todas as organizações. As entradas são reconhecidas pela tabela `saidas`, que guarda as saídas não gastas das carteiras acompanhadas: um gasto é reconhecido sem perguntar a ninguém. Só quando uma transação paga uma carteira acompanhada o ingestor pergunta ao nó de onde veio o dinheiro, porque a origem importa para a lista de sanções e para o envenenamento de endereço. Uma cópia por rede fica ativa, presa numa trava do Postgres; as outras esperam e assumem se ela cair.
2. **Avaliador.** Pega lotes da fila com `FOR UPDATE SKIP LOCKED`, transforma cada transação no movimento de cada carteira que ela toca, já descontando o troco, e aplica as regras. A mesma transação chega da mempool, do bloco e às vezes do ponto de partida: o movimento é gravado uma vez e depois só confirma, nunca volta. Item com erro volta para a fila cada vez mais espaçado, sem travar os outros.
3. **Avisador.** Entrega os alertas nos canais de cada organização, com nova tentativa quando o canal está fora do ar.
4. **Tarefas.** O ponto de partida de carteira nova sai do próprio nó, com `scantxoutset`: uma leitura do conjunto de saídas não gastas serve para até 50 carteiras de uma vez. Endereço usado perto do fim abre folga de mais 20.
5. **Manutenção.** Atualiza a lista de sanções uma vez por dia e limpa sessões vencidas.
6. **API.** Sem estado. Cada requisição abre uma transação presa à organização da sessão, e o próprio Postgres (RLS) só devolve linhas dessa organização.

## Por que assim

| Decisão | Motivo |
|---|---|
| Fluxo do nó em vez de consultar endereço por endereço | Consultar um explorer por endereço cresce com o número de endereços, leva bloqueio (429) e entrega a lista de endereços a terceiros. O fluxo custa o volume da rede, que é fixo: poucas transações por segundo |
| Nó próprio também para o ponto de partida | Sem Esplora nem explorer de terceiros. Uma leitura do conjunto de saídas atende muitas carteiras |
| Filas no Postgres com `SKIP LOCKED` | Escala na horizontal sem um serviço de filas a mais para operar. Se um dia o volume pedir, a troca por um corretor de mensagens fica restrita às filas |
| Tabelas grandes particionadas por hash | Endereços e saídas por endereço e transação, que é como o ingestor procura; movimentos e alertas por organização, que é como a tela lê |
| Isolamento por organização no banco (RLS) | Um erro na API não vaza dado de outra organização: o banco recusa. Mesmo padrão do Panthera Roar |
| Um papel de banco por função | A API não lê fila nem escreve movimento; os serviços não passam pelo isolamento porque atravessam organizações |
| Paginação por cursor e buscas exatas | Nenhuma tela faz `OFFSET` nem `LIKE` em tabela grande. Busca é por transação exata, endereço exato (índice GIN em `contrapartes`) ou título |
| Valores em satoshis, inteiros | Dinheiro não passa por ponto flutuante |

## Onde aperta primeiro

- **O nó.** Um Bitcoin Core com `txindex` precisa de cerca de 800 GB em SSD na rede principal. É o único componente que não se multiplica: para alta disponibilidade, um segundo nó e um segundo ingestor na espera.
- **`scantxoutset`.** Leva de um a três minutos por leitura na rede principal, e o nó só faz uma por vez. Em lote de 50, isso dá algo como mil carteiras novas por hora. Para cadastro em massa, aumentar o lote.
- **Lista de saídas.** Cresce com o número de saídas não gastas acompanhadas, não com o histórico. Saída gasta pode ser apagada depois de alguns meses sem perder nada.

## O que fica para depois

- Redes EVM, com o mesmo desenho: o fluxo de blocos de um nó próprio, casado em lote com endereços e contratos acompanhados.
- Tela de administração da plataforma, criando organizações e acessos, como no Roar. Hoje é por linha de comando.
- Segundo fator no acesso, como no Roar.
- Retenção configurável de movimentos e alertas.
