# Biblioteca de relatórios operacionais

Os oito JSON em examples são modelos editáveis: layout A4 paisagem, contrato
JSON Schema e dados iniciais vazios. report_library_service implementa adaptadores
de leitura usando serviços públicos existentes. Não importa ORM dos addons de
origem, não executa hooks de negócio, não faz commit e envolve leitura em
no_autoflush. Não modifica addons de origem nem adiciona migration/dependência.

## Fontes e contratos

| Exemplos | Contrato | Serviços/escopo |
| --- | --- | --- |
| receita-completa, checklist-receita | reports.library.recipe.v1 | MashRecipe, RecipeIngredient, RecipeStep, FermentationStep e WaterProfile; filhos filtrados por recipe_id |
| sessao-detalhada | reports.library.session.v1 | Exportador existente de sessão mais BrewSessionLog/BrewSessionAlarm; filtro por session_id e validação de plant_id |
| estoque-atual | estoque.saldos.v1 | Exportador existente de Saldo legado; compatível sem generated_at |
| banco-leveduras | reports.library.yeast.v1 | YeastBankItem.to_dict; projeção de cepa, recipiente e campos armazenados |
| disponibilidade-validade | reports.library.expiry.v1 | Mesma fonte, somente active, separada pela expiry_date |
| planejamento-starters | reports.library.starters.v1 | YeastBankEvent: Starter planned/active, item não excluído |
| dashboard-geral | reports.library.dashboard.v1 | Contagens e projeções das fontes acima; sem telemetria ou agregação de quantidades/custos |

GET /api/reports/examples/<name> devolve definição autorizada em Reports.
GET /api/reports/examples/<name>/choices devolve seletores de receita/sessão.
POST /api/reports/examples/<name>/data recebe {"options": {...}} e devolve
{"item": ...}. Consultas de dados exigem autenticação, CSRF, report_templates.detail,
addon/feature ativo e permissões .list das fontes usadas; respostas no-store.
As chaves aceitas são recipe_id, ou session_id+plant_id, ou days+reference_date
para validade; as demais fontes não aceitam filtros. IDs inteiros positivos,
janela inteira 0–365 dias e data ISO canônica. Valores desconhecidos são rejeitados.
A receita usa também fermentation_steps.list e water_profiles.list; sessão
usa brew_session_logs.list e brew_session_alarms.list. Dashboard exige a união
das permissões de suas fontes. Consulte PERMISSIONS no adaptador para lista completa.

Validade: vencidos antes da referência; a vencer da referência até o fim da
janela, inclusive; disponíveis depois da janela; sem validade em lista própria.
Viabilidade é o último valor armazenado, sem engine de recalculo. Datas UTC
identificam a geração; nenhum cálculo de crescimento, pitch rate ou criação
de planejamento é executado. Valores de custo não recebem moeda presumida.

## Fluxo e limites

Criar modelo pronto → rascunho salvo vazio → selecionar fonte/registro →
carregar cópia em sample_data → conferir prévia → salvar/publicar conforme fluxo
existente. A cópia segue o controle de acesso do relatório após ser salva,
não uma autorização dinâmica das fontes. Não há consulta automática na impressão.

O contrato de sessão detalhada é diferente de brewstation.session.v1. O botão
de relatório do consumidor session continua oferecendo somente modelos do seu
contrato original. Use a IDE ou a API genérica publicada para sessão detalhada;
o exemplo simples brewstation-session continua intacto. Estoque mantém seu DTO
original. Não se altera serviço/consumer dos addons para ampliar esses contratos.

Os serviços públicos .list são atualmente não paginados. O adaptador rejeita
mais de 2.000 registros por lista após a leitura; não trunca silenciosamente.
Esse limite não elimina o custo da consulta original, nem garante snapshot
transacional entre fontes. Coleções muito grandes exigirão APIs de leitura
paginadas nas fontes em trabalho futuro autorizado. Mantêm-se limite JSON
1 MiB e restrições de layout/tabela do Reports. Nunca substitui a leitura por
SQL/ORM privado de outro addon. HTML e impressão do navegador são o caminho
principal; PDF do servidor continua opcional.

## Validação

18 testes novos cobrem os oito contratos, leitura real com fixtures, isolamento
por receita/sessão, classificação de validade, starters registrados, compatibilidade
do estoque, rejeição de parâmetros, CSRF/RBAC e indisponibilidade de feature.
A suíte completa de Reports passou com 224 testes, 10 subtestes e um teste
WeasyPrint opt-in desabilitado; os 11 testes Node passaram. O teste de navegador
cria e carrega cada um dos oito modelos na IDE usando banco descartável.
