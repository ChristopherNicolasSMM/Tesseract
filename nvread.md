<p align="center">
  <img src="docs/imgs/logo.png" alt="Tesseract" width="100%">
</p>

<p align="center"><strong>Tesseract By Christopher N. S. M. Mauricio .'.</strong></p>


# Tesseract

O projeto que une tudo... Agora temos um Hub modular (Core + Addons + Features + Plugins) em Flask.
A fusão arquitetural de três projetos anteriores: 
- **PyTeca** (CrudGen, RBAC, versionamento)
- **BrewStation** (motor de descoberta/registro de módulos) 
- **DEVStationFlask** (transações, motor de regras, Designer drag-and-drop, OData com Lib S2MOdataPy)

*Uso inicial: gestão de cervejaria caseira.*
*Uso de longo prazo: base reaproveitável para outros sistemas.*


#### Atualizações da versão vigente:

> **Versão:** 0.0.1

> **Status atual: Páginas HTML de Core entregues.** Login, home com
> menu dinâmico (catálogo de Transações) e todas as 24 telas de CRUD
> já geradas agora renderizam de verdade — corrigido um bug que
> afetava toda tela HTML desde a Fase 4 (ChoiceLoader nunca estava
> conectado). Reset de senha de admin via CLI. Próximo: Fase 7b
> (motor de regras) ou Fase 7c (Designer visual).

---











## Licença / Autor


> **Autor:** Christopher Nicolas Santa Maria Mauricio
> **Projeto:** Tesseract Modular Python Framework

O Tesseract adota um modelo de licenciamento **Source-Available Meritocrático**. 
Acreditamos que o acesso ao código de alto nível deve ser conquistado, seja através de investimento financeiro para acelerar seus negócios, ou de investimento intelectual para fortalecer a comunidade.

### 💼 Opção A: Licenciamento Comercial
Para equipes e indivíduos que desejam utilizar o Tesseract como base para projetos fechados ou comerciais:
*   **Uso Pessoal/Estudos:** $5 USD / trimestral ou $20 USD / vitalício (inclui atualizações).
*   **Uso Comercial/Empresarial:** $100 USD / usuário (vitalício) ou $20 USD / usuário por ano.

### 🛠️ Opção B: Licenciamento Meritocrático (Work-to-Play)
Você pode adquirir licenças de uso vitalícias e gratuitas contribuindo para o desenvolvimento do Tesseract. 
Acumule **5 pontos** através de Pull Requests aprovados para ganhar 1 Licença de Usuário Vitalícia.

**Tabela de Pontuação:**
*   **1 Ponto:** Correções menores (falhas de caractere, documentação, novas legendas/idiomas por addon/plugin/tela).
*   **2 Pontos:** Melhorias de infraestrutura ou segurança básica.
*   **4 Pontos:** Correções de vulnerabilidades críticas que comprometam dados ou arquitetura.
*   **5 Pontos:** Desenvolvimento de novas funcionalidades core, Addons ou Plugins estruturais.

*Empresas são encorajadas a alocar desenvolvedores para o nosso backlog. Ao contribuir com código, a empresa não apenas melhora a ferramenta que utiliza, mas adquire licenças gratuitas para sua equipe.*

Para todos os detalhes legais, restrições de distribuição e termos de uso, consulte o arquivo [`LICENSE`](LICENSE) na raiz deste repositório.

