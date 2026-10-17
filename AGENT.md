# 🤖 AGENT.md — Guia de Engenharia e Contexto para Agentes de IA

> **Atenção para Agentes de IA e Desenvolvedores:**  
> Este documento é a **fonte primária de contexto, regras de negócio e arquitetura** do projeto **FastCooking (Back-End)**.  
> Sempre que você (IA ou engenheiro humano) for realizar alterações, refatorações, criação de novas rotas ou manutenção neste repositório, **leia atentamente todas as diretrizes deste arquivo antes de executar qualquer código**.

---

## 1. Visão Geral do FastCooking

O **FastCooking** é uma plataforma distribuída de gerenciamento e automação de pedidos para restaurantes e redes de alimentação. O sistema foi projetado para operar com alta concorrência em horário de pico, reduzindo drasticamente atrasos, erros humanos e retrabalho entre salão, cozinha e gestão.

### 1.1 Objetivo do Sistema
- **Eliminar gargalos de atendimento:** agilizar a transmissão dos pedidos desde a mesa até a praça de preparo.
- **Acabar com erros de comanda:** eliminar confusões causadas por anotações manuais, caligrafia ilegível e falhas de comunicação verbal entre garçons e cozinheiros.
- **Harmonizar a comunicação Cozinha ⇄ Salão:** notificar garçons no instante exato em que um prato fica pronto para entrega imediata ao cliente.
- **Oferecer Autoatendimento Digital:** permitir que o cliente final visualize o cardápio, faça pedidos e acompanhe o status em tempo real pelo seu próprio smartphone escaneando o QR Code da mesa.

---

## 2. O Diferencial: Método KDS de Gerenciamento Dinâmico de Pedidos

O principal coração operacional do FastCooking é o **Kitchen Display System (KDS)** dinâmico, baseado em priorização algorítmica e sincronização em tempo real via WebSockets.

### 2.1 Algoritmo de Prioridade Dinâmica (`src/services/PrioridadeKDS.py`)
Diferente de filas FIFO tradicionais (que geram atrasos em bebidas e pratos rápidos quando a cozinha está cheia de pratos demorados), o FastCooking aplica uma fórmula de pontuação dinâmica:

$$\text{Pontuação} = \text{Peso}_{\text{categoria}} \times \left(1 + \frac{\text{Tempo de Espera (minutos)}}{\text{Limite}_{\text{categoria}}}\right)$$

- **Parâmetros por Categoria:**
  - **Bebida:** Peso `2.0` | Limite de tolerância: `3 minutos` *(alta urgência imediata para refrescar o cliente)*.
  - **Entrada:** Peso `1.5` | Limite de tolerância: `10 minutos`.
  - **Prato Principal:** Peso `1.0` | Limite de tolerância: `20 minutos`.
  - **Sobremesa:** Peso `0.5` | Limite de tolerância: `5 minutos` *(geralmente retida até o fim da refeição)*.
  - **Fallback / Categoria Neutra:** Peso `1.0` | Limite de tolerância: `20 minutos`.
- **Normalização Resiliente:** Tratamento via normalização Unicode NFKD para remover acentos, conversão para minúsculas e mapeamento de plurais (ex.: `"Sobremesas"` $\to$ `"sobremesa"`).
- **Ordenação da Fila de Preparo:** Na rota `GET /pedidos/kds/fila` e no snapshot WebSocket, os itens pendentes/em preparo são ordenados por:
  1. Maior pontuação dinâmica decrescente (`-item["pontuacao"]`);
  2. Menor data de criação (`item["dataCriacao"]` ASC);
  3. Desempate estável pelo UUID do item (`item["idItemPedido"]`).

### 2.2 Controle Inteligente de Sobremesas
- Ao criar um pedido que contenha sobremesas, o campo `liberadoParaPreparo` é inicializado como `False`.
- As sobremesas **não aparecem** na fila da cozinha até que o garçom ou cliente acione a liberação manual via `PATCH /pedidos/itens/{idItemPedido}/liberar-sobremesa`.
- Isso evita que sobremesas (como sorvetes ou petit gâteau) sejam preparadas e derretam enquanto os clientes ainda consomem a refeição principal.

### 2.3 Máquina de Estados de Itens e Pedidos
O fluxo do item é linear e protegido contra saltos de estado inválidos:

```
[Pendente] ──> [Em preparo] ──> [Pronto] ──> [Entregue]
    │
    └──> [Cancelado] (Apenas permitido enquanto Pendente)
```

- **Transições Inválidas:** Retornam HTTP `409 Conflict`. Exemplo: Não é possível passar direto de `Pendente` para `Pronto`, nem cancelar item que já esteja `Em preparo` ou `Pronto`.
- **Status do Pedido (Comanda):** `Aberto` $\to$ `Fechado` (ao registrar pagamento total) ou `Cancelado`.
- **Status Agregado de Rastreio (Tracking do Cliente):**
  - `PENDING`: Todos os itens ainda pendentes.
  - `IN_PREPARATION`: Ao menos um item em preparo.
  - `READY`: Todos os itens prontos ou entregues (ao menos um pronto para retirada).
  - `DELIVERED`: Todos os itens entregues.
  - `CANCELLED`: Todos os itens cancelados.

### 2.4 Eventos em Tempo Real (`RealtimeHub` em `src/core/realtime.py`)
- O servidor mantém um hub em memória com conexões de dois tipos:
  1. **Staff WebSocket (`/pedidos/kds/ws` ou `/pedidos/ws`):** Cozinheiros e Garçons autenticados via token JWT enviado no primeiro frame:
     ```json
     {"type": "authenticate", "token": "<JWT_DO_USUARIO>"}
     ```
  2. **Customer Tracking WebSocket (`/ws/tracking/{idPedido}`):** Conexão pública para o cliente final acompanhar o progresso dos seus itens na tela.
- **Regra de Negócio RF06 (Notificação de Pratos Prontos):**
  - Quando um item transiciona para o status `Pronto`, o evento é disparado via broadcast para **TODOS** os garçons conectados do restaurante, garantindo que qualquer garçom livre possa levar o prato quente imediatamente à mesa.
  - Para outros status, notificações parciais são filtradas apenas para o garçom responsável pelo pedido.
- **Eventos Transmitidos:**
  - `queue.snapshot`: Estado completo autorizado enviado na conexão.
  - `item.created`: Novo item inserido.
  - `item.status_changed`: Avanço de status do item.
  - `item.dessert_released`: Liberação de preparo de sobremesa.
  - `mesa.garcom_chamado`: Notificação de cliente chamando garçom na mesa.
  - `mesa.garcom_atendido`: Confirmação de atendimento do chamado.
  - `order.closed`: Pedido pago e comanda encerrada.

---

## 3. Módulos do Sistema e Controle de Acesso (RBAC)

O sistema é estritamente **multi-tenant** isolado por restaurante (`idRestaurante`) com quatro papéis (funções) de usuário:

| Papel | Escopo | Permissões Principais |
| :--- | :--- | :--- |
| **Adm** | Global / Plataforma | Criação e gestão de estabelecimentos (`/restaurantes`), onboarding completo (`/restaurantes/com-usuario`), ativação/desativação, criação e edição de qualquer usuário. |
| **Gerente** | Restaurante Local | Gestão completa do cardápio (`/cardapio`), insumos/estoque (`/insumos`), fichas técnicas (`/fichas-tecnica`), mesas e QR Codes (`/mesas`), consulta de histórico de vendas, e gestão de equipe local restrita a `Garcom` e `Cozinheiro`. |
| **Garcom** | Restaurante Local | Abertura e acompanhamento de comandas (`/pedidos`), adição de novos itens na mesa, liberação de sobremesas, cancelamento de itens pendentes, fechamento de contas com registro de pagamento (`/pedidos/{idPedido}/pagamento`), atendimento de chamados de mesa. |
| **Cozinheiro** | Restaurante Local | Painel KDS em tempo real, visualização da fila com prioridade dinâmica, alteração sequencial de status dos itens (`Pendente` $\to$ `Em preparo` $\to$ `Pronto`), consulta de fichas técnicas e estoque. |
| **Cliente** *(Público)* | Mesa Específica | Escaneamento de QR Code, autoatendimento, abertura de sessão de mesa, lançamento de pedidos diretos para a cozinha, chamada de garçom e tracking em tempo real. |

---

## 4. Arquitetura de Software e Estrutura de Diretórios

O projeto segue a arquitetura em camadas **Controller-Service-Repository/Model** com FastAPI e SQLAlchemy:

```
Back-End/
├── alembic/                      # Migrações do banco de dados (schema versionado)
│   ├── versions/
│   │   ├── 001_initial_uuid_schema.py
│   │   ├── 002_pedido_sessao_kds.py
│   │   ├── cf5c21fd3dca_criar_tabela_sessao_atendimento.py
│   │   └── 003_prioridade_dinamica_kds.py
│   └── env.py
├── docs/                         # Documentações auxiliares de engenharia
│   └── websocket-kds.md          # Especificação de frames e eventos WebSocket
├── src/
│   ├── app.py                    # Ponto de entrada FastAPI, middlewares, CORS, lifespan
│   ├── controllers/              # Rotas REST e endpoints WebSockets
│   │   ├── AuthController.py         # Login JWT e Refresh Token
│   │   ├── CardapioController.py     # Itens de cardápio e upload de imagens
│   │   ├── EstoqueController.py      # Gestão de insumos (/insumos)
│   │   ├── FichaTecnicaController.py # Fichas técnicas com composição de insumos
│   │   ├── MesaController.py         # Mesas, QR Code PNG, sessões e chamados
│   │   ├── PedidoController.py       # Pedidos, KDS, pagamentos e WebSockets
│   │   ├── RestauranteController.py  # Gestão de restaurantes multi-tenant
│   │   └── UsuarioController.py      # Gestão de funcionários e RBAC
│   ├── core/                     # Núcleo da aplicação
│   │   ├── bootstrap.py              # Inicialização idempotente do usuário administrador
│   │   ├── realtime.py               # Hub de WebSockets, multiplexação e versionamento
│   │   ├── security.py               # JWT HS256, hash de senha, injeções de RBAC
│   │   └── websocket_manager.py      # Gerenciador complementar de conexões
│   ├── database/                 # Conexão e scripts SQL
│   │   ├── connection.py             # Engine, Base declarativa e get_db()
│   │   └── scripts/
│   │       ├── database.sql          # Script DDL PostgreSQL com índices
│   │       └── mockData.sql          # Dados de exemplo para desenvolvimento
│   ├── models/                   # Entidades declarativas SQLAlchemy
│   │   ├── Cardapio.py
│   │   ├── Estoque.py
│   │   ├── FichaTecnica.py
│   │   ├── ItemPedido.py
│   │   ├── Mesa.py
│   │   ├── Pagamento.py
│   │   ├── Pedido.py
│   │   ├── Restaurante.py
│   │   ├── Sessao.py
│   │   └── Usuario.py
│   ├── repositories/             # Camada de persistência especializada
│   │   ├── EstoqueRepository.py
│   │   └── FichaTecnicaRepository.py
│   ├── schemas/                  # DTOs e validações com Pydantic v2
│   │   ├── AuthSchema.py
│   │   ├── CardapioSchema.py
│   │   ├── EstoqueSchema.py
│   │   ├── FichaTecnicaSchema.py
│   │   ├── MesaSchema.py
│   │   ├── PedidoSchema.py
│   │   ├── RestauranteSchema.py
│   │   └── UsuarioSchema.py
│   └── services/                 # Regras de negócio e lógica de aplicação
│       ├── AuthService.py
│       ├── CardapioService.py
│       ├── EstoqueService.py
│       ├── FichaTecnicaService.py
│       ├── PedidoService.py
│       ├── PrioridadeKDS.py
│       ├── QrCodeService.py
│       ├── RestauranteService.py
│       ├── SessaoService.py
│       └── UsuarioService.py
├── tests/                        # Suíte de testes automatizados com Pytest
│   ├── conftest.py               # Setup com SQLite em memória (:memory:) e fixtures
│   ├── test_abertura_mesa.py
│   ├── test_auth_refresh.py
│   ├── test_bootstrap_admin.py
│   ├── test_cancelamento_item.py
│   ├── test_cardapio_imagem.py
│   ├── test_chamar_garcom.py
│   ├── test_estoque.py
│   ├── test_pedidos_cliente.py
│   ├── test_prioridade_kds.py
│   ├── test_realtime.py
│   ├── test_restaurantes.py
│   ├── test_tracking_websocket.py
│   └── test_usuarios.py
├── populate_kfc.py               # Script para semear restaurante fictício completo
├── Dockerfile                    # Container Docker do Back-End
├── requirements.txt              # Dependências Python
└── alembic.ini                   # Configurações do Alembic
```

---

## 5. Modelagem de Dados e Relacionamentos

Todas as chaves primárias são do tipo **UUIDv4**. A aplicação adota as seguintes regras de integridade:

1. **`Restaurante`**: Entidade raiz do tenant.
   - Campos: `idRestaurante`, `nome`, `cnpj` (único), `telefone`, `email` (único), `cep`, `status`.
   - Remoção de restaurante propaga em cascata (`CASCADE`) para usuários, mesas, cardápios, insumos e pedidos vinculados.
2. **`Usuarios`**: Funcionários do sistema.
   - Campos: `idUsuario`, `idRestaurante`, `nome`, `cpf` (único), `email` (único), `senha` (hash bcrypt), `funcao` (`Adm`, `Gerente`, `Garcom`, `Cozinheiro`), `status`, `tentativasFalhas`, `bloqueadoAte`.
   - **Exclusão Lógica LGPD:** Em vez de exclusão física que quebraria relacionamentos históricos de pedidos, o método `usuario.delete()` anonimiza nome, CPF e e-mail com tokens pseudo-aleatórios e define `status = False`.
3. **`Mesa`**: Mesas do salão.
   - Constraint de unicidade: `UNIQUE (idRestaurante, numero)`.
   - Status: `'Disponivel'`, `'Indisponivel'`.
4. **`Sessao`**: Sessões de ocupação de mesa com expiração automática após 10 minutos de inatividade sem pedidos ativos.
   - Constraint: apenas uma sessão ativa permitida por mesa simultaneamente (`uq_sessao_ativa_por_mesa`).
5. **`Cardapio`**: Pratos, bebidas e sobremesas.
   - Relacionado ao `Restaurante`. Possui categoria, preço, descrição, status e URL da imagem comprimida salva em `/uploads/cardapio/`.
6. **`Estoque`**: Insumos controlados para produção.
   - `quantidadeEstoque`, `quantidadeMinima`, `unidadeMedida` (kg, g, l, un).
7. **`FichaTecnica`**: Associação $N:M$ entre `Cardapio` e `Estoque`.
   - Define a `quantidadeNecessaria` de cada insumo para produzir 1 unidade do item do cardápio.
8. **`Pedido`**: Comanda de consumo vinculada à mesa.
   - Reutilização inteligente: quando um novo cliente ou novo garçom envia itens para a mesma mesa com pedido ainda não encerrado, os novos itens são agregados à comanda já existente.
9. **`ItemPedido`**: Itens individuais da comanda.
   - Campos essenciais para KDS: `status` (`Pendente`, `Em preparo`, `Pronto`, `Entregue`, `Cancelado`), `categoria`, `prioridade`, `liberadoParaPreparo` (booleano), `dataCriacao` (timestamp UTC com timezone).
10. **`Pagamento`**: Transação financeira de encerramento da comanda.
    - `formaPagamento`: `Dinheiro`, `Credito`, `Debito`, `PIX`.

---

## 6. Endpoints da API (Visão de Referência Rápida)

### 6.1 Autenticação (`/auth`)
- `POST /auth/login`: Autenticação por e-mail e senha. Retorna `access_token` (60 min) e `refresh_token` (7 dias).
- `POST /auth/refresh`: Renovação segura do token de acesso via refresh token.

### 6.2 Restaurantes (`/restaurantes`)
- `POST /restaurantes/com-usuario`: Criação atômica de restaurante + usuário gerente inicial (apenas `Adm`).
- `POST /restaurantes`: Cadastro de restaurante (`Adm`).
- `GET /restaurantes`: Listagem com busca, filtros e paginação (`Adm`, `Gerente`).
- `GET /restaurantes/{id}`: Detalhes do restaurante.
- `GET /restaurantes/{id}/publico`: Consulta pública de nome e telefone (para páginas de cardápio).
- `PUT / PATCH /restaurantes/{id}`: Atualização de cadastro (`Adm`).
- `PATCH /restaurantes/{id}/status`: Ativação/Desativação (`Adm`).

### 6.3 Usuários (`/usuarios`)
- `POST /usuarios`: Cadastro de funcionários com validação de hierarquia (Gerente só pode criar Garçom e Cozinheiro).
- `GET /usuarios`: Listagem com filtro de restaurante e função.
- `GET /usuarios/{id}`: Dados do usuário.
- `PUT / PATCH /usuarios/{id}`: Edição de dados respeitando hierarquia.
- `PATCH /usuarios/{id}/status`: Ativar/Desativar funcionário.
- `DELETE /usuarios/{id}`: Anonimização LGPD e desativação.

### 6.4 Mesas e Sessões (`/mesas`)
- `GET /mesas`: Listagem de mesas do restaurante.
- `POST /mesas`: Cadastro de nova mesa (`Adm`, `Gerente`).
- `GET /mesas/{idMesa}/qrcode`: Retorna streaming de imagem PNG com o QR Code para o autoatendimento.
- `POST /mesas/{idMesa}/abrir`: Inicia ou reutiliza sessão ativa de atendimento para a mesa.
- `POST /mesas/sessoes/expirar-inativas`: Varredura de sessões inativas.
- `POST /mesas/{idMesa}/chamar-garcom`: Cliente solicita garçom (dispara WebSockets no salão).
- `POST /mesas/{idMesa}/atender-chamado`: Garçom confirma atendimento do chamado.
- `GET /mesas/chamados/ativos`: Lista chamados pendentes de atendimento.
- `GET /mesas/{idMesa}/pedido-ativo`: Obtém a comanda ativa atual da mesa.

### 6.5 Cardápio (`/cardapio`)
- `POST /cardapio`: Criação de item (suporta JSON ou `multipart/form-data` com upload automático e compressão de imagem para JPEG/85% via Pillow).
- `GET /cardapio`: Listagem de itens ativos do restaurante.
- `GET /cardapio/{id}`: Consulta detalhada.
- `PUT / POST /cardapio/{id}`: Atualização de dados e troca de imagem (remove arquivos órfãos anteriores).
- `DELETE /cardapio/{id}`: Exclusão lógica (desativação) e limpeza de fichas técnicas.

### 6.6 Estoque e Insumos (`/insumos`)
- `POST /insumos`: Cadastro de matéria-prima.
- `GET /insumos`: Listagem de estoque do restaurante.
- `GET /insumos/{id}`: Consulta de insumo.
- `PUT /insumos/{id}`: Atualização de quantidades e limites mínimos.
- `DELETE /insumos/{id}`: Exclusão de insumo.

### 6.7 Fichas Técnicas (`/fichas-tecnica`)
- `POST /fichas-tecnica`: Vinculação de ingredientes a um item do cardápio.
- `PUT /fichas-tecnica/cardapio/{idCardapio}`: Atualização atômica dos insumos do prato.
- `GET /fichas-tecnica/cardapio/{idCardapio}/completa`: Ficha técnica completa com nomes e unidades de medida.

### 6.8 Pedidos e KDS (`/pedidos`)
- `POST /pedidos`: Criação de novo pedido ou acoplamento a comanda aberta na mesa.
- `POST /pedidos/{idPedido}/itens`: Adição de novos itens à comanda.
- `GET /pedidos`: Listagem de pedidos com filtros (`status`, `tipo=ativos`, `tipo=historico`).
- `GET /pedidos/{idPedido}`: Detalhes da comanda com itens e totais calculados.
- `GET /pedidos/{idPedido}/tracking`: Rastreio em formato simplificado para o cliente.
- `GET /pedidos/kds/fila`: Snapshot da fila de preparo com pontuação dinâmica calculada.
- `PATCH /pedidos/itens/{idItemPedido}/status`: Cozinheiro avança status do item (`Pendente` $\to$ `Em preparo` $\to$ `Pronto`).
- `PATCH /pedidos/itens/{idItemPedido}/liberar-sobremesa`: Garçom libera sobremesa para preparo imediato.
- `PATCH /pedidos/itens/{idItemPedido}/cancelar`: Cancelamento de item pendente.
- `POST /pedidos/{idPedido}/pagamento`: Registro de pagamento (Dinheiro, PIX, Cartão), encerramento do pedido e liberação da mesa.
- `WebSocket /pedidos/kds/ws` ou `/pedidos/ws`: Conexão em tempo real da equipe (KDS e Salão).
- `WebSocket /ws/tracking/{idPedido}`: Conexão em tempo real para acompanhamento do cliente.

---

## 7. Instruções e Regras Mandatórias para Agentes de IA

Ao desenvolver código neste projeto, **siga estritamente as regras abaixo**:

### 7.1 Isolamento Multi-Tenant e Segurança
- **Nunca exponha ou misture dados entre restaurantes diferentes.** Toda busca, filtro ou mutação em mesas, pedidos, cardápio ou usuários deve validar ou injetar `idRestaurante`.
- **Respeite o RBAC:** Use a dependência `Depends(exigir_funcao(...))` em rotas protegidas. Não remova restrições para contornar erros sem justificativa explícita.
- **Hierarquia de Gerente:** Um `Gerente` só tem autoridade sobre seu próprio restaurante e só pode gerenciar usuários de funções inferiores (`Garcom`, `Cozinheiro`). Jamais permita que um Gerente crie ou altere outro Gerente ou um Administrador (`Adm`).

### 7.2 Integridade do KDS e Tempo Real
- **Não altere os cálculos de pontuação de `PrioridadeKDS.py` sem testes:** Mudanças na fórmula matemática impactam a prioridade de todas as praças da cozinha.
- **Mantenha a linearidade da máquina de estados:** Itens só podem avançar um estágio por vez (`Pendente` $\to$ `Em preparo` $\to$ `Pronto` $\to$ `Entregue`). O método `update_item_status` deve lançar `409 Conflict` se houver tentativa de salto.
- **Preserve a regra RF06:** Pratos com status `Pronto` devem notificar **todos** os garçons conectados do restaurante no WebSocket (`realtime_hub.publish_item_event`).
- **Não bloqueie o Event Loop:** Todas as publicações de eventos WebSocket devem ser agendadas via `BackgroundTasks` do FastAPI (`background_tasks.add_task(...)`) para não reter a resposta HTTP do cliente.

### 7.3 Qualidade de Código, Banco de Dados e Testes
- **Banco de Dados Oficial:** PostgreSQL em produção com extensões `uuid-ossp` e `pgcrypto`. Todas as migrações devem ser criadas via Alembic (`alembic revision -m "..."`).
- **Suíte de Testes:** Os testes unitários e de integração residem em `tests/` e utilizam banco de dados SQLite em memória (`sqlite:///:memory:`) com isolamento automático por função (`setup_teardown_db`).
- **Garantir Idempotência:** Qualquer alteração no schema ou bootstrap deve ser idempotente (ver `bootstrap.py` como referência).
- **Tipagem e Schemas:** Utilize sempre schemas Pydantic tipados em `src/schemas/` para validar requests e serializar responses.
- **Manipulação de Imagens:** Fotos de cardápio devem ser redimensionadas proporcionalmente (escala 60%, filtro Lanczos, JPEG qualidade 85%) para economizar espaço de armazenamento e tempo de carregamento no celular dos clientes.

---

## 8. Guia Rápido de Comandos e Ambiente

### 8.1 Variáveis de Ambiente (`.env`)
```bash
DATABASE_URL=postgresql://usuario:senha@localhost:5432/fastcooking_db
SERVER_PORT=8000
JWT_SECRET=sua_chave_secreta_jwt_longa_e_segura
BCRYPT_ROUNDS=12
DEFAULT_ADMIN_EMAIL=fastcooking@fastcooking.com.br
DEFAULT_ADMIN_PASSWORD=f4stc0oking
FRONTEND_BASE_URL=https://fastcooking-front-end.vercel.app
```

### 8.2 Execução Local (Python)
```powershell
# Ativar ambiente virtual
cd Back-End

# Instalar dependências
pip install -r requirements.txt

# Executar migrações
alembic upgrade head

# Popular dados de teste (Opcional - KFC Osasco)
python populate_kfc.py

# Iniciar servidor FastAPI com recarregamento dinâmico
python src/app.py
```

### 8.3 Execução via Docker Compose
Na raiz do projeto (`c:\Users\Carlos\Documents\labs\FastCooking`):
```bash
docker-compose up --build
```
- Back-End: `http://localhost:8000` (Docs Swagger em `http://localhost:8000/docs`)
- Front-End: `http://localhost:5173`

