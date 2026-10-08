# Taxas, simulação e histórico

Antes de usar, aplique a migration `d04f1a65c239` com `python run.py db upgrade`.
O menu Financeiro descobre Taxas de câmbio e Conversões monetárias pelo mesmo
mecanismo de Moedas/Políticas, sem menu especial. Escritas exigem administrador;
permissões de lista podem ser concedidas pelo mecanismo padrão de roles.

1. Cadastre as moedas necessárias e a política da organização nas telas existentes.
2. Em `/financeiro/exchange-rates/`, selecione organização e par original → base.
   Taxa significa **quantas unidades do destino correspondem a 1 unidade original**.
   Exemplo demonstrativo: USD → BRL, 5.25. Informe data, fonte/documento e tipo
   Manual ou Contratual. Nada consulta uma taxa externa ou presume taxa oficial.
3. Em `/financeiro/conversions/`, informe organização, moeda original, valor com
   ponto e data. Escolha explicitamente a taxa da mesma organização/par/data.
   Taxa de outro dia é rejeitada; não se utiliza a última taxa automaticamente.
   Na moeda-base, deixe o seletor de taxa vazio.
4. Simular mostra o montante arredondado e não grava. Para confirmar, informe
   referência e mantenha a chave da operação. O histórico mostra valor original,
   convertido, produto antes de arredondar, política, taxa, fonte e autor.
5. Reenvio da mesma chave/dados retorna o registro existente. Mudança de dados
   com a mesma chave é conflito. Cada operação nova precisa de uma chave nova;
   a tela cria uma chave ao abrir o formulário. A chave não detecta duplicatas
   quando o usuário cria outra chave para a mesma operação.

Taxas e confirmações não possuem edição/exclusão. Corrija uma taxa cadastrando
outra e selecionando seu ID em operações futuras. Uma conversão anterior não é
recalculada. O histórico de cálculo não é lançamento contábil, pagamento ou
recebimento, e não altera o custo/saldo do Estoque.

A política inicial continua única e imutável. Mudança de moeda-base/escala/
arredondamento depende de versionamento explícito posterior. Esta entrega
não associa materiais, saldo, cotação ou pedido antigos a uma organização.

Pesquisar filtra organização e fonte/referência. As listas e a API de histórico
são paginadas em 20 registros. As opções de taxa exibem os registros cadastrados;
a validação no servidor continua obrigatória. Datas são dias civis AAAA-MM-DD,
sem inferir fuso. Autoria guarda username como fotografia, sem FK entre módulos.
