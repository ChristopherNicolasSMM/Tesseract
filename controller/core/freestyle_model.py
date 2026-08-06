"""
controller/core/freestyle_model.py

Modelos de referência para páginas "freestyle" — telas escritas à mão,
fora do CrudGen. São páginas VIVAS (renderizadas dentro do layout real,
com o tema ativo), não arquivos de exemplo soltos: o que você vê aqui é
exatamente o que vai acontecer na sua tela.

Rotas:
    /freestyle/             índice com os quatro modelos
    /freestyle/minimal      esqueleto mínimo
    /freestyle/abas         controle de abas
    /freestyle/consumption  consumo de dados (os três caminhos)
    /freestyle/full         galeria completa de componentes

Fluxo de consumo de dados documentado em
docs/skills/17-paginas-customizadas-fluxo-de-dados.md.
"""
from __future__ import annotations

from flask import Blueprint, render_template, request
from flask_login import login_required

freestyle_bp = Blueprint("freestyle", __name__, url_prefix="/freestyle")


@freestyle_bp.route("/", methods=["GET"])
@login_required
def home():
    """Índice — cartões linkando cada modelo."""
    return render_template("core/freestyle/index.html")


@freestyle_bp.route("/minimal", methods=["GET"])
@login_required
def minimal():
    """Esqueleto mínimo: nenhuma variável, nenhum JS.

    Quando a tela não precisa de dado do servidor no primeiro render,
    `render_template` sem argumento nenhum é o suficiente — todo o dado
    dinâmico entra depois, por JavaScript (ver /freestyle/consumption).
    """
    return render_template("core/freestyle/model_minimal.html")


@freestyle_bp.route("/abas", methods=["GET"])
@login_required
def abas():
    """Controle de abas — puramente client-side, sem dado do servidor."""
    return render_template("core/freestyle/model_abas.html")


@freestyle_bp.route("/consumption", methods=["GET"])
@login_required
def consumption():
    """Consumo de dados — demonstra COMO PASSAR VARIÁVEIS do servidor
    para a tela, e como o JavaScript continua dali.

    Por que passar `page`/`per_page`/`q` daqui, se o JavaScript busca o
    dado depois?
      - A URL vira o estado da tela: `/freestyle/consumption?page=2&q=ale`
        pode ser copiada, favoritada e compartilhada, e abre já no lugar
        certo. Se o estado só existisse em memória no JS, isso se perde.
      - O primeiro render já sai com os controles preenchidos (campo de
        busca com o termo, página atual marcada), sem "piscar" o valor
        padrão antes do JS assumir.

    Para passar MAIS variáveis, basta acrescentar no `render_template` e
    ler no template. Duas formas, com finalidades diferentes:

      1. Direto no HTML — quando o valor é conteúdo visível:
             <input value="{{ q }}">

      2. Via bloco JSON — quando o valor é configuração para o
         JavaScript. É o que fazemos abaixo com `config`: o template
         serializa num <script type="application/json"> e o JS lê de
         lá. Evita montar JavaScript por concatenação de string dentro
         do Jinja, que quebra com aspas/acentos e é vetor de XSS.

    NUNCA passe segredo por aqui (chave de API, senha de conexão): tudo
    que chega ao template chega ao navegador. Dado que exige credencial
    vai por Ação de Dado, que resolve no servidor (skill 17).
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = (request.args.get("q") or "").strip()

    # Limites defensivos: `page`/`per_page` vêm da URL, ou seja, do
    # usuário. Sem clamp, `?per_page=999999` vira uma consulta que
    # derruba a tela (e o banco, se a query for pesada).
    page = max(1, page)
    per_page = min(max(per_page, 5), 100)

    return render_template(
        "core/freestyle/model_consumption.html",
        # 1) valores soltos — usados direto no HTML
        page=page, per_page=per_page, search=search,
        # 2) bloco de configuração — consumido pelo JavaScript
        config={
            "page": page,
            "perPage": per_page,
            "search": search,
            # Endpoints ficam aqui, e não hardcoded no .js, para a mesma
            # tela poder apontar para outra entidade só trocando o
            # controller — o JavaScript não precisa saber qual é.
            "restBase": "/api/brewstation/yeast-strains",
            "optionsPlural": "yeast_strains",
            "dataActionId": None,  # preencha com o id de uma Ação de Dado
        },
    )


@freestyle_bp.route("/full", methods=["GET"])
@login_required
def full():
    """Galeria completa de componentes."""
    return render_template("core/freestyle/model_full.html")
