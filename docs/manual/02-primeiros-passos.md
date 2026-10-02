# 02 — Primeiros Passos

## 1. Acessando o sistema

Acesse o endereço do Tesseract no navegador — você verá a tela de
login. Peça para o administrador criar seu usuário, se ainda não tiver.

## 2. Login

Informe seu usuário e senha na tela de login. Esqueceu a senha? Peça
para um administrador redefinir em "Gestão de Usuários" → seu usuário
→ "Redefinir senha".

## 3. Primeira tela

Depois de logado, você cai na **Início** — um painel com cards das
áreas que você tem acesso, organizado por grupo (Banco de Levedura,
Dispositivos, Receitas, Sessões de Brassagem, Ingredientes, Envase,
Estoque, e — se você for administrador — Usuários, Papéis, Regras de
Campo, Versionamento, Catálogo de Transações, Configurações de Menu,
Conexões OData, Model Builder, Playground, Logs, Tarefas Agendadas e
Designer Visual). O menu lateral mostra a mesma lista, em árvore —
grupos podem ter sub-grupos, e você recolhe/expande clicando no nome.

## 4. Seu perfil

Clique no seu nome, no topo da tela, e depois em "Meu Perfil" para
editar seus dados, trocar sua senha, e escolher entre tema claro ou
escuro.

## 5. Ajustando o menu do seu jeito

Se a ordem ou o agrupamento padrão do menu não for do seu gosto, vá em
"Meu Perfil" → "Preferências de Menu" — dá pra reordenar itens dentro
do mesmo grupo e escolher quais grupos ficam recolhidos por padrão,
só pra você, sem afetar os outros usuários.


## Validação de atualização — migrations

Se a suíte informar dois heads depois de um `upgrade` bem-sucedido, confira
`flask db heads`: o teste passou a usar o grafo real do Alembic em vez de
interpretar aspas por regex. Não criar merge nem usar `stamp` apenas para
contornar essa expectativa antiga.

O teste `tests/test_migrations_idempotent.py` executa upgrade e downgrade em
SQLite temporário. Seu comando de downgrade é um teste de manutenção, não
uma etapa para aplicar no banco de uso. A correção histórica não exige novo
`db upgrade`; a migration do registro de envase entregue em 2A.2 continua
necessária se ainda não foi aplicada. Roteiro em
[correção das migrations](../patches/migrations-downgrade-testes.md).
