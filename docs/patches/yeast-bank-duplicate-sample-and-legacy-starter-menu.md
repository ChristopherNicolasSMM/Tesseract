# Banco de Leveduras: duplicação de amostras e rota antiga de Starter

## Alterações

- `TX_YEAST_STARTER_LOGS` é desativada pelo `deprecated_transactions` do
  manifesto do BrewStation. A sincronização de transações é idempotente e
  preserva a personalização dos demais itens do menu.
- Favoritos de `/brewstation/yeast-starter-logs` redirecionam para Eventos do
  Banco com o filtro `Starter`. O destino exige a permissão de listagem de
  eventos.
- A listagem de Itens do Banco oferece **Duplicar** em modal para quem tem
  `yeast_bank_items.create`.
- A nova amostra herda a cepa e os campos físicos/de preparo exibidos no modal.
  Começa ativa; identificação e validade seguem as regras existentes. Eventos,
  contagens, descarte e valores calculados de viabilidade não são copiados.
- A criação passa por `yeast_integrity_service.operate`, que valida referências,
  campos, datas e persiste a operação em uma transação com rollback em falhas.
  Os filtros e a página atuais são preservados no retorno.

## Verificação

```bash
python -m pytest tests/test_yeast_bank_duplicate.py tests/test_yeast_bank_painel.py -q
```

O teste cobre duplicação sem cópia de histórico, origem preservada, referência
inválida, permissão e redirecionamento do endereço legado. A desativação do
menu usa `TX_YEAST_STARTER_LOGS` conforme o catálogo de transações versionado.

**Validação executada:** 19 testes passaram, incluindo os novos casos e a
regressão do painel Yeast Bank. Compilação Python, JSON e `git diff --check`
também passaram. O ambiente precisou de dependências Python adicionais para
iniciar a suíte; nenhuma delas foi adicionada ao repositório.
