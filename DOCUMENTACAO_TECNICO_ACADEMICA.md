# Sistema Integrado de Gestao para Cafeteria

## Documentacao Tecnico-Academica

**Autores:** [Seu Nome]  
**Orientador:** [Nome do Professor]  
**Curso:** [ADS / Engenharia de Software / SI]  
**Ano:** 2026

---

## 1. Resumo

O presente documento descreve a arquitetura, modelagem e implementacao de um sistema completo para cafeterias, composto por quatro subsistemas: aplicativo para o cliente na mesa, gerenciador de pedidos para atendente ou caixa, dashboard para a cozinha e painel administrativo para o gerente. A solucao proposta utiliza Flask como framework backend, PostgreSQL para persistencia, autenticacao via JWT, interface responsiva com Tailwind CSS e comunicacao em tempo real via WebSockets com Flask-SocketIO. O objetivo principal e otimizar o fluxo de pedidos, reduzir erros de comunicacao e oferecer visibilidade gerencial sobre vendas por mesa e colaborador.

**Palavras-chave:** Flask, JWT, cafeteria, gestao de pedidos, WebSockets, PostgreSQL.

---

## 2. Introducao

Estabelecimentos de alimentacao, especialmente cafeterias, frequentemente enfrentam gargalos na comunicacao entre salao e cozinha, alem de dificuldades no controle de vendas por mesa e por funcionario. Este trabalho propoe um sistema integrado em que:

- clientes fazem pedidos por meio de uma interface acessada na propria mesa, preferencialmente por QR Code;
- atendentes gerenciam pedidos, fecham contas e associam vendas aos colaboradores responsaveis;
- a cozinha visualiza uma fila organizada de preparo;
- o gerente acompanha vendas em tempo real e gera relatorios operacionais.

A separacao em modulos e o uso de autenticacao JWT garantem seguranca, rastreabilidade e controle de acesso por perfil.

---

## 3. Objetivos

### 3.1 Objetivo Geral

Desenvolver um sistema web completo para gestao de pedidos, vendas e cozinha em uma cafeteria, utilizando tecnologias open source como Flask, PostgreSQL, Tailwind CSS e JWT.

### 3.2 Objetivos Especificos

- Permitir que clientes enviem pedidos de suas mesas sem intermediacao direta.
- Oferecer ao gerenciador de pedidos uma interface unificada para controle de comandas.
- Exibir na cozinha uma sequencia cronologica de pedidos com detalhes de cada item.
- Gerar relatorios gerenciais, incluindo produtos mais vendidos, produtividade por colaborador e faturamento por periodo.
- Implementar autenticacao segura baseada em tokens JWT para os perfis atendente, gerente, cozinha e administrador.

---

## 4. Requisitos do Sistema

### 4.1 Requisitos Funcionais

| ID   | Descricao                                                                               |
| ---- | --------------------------------------------------------------------------------------- |
| RF01 | O cliente deve visualizar o cardapio e adicionar itens ao pedido da mesa.               |
| RF02 | O cliente deve enviar o pedido para o backend.                                          |
| RF03 | O gerenciador deve visualizar todos os pedidos ativos por mesa.                         |
| RF04 | O gerenciador deve adicionar e remover itens de um pedido.                              |
| RF05 | O gerenciador deve finalizar o pedido e registrar pagamento em dinheiro, cartao ou PIX. |
| RF06 | A cozinha deve visualizar pedidos em sequencia cronologica.                             |
| RF07 | A cozinha deve alterar o status do pedido entre recebido, preparando e pronto.          |
| RF08 | O gerente deve visualizar vendas ativas por mesa e colaborador.                         |
| RF09 | O gerente deve acessar relatorios com filtros por dia, semana e mes.                    |
| RF10 | O administrador deve gerenciar o cardapio por meio de CRUD de produtos e categorias.    |
| RF11 | O administrador deve gerenciar mesas e colaboradores.                                   |
| RF12 | O sistema deve exigir autenticacao JWT para todos os acessos autenticados.              |

### 4.2 Requisitos Nao Funcionais

| ID    | Descricao                                                                      |
| ----- | ------------------------------------------------------------------------------ |
| RNF01 | O tempo de resposta ao enviar um pedido deve ser de ate 2 segundos.            |
| RNF02 | O dashboard da cozinha deve ser atualizado em tempo real via WebSocket.        |
| RNF03 | A interface deve ser responsiva e funcionar adequadamente em tablet e desktop. |
| RNF04 | Os tokens JWT devem expirar apos 8 horas, com refresh token opcional.          |
| RNF05 | As senhas devem ser armazenadas com hash bcrypt.                               |
| RNF06 | O banco PostgreSQL deve possuir politica de backup automatico diario.          |

---

## 5. Arquitetura do Sistema

### 5.1 Visao Geral

A arquitetura adotada e do tipo cliente-servidor, combinando comunicacao sincrona por REST e comunicacao assincrona por WebSockets.

```text
[App Mesa] -----\
[Gerenciador] ---+--> REST + WebSocket --> Flask Backend --> PostgreSQL
[Cozinha] ------/
[Painel Admin] -----> REST
```

Os principais elementos arquiteturais sao:

- frontends separados, com HTML, JavaScript e Tailwind CSS para cada modulo;
- backend unico em Flask, organizado por blueprints e servicos de dominio;
- autenticacao via JWT em rotas protegidas;
- camada de tempo real com Flask-SocketIO para emissao de novos pedidos e mudancas de status.

### 5.2 Diagrama de Componentes Textual

1. **Auth Service**: responsavel por login, emissao e validacao de tokens JWT.
2. **Pedido Service**: responsavel pelo CRUD de pedidos, itens e alteracoes de status.
3. **Mesa Service**: gerencia mesas e associacao com pedidos ativos.
4. **Produto Service**: disponibiliza cardapio, categorias e regras de disponibilidade.
5. **Relatorio Service**: consolida vendas e indicadores gerenciais.
6. **WebSocket Namespace**: canal dedicado a cozinha para entrega de eventos em tempo real.

---

## 6. Modelagem do Banco de Dados

### 6.1 Esquema Relacional Proposto

```sql
CREATE DATABASE cafeteria;

CREATE TABLE colaboradores (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    perfil VARCHAR(20) CHECK (perfil IN ('admin', 'gerente', 'atendente', 'cozinha'))
);

CREATE TABLE mesas (
    id SERIAL PRIMARY KEY,
    numero INTEGER UNIQUE NOT NULL,
    qr_code TEXT UNIQUE
);

CREATE TABLE categorias (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(50) NOT NULL,
    ativo BOOLEAN DEFAULT TRUE
);

CREATE TABLE produtos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    preco DECIMAL(10,2) NOT NULL,
    ingredientes TEXT,
    categoria_id INTEGER REFERENCES categorias(id),
    ativo BOOLEAN DEFAULT TRUE
);

CREATE TABLE pedidos (
    id SERIAL PRIMARY KEY,
    mesa_id INTEGER REFERENCES mesas(id),
    colaborador_id INTEGER REFERENCES colaboradores(id),
    status VARCHAR(20) DEFAULT 'aberto',
    total DECIMAL(10,2) DEFAULT 0,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE itens_pedido (
    id SERIAL PRIMARY KEY,
    pedido_id INTEGER REFERENCES pedidos(id) ON DELETE CASCADE,
    produto_id INTEGER REFERENCES produtos(id),
    quantidade INTEGER NOT NULL,
    observacao TEXT,
    preco_unitario DECIMAL(10,2) NOT NULL
);

CREATE TABLE pagamentos (
    id SERIAL PRIMARY KEY,
    pedido_id INTEGER REFERENCES pedidos(id),
    valor_pago DECIMAL(10,2),
    forma_pagamento VARCHAR(20),
    data_pagamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 Indices Sugeridos

- `pedidos(mesa_id, status)` para consultas de mesas abertas.
- `itens_pedido(pedido_id)` para acelerar joins por pedido.
- `pedidos(criado_em)` para apoiar relatorios por periodo.

---

## 7. Tecnologias Utilizadas

| Camada                    | Tecnologia                                 |
| ------------------------- | ------------------------------------------ |
| Backend                   | Python 3.10+ / Flask / Flask-SocketIO      |
| Autenticacao              | Flask-JWT-Extended + bcrypt                |
| Banco de dados            | PostgreSQL + psycopg2-binary ou SQLAlchemy |
| Frontend                  | HTML5, JavaScript e Tailwind CSS           |
| Comunicacao em tempo real | Socket.IO cliente + Flask-SocketIO         |
| Servidor                  | Gunicorn + eventlet                        |
| Versionamento             | Git e GitHub                               |
| Documentacao              | Markdown convertido para PDF               |

---

## 8. Estrutura de Pastas Proposta

```text
cafeteria_system/
|-- backend/
|   |-- app.py
|   |-- config.py
|   |-- models.py
|   |-- auth.py
|   |-- pedidos_routes.py
|   |-- produtos_routes.py
|   |-- relatorios_routes.py
|   |-- mesas_routes.py
|   |-- socket_events.py
|   `-- db_connection.py
|-- frontend/
|   |-- cliente_mesa/
|   |-- gerenciador/
|   |-- cozinha/
|   `-- admin/
|-- static/
|   |-- css/
|   `-- js/
|-- templates/
|-- requirements.txt
`-- README.md
```

### 8.1 Relacao com o Repositorio Atual

O repositorio atual `order_snakbar` contem, no momento, a estrutura inicial de diretorios `app/`, `app/static/` e `app/templates/`, sem implementacao funcional concluida. Assim, esta documentacao deve ser entendida como **especificacao arquitetural e academica do sistema alvo**, servindo de base para a construcao incremental do software.

---

## 9. Autenticacao JWT

### 9.1 Fluxo de Autenticacao

1. O usuario envia `POST /api/login` com e-mail e senha.
2. O backend valida as credenciais e retorna um `access_token`.
3. O frontend armazena o token em `localStorage` ou `sessionStorage`.
4. Requisicoes protegidas enviam o cabecalho `Authorization: Bearer <token>`.
5. Decorators como `@jwt_required()` e `@role_required('gerente')` controlam autenticacao e autorizacao.
6. O logout e realizado no frontend pela remocao do token armazenado.

### 9.2 Exemplo de Payload JWT

```json
{
  "sub": "id_do_colaborador",
  "perfil": "atendente",
  "email": "joao@cafeteria.com",
  "exp": 1712000000
}
```

---

## 10. Comunicacao em Tempo Real

Um caso de uso central e a atualizacao imediata da cozinha quando um pedido e confirmado no gerenciador.

- o backend emite o evento `novo_pedido` com os dados consolidados do pedido;
- o frontend da cozinha se conecta ao namespace dedicado e escuta novos eventos;
- o gerenciador, apos confirmar um pedido, dispara a notificacao para o canal da cozinha.

Exemplo de evento:

```javascript
socket.emit("novo_pedido", {
  pedido_id: 101,
  mesa: 12,
  itens: [{ nome: "Cafe", obs: "pouco acucar" }],
  timestamp: "2026-04-15T10:30:00",
});
```

---

## 11. Principais Interfaces

### 11.1 Aplicativo do Cliente na Mesa

- URL sugerida: `/mesa/:id`.
- Exibe cardapio agrupado por categoria.
- Permite montar e enviar o pedido da mesa.

### 11.2 Gerenciador de Pedidos

- URL sugerida: `/gerenciador`.
- Disponivel para perfis atendente, gerente ou administrador.
- Lista mesas com pedidos abertos, inclusao de itens e fechamento de conta.

### 11.3 Dashboard da Cozinha

- URL sugerida: `/cozinha`.
- Disponivel para perfil cozinha.
- Exibe fila vertical de pedidos e comandos de alteracao de status.

### 11.4 Painel Administrativo

- URL sugerida: `/admin`.
- Disponivel para administrador e gerente.
- Contem gestao de cardapio, mesas, colaboradores e relatorios.

---

## 12. Seguranca

- Tokens JWT devem ser assinados com chave secreta forte.
- HTTPS deve ser obrigatorio em producao.
- Validacao de entrada deve ser aplicada com ferramentas como Marshmallow ou Pydantic.
- SQL injection deve ser evitado com ORM ou consultas parametrizadas.
- CORS deve ser restrito a origens confiaveis.
- Senhas devem ser armazenadas exclusivamente em formato hash com bcrypt.

---

## 13. Cronograma de Desenvolvimento

| Semana | Atividades                                                            |
| ------ | --------------------------------------------------------------------- |
| 1      | Modelagem do banco, configuracao inicial do Flask e autenticacao JWT. |
| 2      | CRUD de produtos, categorias e mesas.                                 |
| 3      | Implementacao de login, perfis e telas de autenticacao.               |
| 4      | Desenvolvimento do aplicativo da mesa.                                |
| 5      | Desenvolvimento do gerenciador de pedidos.                            |
| 6      | Dashboard da cozinha e integracao com WebSockets.                     |
| 7      | Painel gerencial com relatorios e indicadores.                        |
| 8      | Integracao final, testes e preparacao da entrega academica.           |

---

## 14. Consideracoes Finais

O sistema proposto atende aos requisitos operacionais de uma cafeteria moderna ao integrar pedidos, cozinha, atendimento e gestao em uma unica solucao. A combinacao entre Flask, PostgreSQL, JWT e WebSockets fornece uma base de baixo custo, escalavel e tecnicamente adequada para o contexto academico e profissional. Como continuidade, o projeto pode evoluir para integracao com autoatendimento, aplicacoes moveis e analise avancada de dados de vendas.

---

## 15. Referencias

- Flask Documentation. Flask Web Development.
- JWT.io. JSON Web Tokens Introduction.
- Tailwind CSS. Utility-First CSS Framework.
- PostgreSQL Global Development Group. PostgreSQL Documentation.
- Socket.IO. Real-time Application Framework.
