# 03 — Funcionalidades

## Banco de Levedura, Dispositivos, Receitas, Sessões, Ingredientes, Envase, Estoque

Cada área segue o mesmo padrão: lista de registros, um botão "+" pra
cadastrar um novo (o formulário fica escondido até você clicar), busca
por texto, filtros (quando o campo tiver opções fixas, vira uma
caixinha de seleção), botão "Colunas" pra escolher o que aparece na
tabela (só pra você, fica salvo), e botões de exportar pra CSV/Excel.
Em cada registro você pode editar, mover pra lixeira, restaurar, ou
excluir de vez (só depois de já estar na lixeira).

## Recalcular Viabilidade (Banco de Levedura)

Recalcula a viabilidade estimada de todas as suas cepas guardadas de
uma vez, usando a leitura mais recente disponível (preferindo sempre
uma contagem real, depois estimada, depois um starter, e por último o
valor inicial cadastrado da cepa).

## Automação de Brassagem (Sessões)

Ao vincular sensores e atuadores a uma planta de brassagem, o sistema
passa a reagir sozinho às leituras — por exemplo, desligar a
resistência assim que a temperatura alvo é atingida, sem você precisar
ficar olhando o painel o tempo todo. As regras de automação ficam
visíveis e editáveis junto com a receita/sessão.

## Estoque

Cadastre materiais (com fabricante, origem, tipo e categoria),
registre composições (um material feito a partir de outros), lance
movimentações de entrada/saída, e acompanhe o saldo atualizado
automaticamente a cada movimentação.

## Meu Perfil

Edite seus próprios dados, troque sua senha (precisa informar a senha
atual), e escolha entre tema claro ou escuro — fica salvo só pra você,
não afeta os outros usuários. Também é aqui que você ajusta sua
preferência pessoal de menu.

## Gestão de Usuários (administrador)

Cadastre usuários, edite dados, atribua Papéis, redefina senha de
qualquer um, e ative/desative acesso.

## Papéis e Permissões (administrador)

Crie grupos de acesso (Papéis) e marque quais permissões cada um tem,
organizadas por área do sistema. Depois, atribua o Papel a um ou mais
usuários em "Gestão de Usuários".

## Versionamento (administrador)

Toda vez que uma tela/funcionalidade é gerada ou alterada pelo
sistema, uma cópia da versão anterior fica guardada. Em
"Versionamento" você vê o histórico, compara duas versões lado a lado,
e pode voltar pra uma versão anterior se precisar.

## Regras de Campo (administrador)

Anexe validações a qualquer campo de qualquer cadastro — por exemplo,
"obrigatório", "tamanho mínimo", "formato de e-mail", "CPF válido".
A validação aparece na hora, antes mesmo de salvar.

## Catálogo de Transações (administrador)

São os itens que aparecem no menu lateral, organizados em árvore
(grupos podem ter sub-grupos). Você pode ativar/desativar qualquer
um, promover/rebaixar de nível, ou criar um item de menu totalmente
seu (um link pra uma página do Designer, por exemplo) em "Nova
transação manual". Itens que já vêm prontos do sistema só podem ser
ativados/desativados aqui — pra mudar o nome ou o link deles é preciso
alterar o código.

## Configurações de Menu (administrador)

Define o padrão global de menu pra todo mundo que não tiver ajustado a
própria preferência: ordem dos itens (arrastar e soltar), quais grupos
começam recolhidos, se a barra lateral inicia aberta ou fechada, e até
que nível da árvore os ícones aparecem (útil pra deixar um menu muito
profundo mais limpo visualmente).

## Conexões OData (administrador)

Conecte o sistema a outra fonte de dados externa (um servidor que
"fala" o protocolo OData) e veja os dados dela direto na tela, sem
precisar exportar/importar planilha. Por enquanto é só visualização —
não dá pra editar esses dados externos por aqui ainda. Se o nome de
uma entidade não bater com a URL real do servidor, dá pra corrigir na
mão, direto na tela.

## Model Builder Visual (administrador)

Cria um cadastro novo (tabela + tela completa) sem escrever código —
escolhe em qual área do sistema ele vai morar (ou cria uma área nova),
define os campos um a um, e gera. Pode nascer do zero, ou a partir de
uma resposta de API testada no Playground (veja abaixo).

## Playground de API/SQL (administrador)

Uma ferramenta pra testar chamadas de API externas (com usuário/senha,
token, ou chave de API) e consultas SQL somente-leitura, sem precisar
de um programa separado no computador. As requisições ficam
organizadas em pastas, dá pra arquivar as que não usa mais, e a
resposta de uma chamada HTTP pode virar direto os campos de um
cadastro novo no Model Builder.

## Logs (administrador)

Consulta o registro de eventos do sistema — tanto o log geral quanto
os logs específicos de integração de cada área (por exemplo, mensagens
trocadas com o broker MQTT dos dispositivos).

## Tarefas Agendadas (administrador)

Programa uma ação pra rodar sozinha, de tempos em tempos ou num
horário fixo — chamar uma rotina do sistema, uma URL, ou uma consulta
SQL. Acompanha se cada execução deu certo, e quanto tempo levou.

## Designer Visual (administrador)

Monte uma tela do seu jeito, arrastando elementos (título, texto,
campo de formulário, botão, imagem) num quadro em branco, sem precisar
de nenhum desenvolvedor. Depois de publicar, a tela fica disponível
num link próprio, que você pode adicionar ao menu em "Catálogo de
Transações".
