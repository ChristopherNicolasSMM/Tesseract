# Conversões de ingredientes pelo material no workspace

Implementado em 06/10/2026; aguarda aplicação e validação local. O patch
anterior de revisão integrada foi validado pelo usuário.

## Problema e comportamento

A receita pode importar Whirlfloc em `items`, enquanto o material mantém
estoque em `UN`. O de-para identifica o material, mas não define conversão.
Agora `item`, `items` e `ITEM` são reconhecidos como o código `ITEM` na
consulta de conversão, preservando a unidade original no ingrediente.
Não há equivalência automática de ITEM para UN, massa ou volume.

Na aba Receita, uma linha pendente com material resolvido e unidades
origem/base diferentes oferece **Ajustar conversão do material**. O modal
mostra o material, a origem importada, a base, o fator e uma prévia. Para
Whirlfloc, cadastre fator 1 SOMENTE se cada item importado representar uma
unidade do material: `2 items × 1 = 2 UN`.

A quantidade é multiplicada pelo fator para obter unidades-base. Fator
0,5 significa que 1 unidade de origem corresponde a 0,5 unidade-base.
O valor nunca é sugerido automaticamente. Conteúdo de PCT continua no fator
do material; nenhum nome de unidade incorpora peso ou volume.

## Cadastro e limites

- Requer `recipe_steps.list` e `material_unidades.create`.
- O material deve estar ativo, não apagado, com base válida no catálogo.
- Uma base legada sem linha MaterialUnidade é cadastrada com fator 1,
  preservando o código e a unidade do material. Base existente é preservada.
- ITEM é incluído no catálogo apenas no primeiro salvamento explícito da
  conversão, dentro da mesma transação. Sua referência genérica fica vazia:
  o fator é específico do material. Não há migration ou gravação no GET.
- Outras unidades devem existir no catálogo. O formulário usa a unidade
  da receita, não recebe nomes arbitrários para cadastrar no catálogo.
- Cadastro repetido com o mesmo fator é idempotente. Unidade existente
  inativa, duplicada, de uso incompatível ou com outro fator é rejeitada;
  manutenção avançada continua no cadastro de unidades do material.
- O ajuste vale para outras receitas do mesmo material e para futuras
  importações que reutilizem esse vínculo. De-para, receita e suas unidades
  originais permanecem iguais. A alteração é permitida em receita usada,
  pois não é edição do ingrediente; modifica a configuração do material.
- Conferência e custo estimado usam a conversão. Confirmar ingredientes
  continua usando a regra central de ledger/saldo. Custo registrado de lote
  confirmado não é recalculado; snapshots de envase não são modificados.
- Fatores devem ser finitos e positivos. Unidades inativas/duplicadas não
  são usadas pela consulta de conversão específica do material.
- Falha ao salvar faz rollback de catálogo, base e unidade adicional.
  Reserva de escrita SQLite serializa cadastros feitos por este serviço.
  Não substitui a manutenção avançada nem garante ausência de duplicatas
  criadas por outros caminhos legados.

## Arquitetura e interface

`material_conversion_service` é serviço público/manual do estoque, retorna
dados/fator e mantém o ORM no addon proprietário. O conversor de Envase
passa a consultá-lo; não acessa mais MaterialUnidade de outro addon.
O cadastro gerado pelo CrudGen permanece intacto.

POST:
`/brewstation/plant-workspace/<planta>/recipes/<receita>/ingredients/<ingrediente>/conversion`

Valida planta, receita, ingrediente, vínculo e unidades esperadas. Normal
retorna à mesma receita; AJAX recarrega o fragmento selecionado. Nenhuma
consulta/simulação/cadastro de conversão movimenta estoque. Não há nova
rota de baixa. Não é necessário `flask db upgrade` para este patch. Reinicie a aplicação
após aplicá-lo para recarregar serviços e traduções.

O editor usa modal Bootstrap, confirmação Core e mensagens existentes.
Fecha o editor antes de abrir a confirmação para evitar backdrops
sobrepostos. Cancelamento/erro reabre o editor, preservando o valor. Há
proteção contra envio simultâneo e navegação de fragmento já removido.
O helper de envio agora retorna resultado ou null; chamadas existentes
continuam válidas e respostas antigas não trocam a aba atual.

Também foi corrigido o carregamento de i18n: ModuleManager expõe as features
realmente registradas; o tradutor inclui seus arquivos sem reinstanciar
addons nem descobrir diretórios inativos. Isso disponibiliza os textos do
modal e as mensagens de confirmação do Core.

## Aplicação e testes locais

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-conversoes-ingredientes-material.patch
python -m pytest tests/test_plant_workspace.py tests/test_mash_control_ingredient_resolution.py tests/test_precificacao_envase.py tests/test_feature_envase.py tests/test_addon_estoque.py tests/test_i18n_registered_features.py tests/test_module_discovery.py -q
node tests/js/test_workspace_ingredient_conversion.cjs
node tests/js/test_workspace_recipe_generation.cjs
node tests/js/test_workspace_operations.cjs
```

Para começar somente pelos novos casos:

```powershell
python -m pytest tests/test_plant_workspace.py tests/test_mash_control_ingredient_resolution.py -k conversion -q
python -m pytest tests/test_i18n_registered_features.py -q
```

## Roteiro visual

1. Abra `/brewstation/plant-workspace/1?tab=recipe&recipe_id=<ID_RECEITA>`.
   Use a receita com Whirlfloc em items e material vinculado com base UN.
2. Clique **Ajustar conversão do material** na linha pendente.
3. Confira material e base. Informe 1 somente se item = uma unidade real.
   Verifique a prévia (ex.: 2 items → 2 UN). Teste 0,5 para observar a prévia,
   sem salvar se esse não for o fator correto.
4. Cancele a confirmação: editor deve reabrir sem gravar. Salve o fator
   correto; a receita deve permanecer selecionada e a pendência desaparecer
   se não houver outros problemas. Verifique os temas claro e escuro.
5. Abra a sessão da receita pelo workspace e confira a quantidade convertida
   e o custo estimado. Apenas cadastrar a conversão não deve reduzir saldo.
6. Confirme ingredientes em lote de teste. Repita a confirmação: sem segunda
   baixa. Em lote já confirmado, o custo registrado permanece congelado.
7. Teste sem permissão de criar unidades e tente fator inválido/conflitante.
   Não deve ocorrer gravação parcial ou alteração de unidade-base.

## Pendências preservadas

Troca de unidade-base, revisão de fator existente, ativação/restauração de
unidades e catálogo de códigos desconhecidos continuam na manutenção de
estoque. O patch não incorpora manutenção completa de materiais ou um novo
motor universal de conversões. As demais pendências de plantas, sessões,
PID e origem física de eventos permanecem no plano de continuidade.

## Verificação executada nesta entrega

70 casos Python únicos aprovados: 16 de workspace/conversão, 10 de
conversão/consumo/rollback no saneamento, 38 da suíte de precificação e
6 de tradução/descoberta de módulos. As três suítes Node indicadas passaram.
Sintaxe Python/Jinja/JSON/JavaScript e diff conferidos. Format-patch aplicado
com git am em checkout isolado; árvore resultante idêntica à entrega. A execução ampla foi
interrompida e não é considerada aprovada; o comando completo acima fica
para validação local. Não houve teste visual no navegador ou banco do usuário.
