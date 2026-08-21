# 02 — Primeiros Passos (Yeast Bank)

A tela só deixa você avançar depois que o passo anterior existe — por
isso a ordem abaixo importa. Cadastrar fora dessa ordem não funciona:
por exemplo, não dá pra criar um Container sem escolher um
Dispositivo, nem um Item sem escolher um Container.

## Ordem de cadastro

1. **Dispositivo de Armazenamento** — cadastre primeiro o freezer,
   geladeira ou câmara fria onde as amostras vão ficar. Se ele tiver
   sensor de temperatura, as leituras entram automaticamente depois.
2. **Cepa** — cadastre a cepa de levedura em si (nome, família,
   fornecedor). Pode fazer isso em paralelo ao passo 1, não depende
   dele.
3. **Container** — dentro do Dispositivo que você acabou de
   cadastrar, crie o Container: a caixa, estante ou prateleira onde
   as amostras dessa cepa (ou de outras) vão ficar organizadas.
4. **Item do Banco** — agora sim, registre o item físico: escolha a
   Cepa e o Container onde ele vai ficar, e preencha data de preparo,
   validade, etc.
5. **Starter** (quando fizer uma propagação) — registre vinculado ao
   Item do Banco de origem.
6. **Contagem de Célula** (quando tiver uma contagem real, ao
   microscópio) — vincule ao Item e, se veio de um Starter, ao
   Starter também.

## Passo a passo na tela

1. Acesse "Banco de Levedura" no menu.
2. Em "Dispositivos", clique em "Novo" e cadastre o freezer/geladeira.
3. Em "Cepas", clique em "Nova Cepa" e preencha pelo menos o nome
   (ex.: "US-05").
4. Em "Containers", clique em "Novo", escolha o Dispositivo do passo 2
   e dê um nome pro Container (ex.: "Caixa 1", "Estante A").
5. Em "Itens do Banco", clique em "Novo", escolha a Cepa e o Container
   que você acabou de criar.
6. Sempre que fizer um starter com essa cepa, registre em "Starters",
   vinculado ao Item correspondente — é outra fonte de referência pro
   cálculo de viabilidade.

## Se você já usava o sistema antes

Itens que já existiam antes do Container ser introduzido foram
organizados automaticamente: o sistema criou um Container chamado
"[Nome do Dispositivo] — Geral" para cada dispositivo que já tinha
itens, e moveu esses itens pra lá. Você pode reorganizá-los em
Containers mais específicos quando quiser — não é obrigatório.
