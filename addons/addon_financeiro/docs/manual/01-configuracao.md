# Financeiro — primeira parte

Acesse **Configuração financeira** no menu, ou `/financeiro/`, como administrador.

1. Cadastre uma moeda: código ASCII de três letras, nome e casas decimais (0–6).
   Exemplo de configuração deliberada: BRL, Real, 2. Não há moeda pré-cadastrada.
2. Selecione a organização ativa, moeda-base e regra de arredondamento.
   HALF_UP afasta de zero nos empates; HALF_EVEN escolhe o último dígito par.
   Por exemplo, 1.005 com duas casas resulta em 1.01 ou 1.00, respectivamente.
3. Confira a política na tabela. Ela não altera compras, saldos ou custos.

Moeda e política inicial são imutáveis nesta entrega. Não existem botões para
sobrescrever ou excluir: alterações futuras exigem desenho de versão/vigência,
sem recalcular históricos. Verifique os dados antes de cadastrar.

`/admin/organizations/` permite ampliar a organização existente com razão
social, nome fantasia, CNPJ, inscrições estadual/municipal, e-mail, telefone,
site e endereço principal. Campos novos são opcionais, sem valores inferidos.
Responsáveis têm nome, função, CPF opcional, e-mail, telefone e estado ativo;
podem ser editados e inativados. Não criam usuários nem concedem acesso.

GetCEP preenche apenas campos vazios de logradouro, bairro, cidade e UF.
Número e complemento continuam manuais. Ao trocar CEP de endereço preenchido,
confira a sugestão e ajuste manualmente; campos preenchidos são preservados.
Salvar não consulta a internet. Documentos com DV válido não comprovam
existência, titularidade ou situação fiscal; IE/IM ficam como texto cadastral.

Esta parte não oferece taxas de câmbio, pagamentos, títulos, conciliação,
emissão fiscal, plano de contas nem integração de custos com o estoque.


## Correção de cadastro/menu — 08/10/2026

Financeiro usa a árvore automática do addon: Moeda e Política monetária,
com rotas `/financeiro/currencies/` e `/financeiro/monetary-policies/`.
`/financeiro/` permanece como acesso compatível, redirecionando à lista de moedas.
O antigo item isolado Configuração financeira é inativado no boot, sem excluir
sua linha/referências. Lista com busca/paginação; novo cadastro expansível.
Permissões de leitura seguem `currencies.list`/`monetary_policies.list`;
cadastro/escrita e API administrativa continuam exigindo `admin`.

Organizações ficam na lista tabular com busca/paginação/CSV/Excel e ação
Ver / Editar. O detalhe `/admin/organizations/<id>` reúne dados e responsáveis,
com formulários separados. Erro de validação mantém os valores digitados,
mostra mensagem no formulário e não altera o registro persistido. Formulários
parciais preservam campos omitidos e estado ativo; novos formulários enviam
marcador para distinguir checkbox desmarcado de campo não enviado.

CEP completo consulta após breve pausa, ao sair do campo ou por botão.
Enquanto o JS não inicializa, há mensagem explícita e o botão fica desabilitado;
se o plugin não carregou, a tela informa que o preenchimento é manual.
Falha/CEP ausente aparece junto ao campo, sem apagar endereço. Reinicie a
aplicação depois do patch; se houver página antiga em cache, use Ctrl+F5.
Não há nova migration sobre a revisão financeira b82d9e43a017 já aplicada.
