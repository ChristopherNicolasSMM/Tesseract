# Opções fixas e referências em formulários

Diretriz solicitada pelo usuário: preferir seleção a texto livre quando existe um
conjunto conhecido de valores ou uma referência cadastrada. Aplicar nas próximas
criações/revisões de formulários sem restringir campos legitimamente abertos.

- Vocabulário fechado: declarar `@enum_field` no model, com pares `(valor interno,
  rótulo em português)`. Criação, edição e filtros devem usar a mesma anotação.
- Referência a registros: declarar `@weak_ref`, com resolver, catálogo e chave
  estável adequados; usar o combo pesquisável padrão. Texto digitado não é referência.
- `@choices` serve para opções dinâmicas/filtros; sozinho não cria um select de
  edição. Não usá-lo como substituto de `@enum_field` em categorias fixas.
- Booleanos: checkbox/seletor booleano padrão. Nomes, descrições, unidades extensíveis
  e identificadores livres continuam texto quando não existe catálogo real.
- Complementar com `@required`, `@field_labels` e validações de tamanho/limites
  pertinentes. Validar criação e alteração também no servidor, inclusive via API.
- Preservar legados: normalizar apenas aliases conhecidos. Não selecionar por
  engano a primeira opção quando o valor antigo é desconhecido; exigir correção
  explícita no formulário. Não recriar registros nem alterar seus identificadores.

## Aplicação em Funções de Dispositivo

`DeviceFunction.category`: Sensor (`sensor`), Atuador (`actuator`), Híbrido (`hybrid`).
`data_type`: Número decimal (`float`), Número inteiro (`int`), Liga/desliga (`bool`),
Texto (`string`). Ambos usam `@enum_field`, `@required` e rótulos em português.
O catálogo está em `model/device_function_options.py` e também alimenta a validação.

A validação nos eventos ORM de inserção/alteração ocorre dentro do commit, mantendo
os serviços/controllers gerados intactos e retornando o erro transacional já previsto.
As grafias antigas conhecidas aparecem como a categoria canônica na edição; ao
salvar uma nova categoria/alias, o valor é padronizado. Ler o cadastro não migra a
linha. Uma alteração não relacionada não bloqueia exclusão/edição parcial de um
legado desconhecido; alterar a própria categoria exige um valor válido.

Papéis de mapeamento, tipos de ator e tipos de dispositivo já possuem `@enum_field`.
Referências a tanque, função e controlador usam o combo de referência correspondente.

Testes: formulários anotados, opções persistidas, rejeição/rollback no serviço e
na API, edição de aliases e sinalização de legado desconhecido; regressão dos
mapeamentos e importação Bridge. Sem alteração de schema ou acionamento físico.
