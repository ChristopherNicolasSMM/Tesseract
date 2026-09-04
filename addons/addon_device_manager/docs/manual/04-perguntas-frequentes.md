# 04 — Perguntas Frequentes (Dispositivos)

**P: Preciso ter o equipamento físico para testar?**
R: Não — cadastre um "Dispositivo Emulado" pra simular leituras antes
de ter o hardware.

**P: Cadastrei tudo mas as leituras do sensor não chegam sozinhas.**
R: Confira se `MQTT_ENABLED=true` está no `.env` e se o sistema foi
reiniciado depois dessa mudança — a conexão MQTT só abre na subida.
Sem isso ligado, os cadastros funcionam, mas nada troca mensagem de
verdade com o broker.

**P: Preciso preencher o "Config Json" do Ator?**
R: Não, é opcional. Sem ele, o sistema usa um tópico MQTT gerado
automaticamente (funciona igual). Só preencha se você quiser um nome
de tópico específico, mais fácil de reconhecer olhando o broker
direto.

**P: O que acontece se o sistema cair com um equipamento ligado?**
R: Se você marcou esse atuador como "de risco" e definiu um valor
seguro, o próprio equipamento (ou a ponte que o controla) aplica esse
valor automaticamente — não depende do sistema estar de pé pra isso
funcionar.

**P: Posso forçar a comunicação a se reconectar sem reiniciar tudo?**
R: Sim — vá em "Monitor de Tarefas" (área administrativa) e execute a
tarefa de reconexão MQTT manualmente.
