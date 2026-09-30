# Verificação do combo de funções no workspace

O teste `test_mapeamento_planta_cria_vinculo_e_rejeita_outra_planta` esperava
encontrar todas as funções no HTML inicial, comportamento do seletor anterior.
O componente padrão `weakref-combo` consulta `/api/options/device_functions`
com `value_field=name` para carregar as opções durante a busca.

O teste passa a verificar a configuração do componente e o retorno da API
(chave `workspace_temp` e descrição `Temperatura`). Após a criação, verifica
também a presença do vínculo na aba da planta. Permanecem as verificações de
pertencimento do tanque, compatibilidade do papel e rejeição de duplicidade.

Não há mudança de produção, migration ou cadastro. Executar:

```shell
pytest tests/test_plant_workspace.py tests/test_weak_ref_value_field.py
```
