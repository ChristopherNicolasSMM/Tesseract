# 04 — Perguntas Frequentes (Yeast Bank)

**P: O que são os "parâmetros de viabilidade"?**
R: São números usados para estimar quanto a cepa perde de força ao
longo do tempo. Se você não souber os valores certos, pode deixar no
padrão sugerido pelo sistema.

**P: Cadastrei a cepa errada, como removo?**
R: Mova para a lixeira primeiro. Se tiver certeza que quer remover de
vez, é possível excluir permanentemente só depois disso.

**P: Como o sistema decide qual referência usar no cálculo de
viabilidade?**
R: Segue uma ordem de prioridade: contagem de célula real primeiro
(mais confiável), depois uma estimativa anterior, depois um starter
registrado, e por último o valor inicial cadastrado da cepa. Se não
achar nenhuma referência, o item fica marcado como "sem referência".

**P: Um item marcado como contaminado ainda entra no cálculo?**
R: Não — itens descartados ou contaminados são sempre ignorados no
recálculo de viabilidade.

**P: Marquei "Contaminação Detectada" numa Contagem de Célula — o que
isso muda?**
R: Só aquela leitura específica deixa de contar como referência pro
cálculo de viabilidade — o sistema pula pra próxima disponível
(estimativa anterior, depois starter, depois valor inicial da cepa).
O Item em si continua "Ativo" normalmente; se você quiser marcar o
Item inteiro como contaminado, isso é outra coisa — feito via Evento
do Banco tipo "Descarte", escolhendo "Contaminado".

**P: Por que não consigo criar um Item do Banco sem escolher um
Container?**
R: Todo Item precisa estar dentro de um Container, e todo Container
precisa estar dentro de um Dispositivo — é assim que o sistema sabe
onde fisicamente cada amostra está guardada. Cadastre nessa ordem:
Dispositivo → Container → Item.

**P: Um Container pode ficar em mais de um Dispositivo, ou vice-versa?**
R: Não. Cada Container pertence a exatamente um Dispositivo, mas um
Dispositivo pode ter quantos Containers você quiser (várias caixas
dentro do mesmo freezer, por exemplo).

**P: Como faço pra mover um item de um Container pra outro?**
R: Edite o Item do Banco e troque o Container selecionado — o
histórico do item (starters, contagens) continua vinculado normalmente,
só a localização física muda.

**P: Por que não existe mais uma tela própria de "Starters"?**
R: O Starter deixou de ser um registro separado — agora é só um tipo
de Evento do Banco. Crie um evento tipo "Starter" e preencha os
campos (data, volume, objetivo) direto ali; editar um starter já
registrado também é editar o evento dele.

**P: O que acontece se eu não cadastrar uma Configuração do Banco pro
tipo de armazenamento?**
R: Nada quebra — o sistema usa o decaimento cadastrado na Cepa (como
sempre foi) e você preenche a data de validade manualmente. A
Configuração do Banco é opcional, só ajuda a automatizar quando você
quiser.

**P: Dá pra ter mais de uma Configuração do Banco pro mesmo tipo de
armazenamento?**
R: Não — só uma configuração ativa por tipo. Se tentar criar uma
segunda pro mesmo tipo, o sistema recusa.

**P: Ao criar um Evento tipo "Descarte", o status do Item realmente
muda?**
R: Sim — diferente dos outros tipos de evento, "Descarte" aplica a
mudança de verdade no Item (pra Descartado ou Contaminado, você
escolhe). O status anterior fica registrado sozinho no evento, como
histórico. Se você não escolher entre Descartado/Contaminado, o
padrão é Descartado.

**P: O aviso de vencimento/viabilidade baixa manda alguma notificação?**
R: Não — é só um sinal na tela do próprio item, calculado na hora que
você olha (não fica desatualizado, mas também não avisa proativamente
por e-mail ou push).

**P: Como o Painel calcula "quantos dias pro próximo starter"?**
R: É uma estimativa, não um agendamento — pega a viabilidade atual do
item, o quanto ela cai por dia (da Configuração do Banco, ou da cepa
se não tiver config), e calcula quantos dias faltam até cruzar a
viabilidade mínima cadastrada na Configuração do Banco. Se já cruzou,
mostra "Agora". Se não tiver Configuração do Banco cadastrada pro
tipo de armazenamento, ou nenhum decaimento configurado (nem na
config, nem na cepa), o campo fica vazio — não tem base pra estimar.

**P: Como o sistema calcula células/mL a partir da contagem na câmara
de Neubauer?**
R: células/mL = (vivas + mortas) × (25 / quadrados contados) × fator
de diluição × 10.000; viabilidade% = vivas × 100 / (vivas + mortas).
É a fórmula padrão de contagem em câmara de Neubauer (prática
cervejeira usual: contar 5 dos 25 quadrados centrais). Só calcula
automaticamente se você preencher os campos brutos (vivas, mortas,
quadrados, diluição) — se preferir, pode digitar o resultado final
direto, sem passar pelos campos brutos.
