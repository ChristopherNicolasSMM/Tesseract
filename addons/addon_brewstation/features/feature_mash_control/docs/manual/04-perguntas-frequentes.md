# 04 — Perguntas Frequentes (Controle de Mostura)

**P: Cadastrei uma regra de automação, ela já liga/desliga sozinha?**
R: Sim — assim que uma leitura chega do sensor vinculado, a regra é
avaliada e, se a condição for verdadeira, a ação é disparada
automaticamente. Você pode acompanhar cada disparo no histórico da
própria regra.

**P: Minha regra não está disparando, o que confiro primeiro?**
R: Confirme que o sensor e o atuador da regra estão corretamente
vinculados a Funções de Dispositivo existentes, e que o dispositivo
está mesmo enviando leituras (veja em "Dispositivos" se a última
leitura é recente).

**P: O que acontece se o sistema cair enquanto um atuador de
aquecimento está ligado?**
R: Se esse atuador foi marcado como "de risco" na área de Dispositivos
(com um valor seguro definido), ele é desligado automaticamente pelo
próprio equipamento/ponte de controle, mesmo sem o sistema estar de
pé — não depende da automação daqui pra isso funcionar.

**P: Existe um loop de controle automático de temperatura (tipo
termostato) durante a mostura?**
R: Os parâmetros pra isso (ex.: ganhos de um controlador PID) já
podem ser configurados na etapa da sessão, mas o loop de controle em
tempo real ainda não foi ativado nesta versão — hoje a reação
automática acontece via Regras de Automação (evento → condição →
ação), não um controlador contínuo.

**P: Editei uma etapa em "Gerenciar Etapas" no Dashboard e não vejo a
mudança na brassagem em andamento — por quê?**
R: Aquele formulário edita a **receita** (o modelo, reaproveitável em
futuras sessões), não a sessão que já está rodando. Clique em
"Ressincronizar com a sessão" pra essa mudança aparecer na brassagem
atual — uma etapa já concluída ou em andamento nunca é sobrescrita
por esse botão, só as que ainda não começaram.

**P: O botão "Voltar" do Card de Etapa desfaz exatamente o tempo que
já tinha passado?**
R: Não — ele reativa a etapa anterior com o timer **reiniciado do
zero**, não reconstrói o tempo exato que já tinha se passado antes de
avançar. É pra usar como um "deixa eu refazer esta etapa", não como
um desfazer preciso.
