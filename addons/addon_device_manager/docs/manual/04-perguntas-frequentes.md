# 04 — Perguntas Frequentes (Dispositivos)

**P: Preciso ter o equipamento físico para testar?**
R: Não — cadastre um "Dispositivo Emulado" pra simular leituras antes
de ter o hardware.

**P: O que acontece se o sistema cair com um equipamento ligado?**
R: Se você marcou esse atuador como "de risco" e definiu um valor
seguro, o próprio equipamento (ou a ponte que o controla) aplica esse
valor automaticamente — não depende do sistema estar de pé pra isso
funcionar.

**P: Posso forçar a comunicação a se reconectar sem reiniciar tudo?**
R: Sim — vá em "Monitor de Tarefas" (área administrativa) e execute a
tarefa de reconexão MQTT manualmente.
