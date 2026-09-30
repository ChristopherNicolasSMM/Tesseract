# Alinhamento da tela de login

O template `templates/core/base_no_login.html` carregava `style.css` e usava
`#main`, o mesmo identificador do layout autenticado. Esse seletor aplica
`margin-top: 60px` para o cabeçalho e, a partir de 1200 px, `margin-left: 300px`
para a sidebar. Sem esses elementos, o login ficava deslocado para a direita.

O layout público agora usa `body.auth-page` e `main.auth-main`, com estilos
próprios em `static/css/auth_layout.css`. A altura mínima é a da janela e o
conteúdo ocupa o espaço disponível acima do rodapé. A linha do formulário
deixa de impor `90vh`, evitando somar essa altura às margens e ao rodapé.
Quando o conteúdo cresce ou a janela é baixa, a página pode rolar normalmente.

O CSS do layout autenticado e o comportamento de autenticação permanecem
inalterados. Não há alteração de banco ou migration.

Para verificar visualmente, abrir `/login` abaixo e acima de 1200 px de
largura, em uma janela baixa e em dispositivo móvel. O formulário deve ficar
centralizado horizontalmente, sem reserva para sidebar, e continuar acessível
por rolagem quando necessário. Conferir também a mensagem de erro e uma
página autenticada para verificar o isolamento dos estilos.
