# Financeiro — entrega 2 de 3: contas, títulos e liquidações

Base atualizada `86b621c`, com a primeira entrega já aplicada na main. Reúne
as etapas 3, 4, 5 e 6 aprovadas: contas bancárias/caixa, categorias, centros de
custo, contas a pagar/receber, parcelas, baixas parciais/totais e estornos.
A terceira entrega permanece reservada a fluxo de caixa, conciliação,
transferências financeiras e relatórios. Refatorações amplas ficam posteriores.

## Aplicação

```powershell
git am --keep-cr .\tesseract-financeiro-entrega2-tesouraria.patch
python run.py db upgrade
python -m pytest tests/test_financeiro_treasury.py tests/test_financeiro_exchange.py tests/test_financeiro_policy_versions.py tests/test_financeiro_ui_integrity.py tests/test_purchase_pricing.py tests/test_production_organization.py -q
```

Migration d60a8c34e972, parent c59f7a23d861. Reinicie a aplicação depois do upgrade.
Não há preenchimento automático de caixa/títulos nem migração de dados anteriores.

## Validação funcional

1. Configure organização/moeda/política; crie uma conta com saldo inicial
   conhecido, categoria de despesa e receita e centro de custo.
2. Acesse /financeiro/titulos/, escolha organização e carregue opções. Confira
   um título parcelado, registre e verifique a conservação dos totais e datas.
3. Na parcela, confira a baixa e confirme parte do principal com juros/multa/
   desconto. Verifique saldo aberto e saldo da conta; repita a mesma referência.
4. Complete a parcela. Estorne uma baixa com motivo e referência novos; confira
   reabertura e movimento contrário, sem exclusão do histórico.
5. Crie título a receber e registre recebimento. Não pode ser estornado se o
   dinheiro já utilizado impedir a saída da conta. Título com baixa ativa não
   pode ser cancelado; estorne antes.
6. Use taxa explícita da emissão e outra da baixa para uma obrigação estrangeira.
   Confira valores na moeda original/base e diferença cambial. Estorno conserva
   o movimento original; não consulta câmbio atual.
7. Carregue um pedido confirmado/recebido no formulário de título. Confira a
   origem e o total incluindo frete. Geração duplicada é recusada. Baixa e
   estorno não modificam pedidos, recebimentos ou saldo/custo de estoque.
8. Renomeie/inative cadastros e confira snapshots históricos. Erro ou conflito
   de formulário preserva os dados digitados; organização/moeda/abertura não
   podem ser trocadas pela manutenção do cadastro.

## Documentação

Manual: addons/addon_financeiro/docs/manual/04-tesouraria.md.
Contrato: addons/addon_financeiro/docs/technical/04-tesouraria.md.

Novas contas operam exclusivamente na moeda-base, sem cheque especial.
Escritas e APIs exigem admin; consulta HTML usa permissões automáticas.
Dados de fornecedor/cliente em títulos manuais são explícitos, sem criar
cadastros comerciais. Nenhuma integração bancária ou fiscal foi ativada.
A cadeia completa de upgrade foi conferida sobre o esquema inicializado.
Resultados dos testes e conferência do patch constam na entrega final.

## Resultado conferido

144 casos distintos passaram: 20 novos da tesouraria, 73 de câmbio/políticas/
interface financeira, 32 de preços monetários de compras e 19 da produção e
reconciliação da primeira entrega. Cinco casos adicionais de quantização da
fundação também passaram durante a verificação inicial. HTML real das seis
telas, fluxos POST/JSON, preservação de formulários e menus automáticos foram
conferidos. Sem inspeção visual em navegador ou certificação nativa de Windows/
PostgreSQL; a execução foi em Linux/SQLite.

Concorrência com duas conexões cobre criação idempotente do título, baixa
repetida, excesso de principal, dois títulos disputando a mesma conta e estorno
repetido. Falha no commit final desfaz evento, movimento e saldo juntos.
Prévia de título/baixa executou somente SELECT. A origem de compra conserva
preços, frete e estoque antes/depois de títulos e pagamentos.

A cadeia Alembic completa passou sobre esquema inicializado por create_all,
com uma única head d60a8c34e972. Upgrade repetido, schema incompatível antes de
DDL e bloqueio de downgrade com dados foram testados. Como na entrega anterior,
banco bruto sem bootstrap Core não é um fluxo de instalação novo certificado.

O patch foi aplicado por git am --keep-cr em checkout isolado da base 86b621c;
árvore final e verificação reversa conferidas. Não altera arquivos gerados pelo
CrudGen nem sobrescreve históricos. Nenhuma dependência nova.
