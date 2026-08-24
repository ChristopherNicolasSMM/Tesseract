# 02 — Primeiros Passos (Yeast Bank)

A tela só deixa você avançar depois que o passo anterior existe — por
isso a ordem abaixo importa. Cadastrar fora dessa ordem não funciona:
por exemplo, não dá pra criar um Container sem escolher um
Dispositivo, nem um Item sem escolher um Container.

## Ordem de cadastro

1. **Dispositivo de Armazenamento** — cadastre primeiro o freezer,
   geladeira ou câmara fria onde as amostras vão ficar.
2. **Cepa** — cadastre a cepa de levedura em si (nome, família,
   fornecedor). Pode fazer isso em paralelo ao passo 1, não depende
   dele.
3. **Container** — dentro do Dispositivo que você acabou de
   cadastrar, crie o Container: a caixa, estante ou prateleira onde
   as amostras dessa cepa (ou de outras) vão ficar organizadas.
4. **Item do Banco** — agora sim, registre o item físico: escolha a
   Cepa e o Container onde ele vai ficar, e preencha data de preparo.
   Se você tiver cadastrado uma Configuração do Banco (passo
   opcional, ver `03-funcionalidades.md`) pro tipo de armazenamento
   escolhido, a data de validade é preenchida sozinha.
5. **Starter/Contagem de Célula** (quando precisar) — vá em "Eventos
   do Banco", crie um evento novo escolhendo o tipo (Starter ou
   Contagem de Células) e o Item de origem. O sistema já cria o
   registro certo e te leva direto pra edição dele.

## Passo a passo na tela

1. Acesse "Banco de Levedura" no menu.
2. Em "Dispositivos", clique em "Novo" e cadastre o freezer/geladeira.
3. Em "Cepas", clique em "Nova Cepa" e preencha pelo menos o nome
   (ex.: "US-05").
4. Em "Containers", clique em "Novo", escolha o Dispositivo do passo 2
   e dê um nome pro Container (ex.: "Caixa 1", "Estante A").
5. Em "Itens do Banco", clique em "Novo", escolha a Cepa e o Container
   que você acabou de criar.
6. Sempre que fizer um starter ou uma contagem com esse item, vá em
   "Eventos do Banco" → "Novo evento", escolha o tipo certo — o
   sistema cria o registro especializado e já abre a edição dele.

## Se você já usava o sistema antes

Itens que já existiam antes do Container ser introduzido foram
organizados automaticamente: o sistema criou um Container chamado
"[Nome do Dispositivo] — Geral" para cada dispositivo que já tinha
itens, e moveu esses itens pra lá. Você pode reorganizá-los em
Containers mais específicos quando quiser — não é obrigatório.
