# GetCEP

Plugin auxiliar, sem tabelas. Nos formulários de endereço com `cep`, `cidade`
e `estado`, informe o CEP e saia do campo, ou clique **Consultar CEP**.
A consulta sugere logradouro, bairro, cidade e UF de endereço no Brasil.
Campos vazios são preenchidos; dados existentes e edições durante a consulta
são preservados. Confira o endereço, número e complemento antes de salvar.

Disponível no cadastro Core de organizações e nos formulários de endereços
do Estoque (incluindo modais dinâmicos). Fornecedores/transportadoras usam
seus vínculos aos mesmos endereços, sem criar cadastro paralelo. Se a API
falhar ou o CEP não existir, o preenchimento e a gravação manual continuam.
Campos `pais` explicitamente estrangeiros não acionam ViaCEP.

Não use para consultar bases em massa: o provedor pode bloquear esse uso.


## GetCEP 1.0.1

Consulta também após digitar oito dígitos e aguardar 450ms. O campo exibe
inicialização, consulta ou motivo de falha; ausência do plugin é indicada no
cadastro da organização. Conferir número/complemento continua necessário.
Arquivo de UI versionado: `/plugins/getcep/static/getcep.js?v=1.0.1`.
