"""
addons/addon_estoque/root/services/estoque_service.py

API pública rica do addon_estoque, além do CRUD genérico já gerado em
material_service.py/movimentacao_service.py/saldo_service.py. Não é
gerado pelo CrudGen (mesmo papel de device_service.py em
addon_device_manager) — é o ponto de extensão estável para a lógica
de negócio (registrar movimentação + atualizar saldo em conjunto).

Regra de negócio: toda movimentação passa por aqui, nunca por INSERT
direto em Movimentacao a partir de outro módulo — é este service que
garante Movimentacao (ledger) e Saldo (cache) ficarem consistentes na
mesma operação.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from addons.addon_estoque.root.model.saldo import Saldo

TIPOS_VALIDOS = ("entrada", "saida", "ajuste")


class MaterialNaoEncontradoError(Exception):
    pass


class TipoMovimentacaoInvalidoError(Exception):
    pass


def _get_or_create_saldo(material_id: int) -> Saldo:
    saldo = Saldo.query.filter_by(material_id=material_id).first()
    if saldo is None:
        saldo = Saldo(material_id=material_id, quantidade_atual=0.0)
        db.session.add(saldo)
        db.session.flush()
    return saldo


def registrar_movimentacao(
    material_id: int,
    tipo_movimentacao: str,
    quantidade: float,
    *,
    custo_unitario: float | None = None,
    lote_fornecedor: str | None = None,
    data_validade=None,
    usuario_id: int | None = None,
    observacoes: str | None = None,
    fornecedor_id: int | None = None,
    pedido_compra_item_id: int | None = None,
    unidade_original: str | None = None,
    quantidade_original: float | None = None,
    fator_conversao_aplicado: float | None = None,
) -> dict:
    """
    Registra uma Movimentacao (ledger, imutável) e atualiza o Saldo
    (cache) na mesma transação. "ajuste" pode ser positivo (entrada
    corretiva) ou negativo (saída corretiva) — quantidade aceita
    qualquer sinal só para tipo_movimentacao="ajuste"; "entrada"/
    "saida" exigem quantidade >= 0 (o sinal é dado pelo tipo).

    `fornecedor_id`/`pedido_compra_item_id`/`unidade_original`/
    `quantidade_original`/`fator_conversao_aplicado` (skill 23, Fase 4)
    são todos opcionais — só preenchidos quando a movimentação vem de
    receber_pedido_compra(); movimentação manual continua funcionando
    sem nenhum deles. Quando `fornecedor_id` é passado numa entrada,
    Saldo.ultimo_preco_compra/ultimo_fornecedor_id/data_ultima_compra
    são atualizados (cache de última compra).

    Retorna dict primitivo (nunca o objeto ORM) — mesma regra de
    fronteira usada em device_manager (skill 05, seção 6).
    """
    if tipo_movimentacao not in TIPOS_VALIDOS:
        raise TipoMovimentacaoInvalidoError(
            f"tipo_movimentacao deve ser um de {TIPOS_VALIDOS}, recebido: {tipo_movimentacao!r}"
        )

    material = Material.query.filter_by(id=material_id, is_deleted=False).first()
    if material is None:
        raise MaterialNaoEncontradoError(f"Material id={material_id} não encontrado ou removido")

    if tipo_movimentacao in ("entrada", "saida") and quantidade < 0:
        raise ValueError("quantidade não pode ser negativa para entrada/saida — use tipo_movimentacao='ajuste'")

    custo_total = (custo_unitario * quantidade) if custo_unitario is not None else None

    movimentacao = Movimentacao(
        material_id=material_id,
        tipo_movimentacao=tipo_movimentacao,
        quantidade=quantidade,
        custo_unitario=custo_unitario,
        custo_total=custo_total,
        lote_fornecedor=lote_fornecedor,
        data_validade=data_validade,
        data_movimentacao=datetime.now(timezone.utc),
        usuario_id=usuario_id,
        observacoes=observacoes,
        fornecedor_id=fornecedor_id,
        pedido_compra_item_id=pedido_compra_item_id,
        unidade_original=unidade_original,
        quantidade_original=quantidade_original,
        fator_conversao_aplicado=fator_conversao_aplicado,
    )
    db.session.add(movimentacao)

    saldo = _get_or_create_saldo(material_id)

    if tipo_movimentacao == "entrada":
        _aplicar_entrada(saldo, quantidade, custo_unitario)
    elif tipo_movimentacao == "saida":
        saldo.quantidade_atual -= quantidade
    else:  # ajuste — sinal já vem embutido em quantidade
        if quantidade > 0 and custo_unitario is not None:
            _aplicar_entrada(saldo, quantidade, custo_unitario)
        else:
            saldo.quantidade_atual += quantidade

    if saldo.custo_medio is not None:
        saldo.valor_total_estoque = saldo.quantidade_atual * saldo.custo_medio
    saldo.ultima_atualizacao = datetime.now(timezone.utc)

    if tipo_movimentacao == "entrada" and fornecedor_id is not None:
        saldo.ultimo_preco_compra = custo_unitario
        saldo.ultimo_fornecedor_id = fornecedor_id
        saldo.data_ultima_compra = datetime.now(timezone.utc).date()

    db.session.commit()

    return {
        "movimentacao": movimentacao.to_dict(),
        "saldo": saldo.to_dict(),
    }


def _aplicar_entrada(saldo: Saldo, quantidade: float, custo_unitario: float | None) -> None:
    """Custo médio ponderado: (saldo_atual*custo_medio_atual + entrada*custo_entrada) / (saldo_atual+entrada)."""
    quantidade_anterior = saldo.quantidade_atual
    custo_medio_anterior = saldo.custo_medio or 0.0

    saldo.quantidade_atual = quantidade_anterior + quantidade

    if custo_unitario is not None and saldo.quantidade_atual > 0:
        valor_anterior = quantidade_anterior * custo_medio_anterior
        valor_entrada = quantidade * custo_unitario
        saldo.custo_medio = (valor_anterior + valor_entrada) / saldo.quantidade_atual


def consultar_saldo(material_id: int) -> dict | None:
    saldo = Saldo.query.filter_by(material_id=material_id).first()
    return saldo.to_dict() if saldo else None


class PedidoCompraNaoEncontradoError(Exception):
    pass


class PedidoCompraStatusInvalidoError(Exception):
    pass


def receber_pedido_compra(
    pedido_compra_id: int,
    *,
    usuario_id: int | None = None,
    dados_por_item: dict[int, dict] | None = None,
) -> dict:
    """
    Recebimento (skill 23, Fase 4; correção Entrada de Mercadoria —
    achado do Christopher, sessão pós skill 24) — SEMPRE total nesta
    fase (decisão explícita, mantida na correção: recebimento parcial
    fica pra quando o volume real de uso justificar). Transiciona
    PedidoCompra.status para "recebido" e gera uma Movimentacao de
    entrada por ItemPedidoCompra via registrar_movimentacao() (nunca
    INSERT direto), preservando a regra de que toda movimentação passa
    por lá.

    `dados_por_item` (novo): dict opcional `{item_pedido_compra_id:
    {"lote_fornecedor": str|None, "data_validade": date|None}}` — a
    tela de Entrada de Mercadoria captura isso por item (sempre
    disponível pra preencher, nunca obrigatório — decisão de sessão).
    Item sem entrada no dict, ou dict ausente inteiro, recebe sem
    lote/validade (mesmo comportamento de antes desta correção).

    custo_unitario da Movimentacao é sempre por UNIDADE-BASE do
    Material (preco_unitario do item, que é por unidade de compra,
    dividido pelo fator_conversao_aplicado) — mantém
    Saldo.custo_medio consistente com o resto do sistema, que já
    calcula tudo em unidade-base.

    Só é permitido a partir de status="confirmado" — replica a máquina
    de estado documentada na skill 23 (rascunho -> enviado ->
    confirmado -> recebido).
    """
    from addons.addon_estoque.root.model.pedido_compra import PedidoCompra

    pedido = PedidoCompra.query.filter_by(id=pedido_compra_id, is_deleted=False).first()
    if pedido is None:
        raise PedidoCompraNaoEncontradoError(f"PedidoCompra id={pedido_compra_id} não encontrado ou removido")

    if pedido.status != "confirmado":
        raise PedidoCompraStatusInvalidoError(
            f"Só é possível receber um pedido com status='confirmado' (atual: {pedido.status!r})"
        )

    itens = [i for i in pedido.itens if not i.is_deleted]
    if not itens:
        raise ValueError(f"PedidoCompra id={pedido_compra_id} não tem itens para receber")

    dados_por_item = dados_por_item or {}

    movimentacoes = []
    for item in itens:
        fator = item.fator_conversao_aplicado or 1.0
        custo_unitario_base = item.preco_unitario / fator if fator else item.preco_unitario
        extra = dados_por_item.get(item.id, {})

        resultado = registrar_movimentacao(
            item.material_id,
            "entrada",
            item.quantidade_convertida_base or (item.quantidade * fator),
            custo_unitario=custo_unitario_base,
            usuario_id=usuario_id,
            observacoes=f"Recebimento do pedido de compra {pedido.numero}",
            fornecedor_id=pedido.fornecedor_id,
            pedido_compra_item_id=item.id,
            unidade_original=item.material_unidade.unidade if item.material_unidade else None,
            quantidade_original=item.quantidade,
            fator_conversao_aplicado=fator,
            lote_fornecedor=extra.get("lote_fornecedor") or None,
            data_validade=extra.get("data_validade") or None,
        )
        movimentacoes.append(resultado["movimentacao"])

    pedido.status = "recebido"
    pedido.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return {
        "pedido_compra": pedido.to_dict(),
        "movimentacoes": movimentacoes,
    }


class ItemCotacaoNaoEncontradoError(Exception):
    pass


def selecionar_item_cotacao_vencedor(item_cotacao_id: int) -> dict:
    """
    Marca um ItemCotacao como vencedor (skill 24, Fase 6.2). Regra de
    negócio central da tela de Comparação: no máximo um vencedor por
    ItemProcessoCotacao (o "item pedido" — Material+quantidade
    definidos uma vez no processo, ver model/item_processo_cotacao.py)
    — atravessa Cotacao (fornecedores diferentes), então não dá pra
    ser índice único de banco. Validado aqui: qualquer outro
    ItemCotacao respondendo ao MESMO item_processo_cotacao_id, em
    qualquer Cotacao do mesmo processo, é desmarcado antes de marcar o
    novo vencedor — a troca é atômica (mesma transação).

    CORREÇÃO (achado do Christopher, sessão pós-Fase 6.3): antes
    agrupava por nome de Material (frágil - ItemCotacao tinha
    material_id próprio, digitado de novo em cada Cotacao). Agora
    agrupa pela FK real item_processo_cotacao_id, que já garante ser o
    mesmo item pedido - não precisa mais de JOIN com Cotacao pra
    filtrar por Material.
    """
    from addons.addon_estoque.root.model.item_cotacao import ItemCotacao

    item = ItemCotacao.query.filter_by(id=item_cotacao_id, is_deleted=False).first()
    if item is None:
        raise ItemCotacaoNaoEncontradoError(f"ItemCotacao id={item_cotacao_id} não encontrado ou removido")
    if item.pedido_compra_item_id is not None:
        raise ValueError("Este item já foi convertido em Pedido de Compra — não pode mudar o vencedor.")

    outros_do_mesmo_item = (
        ItemCotacao.query
        .filter(
            ItemCotacao.item_processo_cotacao_id == item.item_processo_cotacao_id,
            ItemCotacao.id != item.id,
            ItemCotacao.selecionado_como_vencedor.is_(True),
            ItemCotacao.is_deleted.is_(False),
        )
        .all()
    )
    for outro in outros_do_mesmo_item:
        outro.selecionado_como_vencedor = False

    item.selecionado_como_vencedor = True
    db.session.commit()

    return {"item_cotacao": item.to_dict(), "desmarcados": [o.id for o in outros_do_mesmo_item]}


def desmarcar_item_cotacao_vencedor(item_cotacao_id: int) -> dict:
    """Reverte selecionar_item_cotacao_vencedor() — corrige uma
    seleção sem precisar escolher outro vencedor na hora."""
    from addons.addon_estoque.root.model.item_cotacao import ItemCotacao

    item = ItemCotacao.query.filter_by(id=item_cotacao_id, is_deleted=False).first()
    if item is None:
        raise ItemCotacaoNaoEncontradoError(f"ItemCotacao id={item_cotacao_id} não encontrado ou removido")
    if item.pedido_compra_item_id is not None:
        raise ValueError("Este item já foi convertido em Pedido de Compra — não pode mudar o vencedor.")

    item.selecionado_como_vencedor = False
    db.session.commit()

    return {"item_cotacao": item.to_dict()}


class ProcessoCotacaoNaoEncontradoError(Exception):
    pass


def gerar_pedidos_de_cotacao(processo_cotacao_id: int) -> dict:
    """
    "Gerar Pedido" (skill 24, Fase 6.3) — ação manual e separada
    (decisão de sessão, skill 24 seção 1): pega todos os ItemCotacao
    marcados como vencedores no processo E ainda não convertidos
    (pedido_compra_item_id IS NULL — evita duplicar se a ação for
    chamada mais de uma vez), agrupa por fornecedor (via Cotacao) e
    cria UM PedidoCompra por fornecedor vencedor, com os itens
    correspondentes.

    Passa pelos services (PedidoCompraService/ItemPedidoCompraService),
    não INSERT direto — reaproveita os hooks já existentes (numero
    automático do pedido, fator/quantidade_convertida_base/subtotal do
    item), mesmo raciocínio de nunca duplicar lógica de cálculo.

    PedidoCompra nasce em status="rascunho" — revisável antes de
    confirmar (fluxo normal da Fase 4 continua valendo a partir daí).
    Não gera Movimentacao nenhuma aqui — só quando o Pedido gerado for
    de fato recebido (receber_pedido_compra(), fluxo separado).
    """
    from addons.addon_estoque.root.model.processo_cotacao import ProcessoCotacao
    from addons.addon_estoque.root.model.cotacao import Cotacao
    from addons.addon_estoque.root.model.item_cotacao import ItemCotacao
    from addons.addon_estoque.root.services.pedido_compra_service import PedidoCompraService
    from addons.addon_estoque.root.services.item_pedido_compra_service import ItemPedidoCompraService

    processo = ProcessoCotacao.query.filter_by(id=processo_cotacao_id, is_deleted=False).first()
    if processo is None:
        raise ProcessoCotacaoNaoEncontradoError(f"ProcessoCotacao id={processo_cotacao_id} não encontrado ou removido")

    itens_vencedores = (
        ItemCotacao.query
        .join(Cotacao, ItemCotacao.cotacao_id == Cotacao.id)
        .filter(
            Cotacao.processo_cotacao_id == processo_cotacao_id,
            ItemCotacao.selecionado_como_vencedor.is_(True),
            ItemCotacao.pedido_compra_item_id.is_(None),
            ItemCotacao.is_deleted.is_(False),
        )
        .all()
    )
    if not itens_vencedores:
        raise ValueError(
            "Nenhum item vencedor pendente de geração — marque vencedores na aba Comparação "
            "ou este processo já teve todos os vencedores convertidos em pedido."
        )

    itens_por_fornecedor: dict[int, list[ItemCotacao]] = {}
    for item in itens_vencedores:
        fornecedor_id = item.cotacao.fornecedor_id
        itens_por_fornecedor.setdefault(fornecedor_id, []).append(item)

    pedido_service = PedidoCompraService()
    item_service = ItemPedidoCompraService()
    pedidos_gerados = []

    for fornecedor_id, itens in itens_por_fornecedor.items():
        resultado_pedido = pedido_service.create({
            "fornecedor_id": fornecedor_id,
            "data_pedido": datetime.now(timezone.utc).date().isoformat(),
            "observacoes": f"Gerado a partir do processo de cotação {processo.numero}",
        })
        if not resultado_pedido.success:
            raise RuntimeError(f"Falha ao criar PedidoCompra para fornecedor_id={fornecedor_id}: {resultado_pedido.error}")
        pedido = resultado_pedido.data

        for item_cotacao in itens:
            resultado_item = item_service.create({
                "pedido_compra_id": pedido.id,
                "material_id": item_cotacao.material_id,
                "material_unidade_id": item_cotacao.material_unidade_id,
                "quantidade": item_cotacao.quantidade,
                "preco_unitario": item_cotacao.preco_unitario,
            })
            if not resultado_item.success:
                raise RuntimeError(f"Falha ao criar ItemPedidoCompra a partir de ItemCotacao id={item_cotacao.id}: {resultado_item.error}")

            item_cotacao.pedido_compra_item_id = resultado_item.data.id

        pedidos_gerados.append(pedido.to_dict())

    processo.status = "finalizado"
    processo.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return {"processo_cotacao": processo.to_dict(), "pedidos_gerados": pedidos_gerados}


# ═══ Ações em massa (achado do Christopher — seleção de linhas na
# lista de Materiais, mesmo raciocínio de "várias telas pequenas" já
# usado em todo o addon, mas agora disparado a partir de N materiais
# escolhidos de uma vez). ═══════════════════════════════════════════

def movimentar_estoque_em_massa(
    tipo_movimentacao: str,
    itens: list[dict],
    *,
    usuario_id: int | None = None,
) -> dict:
    """
    "Movimentar Estoque" em massa (decisão de sessão: mesmo tipo pra
    todos, quantidade individual por Material — grid). `itens`:
    `[{"material_id": int, "quantidade": float}, ...]`.

    Best-effort por item, não atômico entre itens — mesmo padrão já
    usado em `receber_pedido_compra()`/`gerar_pedidos_de_cotacao()`
    (cada `registrar_movimentacao()` já comita a própria transação;
    forçar atomicidade entre N materiais exigiria reescrever
    `registrar_movimentacao()` pra não comitar sozinha, fora do escopo
    desta correção). Item com erro não impede os seguintes — resultado
    traz sucesso/erro por material pra pessoa corrigir só o que falhou.
    """
    resultados = []
    for linha in itens:
        material_id = linha.get("material_id")
        quantidade = linha.get("quantidade")
        if not material_id or quantidade is None:
            resultados.append({"material_id": material_id, "sucesso": False, "erro": "Material e quantidade são obrigatórios."})
            continue
        try:
            resultado = registrar_movimentacao(
                int(material_id), tipo_movimentacao, float(quantidade), usuario_id=usuario_id,
                observacoes="Movimentação em massa (seleção múltipla de Materiais).",
            )
            resultados.append({"material_id": material_id, "sucesso": True, "saldo": resultado["saldo"]})
        except Exception as e:  # noqa: BLE001
            resultados.append({"material_id": material_id, "sucesso": False, "erro": str(e)})
    return {"resultados": resultados}


def criar_processo_cotacao_em_massa(
    itens: list[dict],
    *,
    processo_cotacao_id: int | None = None,
    novo_processo: dict | None = None,
) -> dict:
    """
    "Criar Cotação" em massa (decisão de sessão: escolhe entre
    processo NOVO ou um já existente em rascunho/aberto). `itens`:
    `[{"material_id": int, "material_unidade_id": int,
    "quantidade_desejada": float}, ...]` — vira um `ItemProcessoCotacao`
    por material, no processo indicado (ou recém-criado).

    Exatamente um de `processo_cotacao_id`/`novo_processo` deve ser
    informado — validado aqui, não deixado pro banco reclamar.
    """
    from addons.addon_estoque.root.model.processo_cotacao import ProcessoCotacao
    from addons.addon_estoque.root.services.processo_cotacao_service import ProcessoCotacaoService
    from addons.addon_estoque.root.services.item_processo_cotacao_service import ItemProcessoCotacaoService

    if bool(processo_cotacao_id) == bool(novo_processo):
        raise ValueError("Informe processo_cotacao_id OU novo_processo, nunca os dois nem nenhum.")

    if novo_processo:
        resultado_processo = ProcessoCotacaoService().create(novo_processo)
        if not resultado_processo.success:
            raise RuntimeError(f"Falha ao criar ProcessoCotacao: {resultado_processo.error}")
        processo = resultado_processo.data
    else:
        processo = ProcessoCotacao.query.filter_by(id=processo_cotacao_id, is_deleted=False).first()
        if processo is None:
            raise ProcessoCotacaoNaoEncontradoError(f"ProcessoCotacao id={processo_cotacao_id} não encontrado ou removido")
        if processo.status in ("finalizado", "cancelado"):
            raise ValueError(f"Não é possível adicionar itens a um processo {processo.status} (id={processo_cotacao_id})")

    item_service = ItemProcessoCotacaoService()
    itens_criados = []
    for linha in itens:
        resultado_item = item_service.create({
            "processo_cotacao_id": processo.id,
            "material_id": linha["material_id"],
            "material_unidade_id": linha["material_unidade_id"],
            "quantidade_desejada": linha["quantidade_desejada"],
        })
        if not resultado_item.success:
            raise RuntimeError(f"Falha ao criar ItemProcessoCotacao para material_id={linha.get('material_id')}: {resultado_item.error}")
        itens_criados.append(resultado_item.data.to_dict())

    return {"processo_cotacao": processo.to_dict(), "itens": itens_criados}


def criar_pedido_compra_em_massa(
    itens: list[dict],
    *,
    pedido_compra_id: int | None = None,
    novo_pedido: dict | None = None,
) -> dict:
    """
    "Criar Pedido" em massa — mesmo raciocínio de
    criar_processo_cotacao_em_massa(), agora pra PedidoCompra/
    ItemPedidoCompra. `itens`: `[{"material_id": int,
    "material_unidade_id": int, "quantidade": float,
    "preco_unitario": float}, ...]`.
    """
    from addons.addon_estoque.root.model.pedido_compra import PedidoCompra
    from addons.addon_estoque.root.services.pedido_compra_service import PedidoCompraService
    from addons.addon_estoque.root.services.item_pedido_compra_service import ItemPedidoCompraService

    if bool(pedido_compra_id) == bool(novo_pedido):
        raise ValueError("Informe pedido_compra_id OU novo_pedido, nunca os dois nem nenhum.")

    if novo_pedido:
        resultado_pedido = PedidoCompraService().create(novo_pedido)
        if not resultado_pedido.success:
            raise RuntimeError(f"Falha ao criar PedidoCompra: {resultado_pedido.error}")
        pedido = resultado_pedido.data
    else:
        pedido = PedidoCompra.query.filter_by(id=pedido_compra_id, is_deleted=False).first()
        if pedido is None:
            raise PedidoCompraNaoEncontradoError(f"PedidoCompra id={pedido_compra_id} não encontrado ou removido")
        if pedido.status != "rascunho":
            raise PedidoCompraStatusInvalidoError(
                f"Só é possível adicionar itens em massa a um pedido em rascunho (atual: {pedido.status!r})"
            )

    item_service = ItemPedidoCompraService()
    itens_criados = []
    for linha in itens:
        resultado_item = item_service.create({
            "pedido_compra_id": pedido.id,
            "material_id": linha["material_id"],
            "material_unidade_id": linha["material_unidade_id"],
            "quantidade": linha["quantidade"],
            "preco_unitario": linha["preco_unitario"],
        })
        if not resultado_item.success:
            raise RuntimeError(f"Falha ao criar ItemPedidoCompra para material_id={linha.get('material_id')}: {resultado_item.error}")
        itens_criados.append(resultado_item.data.to_dict())

    return {"pedido_compra": pedido.to_dict(), "itens": itens_criados}


_CAMPOS_MODIFICACAO_EM_MASSA = ("fabricante_id", "origem_id", "tipo_produto_id", "categoria_id", "ativo")


def modificar_materiais_em_massa(material_ids: list[int], alteracoes: dict) -> dict:
    """
    "Modificação em Massa" (decisão de sessão: só campos de
    classificação — Fabricante/Origem/Tipo de Produto/Categoria/Ativo).
    `alteracoes` só aplica as chaves PRESENTES no dict — campo ausente
    não é tocado em nenhum Material (mesmo raciocínio de update()
    parcial já usado em toda a Fase 4/skill 24: só mexe no que foi
    explicitamente enviado). Chave com valor `None` é rejeitada — os 4
    campos de referência são obrigatórios em Material (skill 23), não
    dá pra "limpar" via ação em massa.
    """
    from addons.addon_estoque.root.model.material import Material

    campos_invalidos = set(alteracoes) - set(_CAMPOS_MODIFICACAO_EM_MASSA)
    if campos_invalidos:
        raise ValueError(f"Campos não permitidos em modificação em massa: {sorted(campos_invalidos)}")

    for campo in ("fabricante_id", "origem_id", "tipo_produto_id", "categoria_id"):
        if campo in alteracoes and alteracoes[campo] is None:
            raise ValueError(f"'{campo}' é obrigatório em Material — não pode ser limpo via modificação em massa.")

    if not alteracoes:
        raise ValueError("Nenhuma alteração informada.")

    materiais = Material.query.filter(Material.id.in_(material_ids), Material.is_deleted.is_(False)).all()
    encontrados_ids = {m.id for m in materiais}
    nao_encontrados = [mid for mid in material_ids if mid not in encontrados_ids]

    for material in materiais:
        for campo, valor in alteracoes.items():
            setattr(material, campo, valor)
        material.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return {
        "atualizados": len(materiais),
        "material_ids_atualizados": sorted(encontrados_ids),
        "material_ids_nao_encontrados": nao_encontrados,
    }
