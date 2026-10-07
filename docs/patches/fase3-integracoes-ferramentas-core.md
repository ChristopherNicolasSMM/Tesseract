# Fase 3 — ferramentas e integrações Core

Implementado no ambiente de geração; aplicação e validação local pendentes.
Base 2d88af3, após o pacote administrativo aplicado pelo usuário. A confirmação
de aplicação foi registrada separadamente da confirmação dos testes locais.
Sem migration, alteração de schema, dependências ou templates CrudGen.

## Evidências e mudanças

Reprodução inicial na base: **4 failed in 7.38s**, com LegacyAPIWarning como
erro. Caminhos: testar conexão OData, salvar conteúdo HTML, detalhe do Model
Builder e PATCH do provedor local. Avisos são de compatibilidade no runtime
normal atual; testes estritos os tornam erros. Substituídos por Session.get.

| Área | Acessos manuais corrigidos | Contrato preservado |
| --- | --- | --- |
| Administração OData | 5 | Remoção, teste, entidades, override e navegação |
| Designer | 6 | Edição/gravação, publicação, menu, exclusão e execução de ação |
| Model Builder controller | 4 | Detalhe, filhos e configuração de campos |
| Model Builder serviço | 7 | Edição/remoção de campo, preview, geração e filhos |
| Playground serviço | 6 | Pasta, pedido, arquivamento/manutenção e ponte de modelo |
| Provedor OData local | 1 | Modelo resolvido dinamicamente, autorização antes do lookup e PATCH |

Total: 29 chamadas. Foram atualizadas 44 leituras legadas nos testes
correspondentes. Dois novos casos conferem que PATCH sem permissão é negado
antes do lookup para ID existente ou ausente, preservando os dados.
Decorators, filtros de coleção, valores de chave, redirects, erros e commits
permanecem nos contratos atuais. Nenhum arquivo gerado foi editado; geração
real ocorre apenas nos projetos temporários dos testes.

A primeira seleção ampliada do Builder/CrudGen, após corrigir os controllers,
revelou as chamadas dos serviços: **12 failed, 48 passed, 19 errors in 7.94s**.
Incluídos os serviços envolvidos e o Playground no mesmo pacote. Após remover
os avisos, apareceram duas expectativas antigas de arquivos:
**2 failed, 118 passed in 52.28s**.

A seleção inicial OData/Designer passou 62 casos e encontrou uma referência
antiga à documentação: **1 failed, 62 passed in 76.98s**. O histórico b035fe4
consolidou os documentos 16/17/18 em docs/skills/16-designer-paginas-customizadas.md;
README confirma a remoção dos arquivos antigos. O teste agora consulta o
arquivo consolidado e mantém as verificações de caminhos de dados, 401/403,
SSTI e CSRF.

Os dois testes do pipeline esperavam nove arquivos por model, mas o gerador
atual escreve o model e dez arquivos do CrudGen, incluindo os hooks HTML de
lista e detalhe. Atualizados para onze por model e vinte e dois para pai/filho;
verificam também a presença dos dois hooks por entidade. Não foi alterado o
gerador para satisfazer contagem antiga.

Os três defeitos de teste também foram reproduzidos na base 2d88af3 isolada:
**3 failed in 3.03s**, com avisos legados ignorados apenas nessa reprodução para
isolar essas expectativas. As seleções finais tratam os avisos como erro.

## Aplicação e comandos

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-fase3-integracoes-ferramentas-core.patch
python -m pytest tests/test_phase8_odata.py tests/test_odata_bugfixes.py tests/test_fase10_patch2_provedor_local.py tests/test_fase12_paginas_customizadas.py tests/test_fase10_patch6_substituicao_menu.py -q -W error::sqlalchemy.exc.LegacyAPIWarning --tb=short
python -m pytest tests/test_model_builder.py tests/test_model_builder_patch_b.py tests/test_phase4_crudgen.py tests/test_playground.py tests/test_playground_v2.py -q -W error::sqlalchemy.exc.LegacyAPIWarning --tb=short
```

Aplicar após o pacote administrativo Core. Não requer `flask db upgrade`.
Reiniciar a aplicação. Runtime de geração: Python 3.12.3, Flask 3.1.3,
Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.51, pytest 9.1.1. Execução por
/usr/bin/python3 com PYTHONPATH do ambiente venv-yeast-audit anteriormente
registrado. Diferenças de Alembic/transitivas continuam conforme relatório de
compatibilidade; não houve nova instalação nem certificação integral do lock.

## Conferência visual e de integração

1. `/admin/odata/`: abrir conexão de teste já existente, testar e consultar
   entidades; conferir navegação e override de nome existente sem usar dados
   reais para exclusão. Testes de rede usam servidor HTTP local de fixture.
2. `/admin/designer/`: em página descartável, editar/gravar HTML, publicar e
   abrir `/designer/<slug>`. Conteúdo do banco continua HTML, sem execução
   Jinja. Conferir a ação de dados configurada e retorno ao editor.
3. `/admin/model-builder/`: abrir rascunho descartável e conferir preview,
   campos, submodel e ordem. Geração no ambiente local deve usar apenas addon
   de teste, pois escreve arquivos; os testes automatizados geram em pasta
   temporária e verificam annotations/pipeline sem editar arquivos existentes.
4. `/admin/playground/`: conferir organização de pedido de teste em pasta,
   arquivamento/restauração e ponte da resposta para rascunho. Uma execução
   HTTP manual deve usar endpoint de teste. SQL mantém o contrato de SELECT.
5. Com usuário sem permissão, conferir bloqueios apropriados. Conferência
   visual nos temas claro/escuro e endpoints remotos reais continua pendente.

## Pendências e limites

Sem nova integração de câmbio ou culturas físicas. Cotacao/PedidoCompra ainda
não representam moeda/taxa; decisão de moeda-base, precisão, fonte/data e
fronteira do financeiro permanece necessária. YeastBank físico depende de
unidade física, genealogia e contratos de consumo/descarte/estorno.

Reprodução de todas as versões fixadas, Windows, PostgreSQL e hardware continuam
pendentes. Os testes de OData usam fixture local, portanto não certificam
Brewfather ou serviços externos. Recebimento parcial permanece adiado. Não há
recalculo de saldo, ledger, snapshots ou custos históricos.


## Resultados finais e protocolo de entrega

- Repetição de Builder, scaffold, CrudGen, Playground e páginas customizadas:
  **136 passed in 64.24s**, com LegacyAPIWarning como erro. Inclui os 16 casos
  de páginas customizadas, agora todos aprovados.
- Outros 47 casos de OData/provider/substituição de menu passaram na seleção
  inicial de 63; seus arquivos permaneceram inalterados após essa execução.
- Total: **183 casos distintos aprovados**, incluindo dois novos de autorização
  de PATCH. Os 16 casos de páginas customizadas não são contados duas vezes.
- `git diff --check`: aprovado. Patch produzido com git format-patch sobre
  2d88af3; entrega requer aplicação isolada por git am, igualdade das árvores
  e git apply --reverse --check.
- Gerados do teste residem em projetos temporários; não integram o patch.
  docs/imgs/logo.png preexistente fica fora do pacote.
