# 02 — Primeiros Passos (Controle de Mostura)

1. Abra **Workspace de Planta**. Cadastre a Planta ali e, na aba
   **Planta**, adicione os Tanques (panela de mostura, caldeira de
   fervura, fermentador...). O número mostrado representa os tanques
   cadastrados, não a capacidade planejada no cadastro.
2. Se tiver sensores/atuadores, na mesma aba selecione **Tanque**,
   **Papel** e uma **Função de Dispositivo** compatível para criar o
   mapeamento (ex.: sensor de temperatura no tanque de mostura).
3. Cadastre uma Receita — direto, ou importada do BrewFather (ver
   manual de Integração BrewFather).
4. Se quiser automação, crie uma Regra de Automação (ex.: "se a
   temperatura do tanque cair abaixo de X, ligue o aquecedor").
5. Na aba **Dashboard**, crie o primeiro layout da Planta. Depois
   entre em "Modo Edição" e arraste da paleta os elementos que quiser (card de
   Etapa pra ver o progresso da brassagem, Tanques pros tanques,
   Gráficos/Botões pros sensores e atuadores), clique em cada um pra
   ligá-lo ao sensor/atuador certo no painel lateral, e ligue a
   tubulação entre os tanques se quiser ver o fluxo animado.
6. Na aba **Receita**, escolha a receita. Se ela já foi usada, crie uma
   revisão para os próximos lotes. Abra **Sanear ingrediente** para conferir
   vínculo, decisão de consumo e dados planejados. Salvar não baixa estoque.
7. Confira a timeline e gere a Sessão; o lote criado abre selecionado na aba
   **Sessões**. Confirme os ingredientes somente pela ação explícita do lote.
