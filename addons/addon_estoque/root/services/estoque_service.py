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
from math import isfinite
from functools import wraps
from sqlalchemy import update
from sqlalchemy.exc import OperationalError

from core.db import db
from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from addons.addon_estoque.root.model.saldo import Saldo

TIPOS_VALIDOS = ("entrada", "saida", "ajuste")


class EstoqueConcorrenciaError(ValueError):
    pass


def _rollback_on_error(operation):
    @wraps(operation)
    def wrapped(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except OperationalError as exc:
            db.session.rollback()
            raise EstoqueConcorrenciaError('Operação concorrente ou banco indisponível. Atualize e tente novamente.') from exc
        except Exception:
            db.session.rollback()
            raise
    return wrapped


class MaterialNaoEncontradoError(Exception):
    pass


class TipoMovimentacaoInvalidoError(Exception):
    pass


def _get_or_create_saldo(material_id: int) -> Saldo:
    saldo = Saldo.query.filter_by(material_id=material_id).populate_existing().first()
    if saldo is None:
        # valor_total_estoque/estoque_minimo já nascem em 0 (achado do
        # Christopher) — nunca null, evita "—"/branco na tela até a
        # primeira Movimentação/edição manual preencher de verdade.
        saldo = Saldo(material_id=material_id, quantidade_atual=0.0, valor_total_estoque=0.0, estoque_minimo=0.0)
        db.session.add(saldo)
        db.session.flush()
    return saldo


@_rollback_on_error
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
    commit: bool = True,
    organization_code: str | None = None,
    source_currency: str | None = None,
    operation_date: str | None = None,
    rate_id: int | None = None,
    policy_version_id: int | None = None,
    idempotency_key: str | None = None,
    actor: str | None = None,
    valuation_id: int | None = None,
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
    if organization_code is not None:
        from .organization_stock_service import register, register_valuation_line
        if valuation_id is not None:
            if any(value is not None for value in (custo_unitario,source_currency,operation_date,rate_id,
                                                  policy_version_id,idempotency_key,fornecedor_id,unidade_original,
                                                  quantidade_original,fator_conversao_aplicado,usuario_id,observacoes)):
                raise ValueError('Recebimento usa exclusivamente o snapshot da avaliação congelada.')
            from .purchase_context_service import get_context
            from addons.addon_estoque.root.model.organization_stock import OrderValuation
            if type(valuation_id) is not int or valuation_id <= 0:
                raise ValueError('Avaliação inválida.')
            valuation = db.session.get(OrderValuation, valuation_id)
            context = get_context('order',valuation.order_id) if valuation else None
            if context is None or context.organization_code != organization_code:
                raise ValueError('Avaliação não pertence à organização informada.')
            if tipo_movimentacao != 'entrada':
                raise ValueError('Avaliação monetária é exclusiva do recebimento de entrada.')
            return register_valuation_line(valuation_id,pedido_compra_item_id,material_id=material_id,quantity=quantidade,actor=actor,
                extra={'lote_fornecedor':lote_fornecedor,'data_validade':data_validade},commit=commit)
        if any(value is not None for value in (pedido_compra_item_id,fornecedor_id,unidade_original,quantidade_original,
                                              fator_conversao_aplicado,lote_fornecedor,data_validade,usuario_id)):
            raise ValueError('Rastro de pedido/lote exige avaliação monetária de recebimento.')
        return register({'organization_code':organization_code,'material_id':material_id,'tipo_movimentacao':tipo_movimentacao,
            'quantidade':quantidade,'custo_unitario':custo_unitario,'source_currency':source_currency,'operation_date':operation_date,
            'rate_id':rate_id,'policy_version_id':policy_version_id,'idempotency_key':idempotency_key,'observacoes':observacoes},
            actor=actor,commit=commit)
    if any(value is not None for value in (source_currency,operation_date,rate_id,policy_version_id,idempotency_key,actor,valuation_id)):
        raise ValueError('Parâmetros monetários organizacionais exigem organização explícita.')

    if tipo_movimentacao not in TIPOS_VALIDOS:
        raise TipoMovimentacaoInvalidoError(
            f"tipo_movimentacao deve ser um de {TIPOS_VALIDOS}, recebido: {tipo_movimentacao!r}"
        )

    if isinstance(quantidade, bool) or not isinstance(quantidade, (int, float)) or not isfinite(quantidade):
        raise ValueError("quantidade deve ser um número finito")
    if quantidade == 0:
        raise ValueError("quantidade deve ser diferente de zero")
    if custo_unitario is not None and (
        isinstance(custo_unitario, bool) or not isinstance(custo_unitario, (int, float))
        or not isfinite(custo_unitario) or custo_unitario < 0
    ):
        raise ValueError("custo_unitario deve ser um número finito não negativo")

    # Reservar a linha do material também protege a criação do primeiro saldo.
    # Em SQLite o UPDATE reserva o escritor; PostgreSQL reserva a linha.
    # Releitura do saldo evita atualizar um objeto antigo no identity map.
    with db.session.no_autoflush:
        db.session.execute(update(Material).where(
            Material.id == material_id, Material.is_deleted.is_(False)
        ).values(updated_at=Material.updated_at).execution_options(synchronize_session=False))
    material = Material.query.filter_by(id=material_id, is_deleted=False).populate_existing().first()
    if material is None:
        raise MaterialNaoEncontradoError(f"Material id={material_id} não encontrado ou removido")

    if tipo_movimentacao in ("entrada", "saida") and quantidade < 0:
        raise ValueError("quantidade não pode ser negativa para entrada/saida — use tipo_movimentacao='ajuste'")

    custo_total = (custo_unitario * quantidade) if custo_unitario is not None else None
    if custo_total is not None and not isfinite(custo_total):
        raise ValueError("custo_total deve ser finito")

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
    for nome in ('quantidade_atual', 'custo_medio', 'valor_total_estoque'):
        valor = getattr(saldo, nome)
        if valor is not None and not isfinite(valor):
            raise ValueError(f'{nome} do saldo deve permanecer finito')
    saldo.ultima_atualizacao = datetime.now(timezone.utc)

    if tipo_movimentacao == "entrada" and fornecedor_id is not None:
        saldo.ultimo_preco_compra = custo_unitario
        saldo.ultimo_fornecedor_id = fornecedor_id
        saldo.data_ultima_compra = datetime.now(timezone.utc).date()

    try:
        if commit:
            db.session.commit()
        else:
            db.session.flush()
    except Exception:
        db.session.rollback()
        raise

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


def consultar_saldo(material_id: int, *, organization_code=None) -> dict | None:
    if organization_code is not None:
        from services.core.organization_service import resolve_organization_by_code
        from addons.addon_estoque.root.model.organization_stock import OrganizationBalance
        org = resolve_organization_by_code(organization_code,require_active=False)
        row = OrganizationBalance.query.filter_by(material_id=material_id,organization_code=org['code']).first()
        return row.to_dict() if row else None
    saldo = Saldo.query.filter_by(material_id=material_id).first()
    return saldo.to_dict() if saldo else None


class PedidoCompraNaoEncontradoError(Exception):
    pass


class PedidoCompraStatusInvalidoError(Exception):
    pass


@_rollback_on_error
def receber_pedido_compra(
    pedido_compra_id: int,
    *,
    usuario_id: int | None = None,
    dados_por_item: dict[int, dict] | None = None,
    actor: str | None = None,
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

    from .purchase_integrity_service import reserve_order
    pedido = reserve_order(pedido_compra_id)
    if pedido is None or pedido.is_deleted:
        raise PedidoCompraNaoEncontradoError(f"PedidoCompra id={pedido_compra_id} não encontrado ou removido")

    from .purchase_context_service import get_context
    if get_context('order',pedido.id):
        from .order_valuation_service import receive
        if actor is None:
            from flask import has_request_context
            from flask_login import current_user
            actor = current_user.username if has_request_context() and current_user.is_authenticated else None
        return receive(pedido,actor=actor,dados_por_item=dados_por_item)

    if pedido.status != "confirmado":
        raise PedidoCompraStatusInvalidoError(
            f"Só é possível receber um pedido com status='confirmado' (atual: {pedido.status!r})"
        )

    # A coleção pode ter sido carregada antes de esperar outra transação.
    from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
    itens = (ItemPedidoCompra.query.filter_by(pedido_compra_id=pedido.id, is_deleted=False)
             .order_by(ItemPedidoCompra.material_id, ItemPedidoCompra.id).populate_existing().all())
    if not itens:
        raise ValueError(f"PedidoCompra id={pedido_compra_id} não tem itens para receber")

    if (Movimentacao.query.join(ItemPedidoCompra, Movimentacao.pedido_compra_item_id == ItemPedidoCompra.id)
            .filter(ItemPedidoCompra.pedido_compra_id == pedido.id).first() is not None):
        raise PedidoCompraStatusInvalidoError('Pedido já possui recebimento registrado. Preserve o histórico; não receba novamente.')

    dados_por_item = dados_por_item or {}

    movimentacoes = []
    try:
        for item in itens:
            # Somente snapshots ausentes em registros legados usam o fator 1.
            # Zero/NaN/infinito nunca podem virar uma conversão válida por fallback.
            fator = item.fator_conversao_aplicado
            if fator is None:
                fator = 1.0
            quantidade_base = item.quantidade_convertida_base
            for nome, valor in (("fator de conversão", fator), ("quantidade", item.quantidade)):
                if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not isfinite(valor) or valor <= 0:
                    raise ValueError(f"Item {item.id}: {nome} deve ser positivo e finito")
            if quantidade_base is None:
                quantidade_base = item.quantidade * fator
            if not isfinite(quantidade_base) or quantidade_base <= 0:
                raise ValueError(f"Item {item.id}: quantidade convertida deve ser positiva e finita")
            if not isfinite(item.preco_unitario) or item.preco_unitario < 0:
                raise ValueError(f"Item {item.id}: preço unitário deve ser não negativo e finito")
            custo_unitario_base = item.preco_unitario / fator
            extra = dados_por_item.get(item.id, {})

            resultado = registrar_movimentacao(
                item.material_id,
                "entrada",
                quantidade_base,
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
                commit=False,
            )
            movimentacoes.append(resultado["movimentacao"])

        pedido.status = "recebido"
        pedido.updated_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

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


@_rollback_on_error
def gerar_pedidos_de_cotacao(processo_cotacao_id: int, *, actor=None) -> dict:
    """
    "Gerar Pedido" (skill 24, Fase 6.3) — ação manual e separada
    (decisão de sessão, skill 24 seção 1): pega todos os ItemCotacao
    marcados como vencedores no processo E ainda não convertidos
    (pedido_compra_item_id IS NULL — evita duplicar se a ação for
    chamada mais de uma vez), agrupa por fornecedor (via Cotacao) e
    cria UM PedidoCompra por fornecedor vencedor, com os itens
    correspondentes.

    Reutiliza os contratos manuais dos overrides de compras, com flush
    em vez de commits intermediários; todo o processo é atômico. Não usa INSERT direto — reaproveita os hooks já existentes (numero
    automático do pedido, fator/quantidade_convertida_base/subtotal do
    item), mesmo raciocínio de nunca duplicar lógica de cálculo.

    PedidoCompra nasce em status="rascunho" — revisável antes de
    confirmar (fluxo normal da Fase 4 continua valendo a partir daí).
    Não gera Movimentacao nenhuma aqui — só quando o Pedido gerado for
    de fato recebido (receber_pedido_compra(), fluxo separado).
    """
    from addons.addon_estoque.root.model.cotacao import Cotacao
    from addons.addon_estoque.root.model.item_cotacao import ItemCotacao

    from .purchase_context_service import document, get_context
    try:
        processo = document('process', processo_cotacao_id, reserve=True)
    except ValueError as exc:
        raise ProcessoCotacaoNaoEncontradoError(str(exc)) from exc
    context = get_context('process',processo.id)
    if context:
        from services.core.organization_service import resolve_organization_by_code
        from .financial_stock_contract import text
        from addons.addon_estoque.root.model.purchase_context import PurchaseContext
        resolve_organization_by_code(context.organization_code)
        if actor is None:
            from flask import has_request_context
            from flask_login import current_user
            actor = current_user.username if has_request_context() and current_user.is_authenticated else None
        actor = text(actor,120,'Autor')
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

    from .purchase_integrity_service import operate
    # Reutiliza os mesmos contratos dos overrides, adiando TODOS os commits.
    pedidos_gerados = []

    for fornecedor_id, itens in itens_por_fornecedor.items():
        resultado_pedido = operate('order','create',data={
            "fornecedor_id": fornecedor_id,
            "data_pedido": datetime.now(timezone.utc).date().isoformat(),
            "observacoes": f"Gerado a partir do processo de cotação {processo.numero}",
        },commit=False)
        if not resultado_pedido.success:
            raise RuntimeError(f"Falha ao criar PedidoCompra para fornecedor_id={fornecedor_id}: {resultado_pedido.error}")
        pedido = resultado_pedido.data
        if context:
            db.session.add(PurchaseContext(order_id=pedido.id,organization_code=context.organization_code,
                organization_name=context.organization_name,created_by=actor))
            db.session.flush()

        for item_cotacao in itens:
            resultado_item = operate('item','create',data={
                "pedido_compra_id": pedido.id,
                "material_id": item_cotacao.material_id,
                "material_unidade_id": item_cotacao.material_unidade_id,
                "quantidade": item_cotacao.quantidade,
                "preco_unitario": item_cotacao.preco_unitario,
            },commit=False)
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


_CAMPOS_MODIFICACAO_EM_MASSA = (
    "fabricante_id", "origem_id", "tipo_produto_id", "categoria_id", "ativo",
    # Ampliação (achado do Christopher — campos do print de detalhe de
    # Material): nenhum destes é FK obrigatória (skill 23), então não
    # precisam da trava de "não pode limpar" abaixo.
    "pendente_revisao", "unidade_medida", "peso",
    "volume_calculado", "unidade_medida_volume_calculado",
    "volume_real", "unidade_medida_volume_real", "formato_fisico",
)


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
