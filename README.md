## Estratégia de Branches

O projeto utiliza uma estratégia de branches para organizar o
desenvolvimento e evitar alterações diretas na branch principal.

### Branches principais

- `main` → versão estável do projeto
- `develop` → integração das funcionalidades em desenvolvimento

### Branches de trabalho

As branches de trabalho devem seguir os seguintes padrões:

- `feature/*` → novas funcionalidades
- `fix/*` → correções de bugs
- `refactor/*` → refatorações
- `test/*` → criação ou alteração de testes
- `devops/*` → infraestrutura e automações
- `docs/*` → documentação

### Exemplos

```text
feature/FE01-cardapio
feature/FE02-carrinho
fix/FE03-calculo-total
refactor/FE04-componente-cardapio
test/FE05-testes-carrinho
devops/DO01-git
docs/README

```

## CI e migrations

O job de CI usa `DATABASE_URL` para os testes e `MIGRATION_DATABASE_URL` para
executar `alembic upgrade head`. Configure `MIGRATION_DATABASE_URL` nos secrets
ou variables do ambiente do GitHub com uma conexão de usuário proprietário do
banco/schema, ou com permissão de criação no schema `public`.

Para PostgreSQL, o usuário de migrations precisa, no mínimo, de acesso ao
schema e permissão para criar a tabela `alembic_version`:

```sql
GRANT USAGE, CREATE ON SCHEMA public TO usuario_migrations;
```

As migrations também podem alterar tabelas existentes; por isso, em produção,
prefira uma conexão de owner/migration role em `MIGRATION_DATABASE_URL`.
