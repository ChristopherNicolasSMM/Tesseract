# 04 — Perguntas Frequentes

**P: Esqueci minha senha, e agora?**
R: Peça para um administrador redefinir em "Gestão de Usuários", ou
mude você mesmo em "Meu Perfil" se ainda conseguir entrar.

**P: Por que não vejo todas as áreas que outro colega vê?**
R: Cada usuário só vê as áreas em que tem permissão. Peça para um
administrador revisar seu Papel em "Papéis e Permissões".

**P: Apaguei um registro por engano, perdi os dados?**
R: Se você usou "mover para lixeira", não — é só restaurar. Se foi
"excluir permanentemente", os dados são removidos de verdade e não há
como recuperar.

**P: O tema escuro não ficou salvo?**
R: O tema é salvo por usuário — confira se você está logado com o
mesmo usuário de antes.

**P: Posso desfazer uma alteração feita pelo sistema (geração de tela,
por exemplo)?**
R: Se você for administrador, sim — em "Versionamento" você encontra o
histórico e pode restaurar uma versão anterior.

**P: Reorganizei o menu e não gostei — dá pra voltar como estava?**
R: Se foi sua preferência pessoal (em "Meu Perfil"), sim, é só ajustar
de novo do jeito que quiser. Se foi o padrão global (administrador em
"Configurações de Menu"), a mudança afeta todo mundo que não tiver
preferência própria — vale ajustar com calma.

**P: Testei uma chamada no Playground e deu erro 404, mas funciona no
Postman — o que pode ser?**
R: Confira se os parâmetros da URL foram colocados no campo "Query
Params" (não colados direto na URL) e se a Autenticação foi preenchida
na aba própria, não misturada nos Headers livres.

**P: Conectei um servidor OData e a navegação de uma entidade dá
erro, mesmo a conexão funcionando?**
R: O nome da entidade que o servidor expõe pode ser diferente do
nome interno dele (por exemplo, "Pedido" no cadastro mas "Pedidos" na
URL real). Corrija o nome da rota direto na tela "Ver entidades".
