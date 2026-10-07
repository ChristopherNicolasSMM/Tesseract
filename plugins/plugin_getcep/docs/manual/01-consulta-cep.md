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
