# order_snakbar

Repositorio base de um sistema integrado de gestao para cafeteria, com foco em pedidos por mesa, operacao de cozinha, atendimento e administracao.

No estado atual, o projeto contem apenas a estrutura inicial de diretorios. A especificacao funcional, arquitetural e academica do sistema foi registrada em [DOCUMENTACAO_TECNICO_ACADEMICA.md](DOCUMENTACAO_TECNICO_ACADEMICA.md).

## Estrutura atual

```text
app/
|-- static/
|   |-- css/
|   `-- js/
`-- templates/
```

## Proxima base de implementacao

- Backend em Flask.
- Persistencia em PostgreSQL.
- Autenticacao via JWT.
- Atualizacoes em tempo real com Flask-SocketIO.
- Interfaces web responsivas para mesa, atendimento, cozinha e administracao.

## Situacao do repositorio

Este repositorio agora possui uma base inicial funcional em Flask e dependencias minimas declaradas em `requirements.txt`. A documentacao academica continua sendo a referencia principal para a evolucao incremental das proximas etapas.

## Primeira entrega implementada

Foi adicionada uma base minima executavel em Flask com:

- app factory em `app/__init__.py`;
- configuracao por ambiente em `app/config.py`;
- rota inicial `/`;
- endpoints de status `/health` e `/api/health`;
- entrypoint em `run.py`.

## Autenticacao implementada

Foi adicionado um fluxo inicial de autenticacao com JWT para dois perfis:

- `colaborador`
- `administrador`

Recursos incluidos nesta etapa:

- login via `POST /api/auth/login`;
- consulta do usuario autenticado em `GET /api/auth/me`;
- area protegida do colaborador em `GET /api/colaborador/area`;
- area protegida do administrador em `GET /api/admin/area`;
- tela de login em `/login`;
- paineis iniciais em `/colaborador` e `/admin`.

## Banco de dados e analitica implementados

Foi adicionada uma camada de persistencia profissional com SQLAlchemy, preparada para PostgreSQL e com fallback local em SQLite para desenvolvimento.

Modelos incluidos:

- colaboradores;
- categorias de cardapio;
- produtos;
- mesas;
- pedidos;
- itens de pedido;
- pagamentos.

Recursos incluidos nesta etapa:

- seed automatica e idempotente da base;
- cardapio inicial com 13 produtos;
- 4 opcoes vegan marcadas no catalogo;
- historico de pedidos e pagamentos para analise de dia, semana e mes;
- ranking de produtividade e vendas por colaborador;
- dashboards com dados reais do banco.

## CRUD administrativo de produtos

O painel do administrador agora permite gerir integralmente os produtos do cardapio, incluindo comidas e bebidas.

Recursos incluidos:

- introduzir produtos com categoria, descricao, preco e indicador vegan;
- editar produtos existentes;
- apagar produtos sem historico de vendas;
- desativar produtos com historico, preservando integridade analitica;
- carregar imagens por upload no painel admin;
- gerir estoque atual e limite minimo por produto;
- armazenar a imagem do produto em `app/static/uploads/products/`.

## Paineis administrativos separados

O modulo administrativo foi dividido em paineis especializados:

- `/admin/produtos`: estatisticas de produtos, vendas, giro e estoque;
- `/admin/colaboradores`: produtividade e atividade por colaborador, com filtro dinamico;
- `/admin/catalogo`: CRUD operacional do catalogo com gestao de imagens e estoque.

Os paineis analiticos fazem atualizacao periodica por requisicoes ao backend para manter a leitura proxima do tempo real.

## Painel operacional do colaborador

O painel do colaborador passou a funcionar como ponto inicial de lancamento de pedidos enquanto a app da mesa ainda nao foi implementada.

Recursos incluidos:

- escolha rapida de mesa por botoes numerados;
- selecao de subgrupos do cardapio por categoria;
- adicao direta de produtos ao ticket da mesa;
- criacao automatica de ticket quando a mesa ainda nao possui pedido aberto;
- visualizacao do ticket atual da mesa em tempo real no proprio painel.

## Como executar

1. Ative o ambiente virtual.
2. Instale as dependencias com `pip install -r requirements.txt`.
3. Execute `python run.py`.
4. Abra `http://127.0.0.1:5000` no navegador.
5. Acesse `http://127.0.0.1:5000/login` para testar o login.

## Banco em desenvolvimento

Por padrao, o projeto usa `sqlite:///order_snakbar.db` para desenvolvimento local.
Para producao ou homologacao, defina `DATABASE_URL` apontando para PostgreSQL.

Exemplo:

- `postgresql+psycopg2://usuario:senha@localhost:5432/order_snakbar`

## Credenciais de desenvolvimento

As credenciais iniciais ficam configuradas no arquivo `.env`.

- administrador: `ADMIN_EMAIL` e `ADMIN_PASSWORD`
- colaborador: `COLLABORATOR_EMAIL` e `COLLABORATOR_PASSWORD`

## Endpoints relevantes desta etapa

- `GET /api/catalog/menu`
- `GET /api/admin/catalog/overview`
- `GET /api/admin/categories`
- `GET /api/admin/products`
- `POST /api/admin/products`
- `PUT /api/admin/products/<id>`
- `DELETE /api/admin/products/<id>`
- `GET /api/admin/products/dashboard?period=day|week|month`
- `GET /api/admin/collaborators`
- `GET /api/admin/collaborators/dashboard?period=day|week|month&collaborator_id=<id>`
- `GET /api/admin/analytics/summary?period=day|week|month`
- `GET /api/admin/analytics/collaborators?period=day|week|month`
- `GET /api/admin/collaborators/<id>/performance?period=day|week|month`
- `GET /api/colaborador/performance?period=day|week|month`
- `GET /api/colaborador/ordering/bootstrap`
- `GET /api/colaborador/tables/<table_id>/ticket`
- `POST /api/colaborador/tables/<table_id>/ticket/items`
