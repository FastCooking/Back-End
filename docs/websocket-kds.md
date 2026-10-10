# WebSocket do KDS

## Conexao e autenticacao

Conecte em `ws://<host>/pedidos/ws` (ou `wss://` em HTTPS). Depois do handshake,
envie em ate 5 segundos o primeiro frame JSON:

```json
{"type":"authenticate","token":"<JWT>"}
```

O JWT vai no primeiro frame, nao na URL. O backend aceita os perfis ativos
`Cozinheiro` e `Garcom`, vinculando a conexao ao restaurante do usuario. Perfil
nao suportado fecha com codigo `4403`; token ausente, invalido ou expirado fecha
com `4401`.

Conexoes de cozinheiros recebem eventos de todos os pedidos ativos do seu
restaurante. Garcons recebem eventos apenas de pedidos cujo `idGarcom` seja o
proprio usuario. A conexao de cliente final nao esta habilitada: o backend nao
possui identidade ou mecanismo de autenticacao para esse publico, e nao libera
acesso por conhecimento do ID do pedido.

## Eventos

Cada mensagem inclui `type`, `eventId`, `sequence` (contador da conexao),
`queueVersion` (versao global em memoria), `occurredAt` e `restaurantId`.

- `queue.snapshot`: enviado logo apos autenticar e novamente em toda conexao
  nova; `data.items` contem o estado atual autorizado.
- `item.created`: publicado para item criado com status `Pendente`.
- `item.status_changed`: publicado depois de o status ser persistido.
- `queue.updated`: acompanha cada evento de item com `refreshRequired: true`.

## Operacoes que publicam eventos

- `POST /pedidos`: garcom autenticado cria um pedido com os itens pendentes.
- `POST /pedidos/{idPedido}/itens`: garcom autenticado adiciona itens somente
  ao pedido atribuido a ele.
- `PATCH /pedidos/itens/{idItemPedido}/status`: cozinheiro autenticado avanca
  um item apenas para o proximo estado permitido.
- `GET /pedidos/kds/fila`: cozinheiro recebe o estado do restaurante; garcom
  recebe apenas os pedidos atribuidos a ele.

Exemplo de notificacao:

```json
{
  "type":"item.status_changed",
  "eventId":"<uuid>",
  "sequence":12,
  "queueVersion":7,
  "occurredAt":"<timestamp ISO-8601>",
  "restaurantId":4,
  "item":{"idItemPedido":31,"idPedido":18,"status":"Pronto"}
}
```

Ao receber `queue.updated`, o cliente pode sincronizar por `GET
/pedidos/kds/fila`, autenticado com Bearer JWT. Em uma reconexao, autentique de
novo e trate o `queue.snapshot` inicial como a fonte autoritativa; WebSocket nao
garante replay de mensagens perdidas. `eventId` pode ser usado para deduplicar
eventos; `sequence` ordena a transmissao daquela conexao e `queueVersion` pode
indicar uma mudanca global que justifique nova consulta. Como garçons recebem
somente pedidos atribuidos, lacunas em `queueVersion` podem ser atualizacoes de
outros pedidos, nao perda de mensagem.

## Reconexao no cliente

O frontend nao esta neste workspace. O cliente deve fechar a conexao anterior,
reconectar com backoff exponencial limitado (por exemplo, de 0,5 ate 30
segundos), reenviar o frame de autenticacao e substituir o estado local pelo
`queue.snapshot` recebido. Se detectar uma lacuna de `sequence`, deve consultar
`GET /pedidos/kds/fila`.

## Limitacoes atuais

RF18 ainda nao esta implementada. O snapshot retorna o estado ativo sem impor
uma ordenacao de prioridade; `priorityApplied` e `false`. O evento de fila
apenas solicita sincronizacao e nao inventa regra de prioridade.

O gerenciador de conexoes e o contador de sequencia vivem na memoria de um unico
processo. A configuracao Docker atual executa uma instancia Uvicorn; se a
implantacao passar a usar varios processos ou instancias, sera necessario um
canal pub/sub compartilhado. A entrega nao e duravel; o snapshot serve para
reconciliar o estado depois de uma queda.