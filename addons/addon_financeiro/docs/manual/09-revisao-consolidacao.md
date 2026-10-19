# Revisão da consolidação e evidências de fechamento

O Financeiro mantém uma única entrada de workspace. Em **DRE e resultados**, o botão **Dashboard de resultados** permite voltar ao painel sem trocar de área ou reconstruir os filtros de organização e período.

As visões carregam os dados que apresentam. Custos não dependem do carregamento do histórico de apropriações ou do catálogo inteiro de categorias; Fechamento carrega seu próprio histórico. O histórico de apropriações continua paginado e as classificações e centros necessários ao formulário continuam disponíveis.

O cabeçalho de organização e datas é validado em todas as visões de Resultados. Se houver erro, corrija o contexto informado. A rejeição não grava o contexto inválido na sessão. Históricos e cadastros continuam independentes do recorte temporal: validar o cabeçalho não passa a filtrá-los por data.

## Conferir e exportar um fechamento

Abra **Conferência e fechamento** e expanda a versão desejada. O sistema recalcula o checksum do snapshot e informa se ele corresponde ao checksum registrado. Se houver divergência, mostra um aviso no próprio registro, preservando os dados para investigação. A conferência não corrige nem regrava evidências automaticamente.

Use **Exportar registro de fechamento (JSON)** para guardar o snapshot e seus metadados: organização, competência, versão, autor, motivo, declarações, checksum, situação de reabertura e resultado da conferência de integridade. A exportação representa a versão selecionada, inclusive quando ela já foi reaberta. Não recalcula a DRE usando dados posteriores.

A conferência cobre o conteúdo do snapshot e detecta divergências em relação ao checksum armazenado. Ela não é assinatura digital ou certificação contábil. A leitura exige a permissão de Resultados e o fechamento deve pertencer à organização explicitamente selecionada.

Esta atualização não exige nova migração. Reinicie a aplicação depois de aplicar o patch.
