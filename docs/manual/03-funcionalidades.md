# 03 — Funcionalidades

## Banco de Levedura, Dispositivos, Receitas, Sessões

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

## Meu Perfil

Edite seus próprios dados, troque sua senha (precisa informar a senha
atual), e escolha entre tema claro ou escuro — fica salvo só pra você,
não afeta os outros usuários.

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

São os itens que aparecem no menu lateral. Você pode ativar/desativar
qualquer um, ou criar um item de menu totalmente seu (um link pra uma
página do Designer, por exemplo) em "Nova transação manual". Itens que
já vêm prontos do sistema só podem ser ativados/desativados aqui — pra
mudar o nome ou o link deles é preciso alterar o código.

## Conexões OData (administrador)

Conecte o sistema a outra fonte de dados externa (um servidor que
"fala" o protocolo OData) e veja os dados dela direto na tela, sem
precisar exportar/importar planilha. Por enquanto é só visualização —
não dá pra editar esses dados externos por aqui ainda.

## Designer Visual (administrador)

Monte uma tela do seu jeito, arrastando elementos (título, texto,
campo de formulário, botão, imagem) num quadro em branco, sem precisar
de nenhum desenvolvedor. Depois de publicar, a tela fica disponível
num link próprio, que você pode adicionar ao menu em "Catálogo de
Transações".
