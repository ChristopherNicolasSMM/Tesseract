# 01 — Introdução

O Yeast Bank é onde você cadastra e acompanha suas cepas de levedura
— nome, fornecedor, família, e os parâmetros usados para estimar a
viabilidade de cada lote ao longo do tempo. Além da cepa em si, você
registra os itens guardados de fato (congelados, slants), leituras de
temperatura do local de armazenamento, starters feitos, e contagens
de célula — tudo isso alimenta o cálculo automático de viabilidade.

## Como as coisas se conectam

Pensando fisicamente, é a mesma organização que você já usa na
cervejaria:

1. Você tem um **Dispositivo** — um freezer, uma geladeira, uma
   câmara fria.
2. Dentro desse dispositivo, você organiza **Containers** — caixas,
   estantes, prateleiras. É a "gaveta" onde as amostras ficam de
   fato.
3. Dentro de um Container, você guarda **Itens do Banco** — cada
   slant, cada tubo, cada amostra congelada de uma cepa específica.
4. A partir de um Item do Banco, você registra **Starters**
   (propagações) e **Contagens de Célula** (contagem real, ao
   microscópio).

Ou seja: o Dispositivo guarda Containers, o Container guarda Itens, e
o Item é a origem de Starters e Contagens. Cada nível só existe dentro
do nível anterior — não dá pra guardar um Item sem já ter escolhido em
qual Container ele vai, do mesmo jeito que na vida real você não bota
uma amostra numa caixa que ainda não existe.

