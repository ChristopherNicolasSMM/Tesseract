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
