"""Envase organizacional: embalagens, custo congelado e entrada do produto juntos."""
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from core.db import db
from addons.addon_brewstation.features.feature_mash_control.services.production_organization_service import reserve, context, consume
from addons.addon_brewstation.features.feature_mash_control.model.production_organization import ProductionConsumption
from addons.addon_estoque.root.services import estoque_service, material_lookup
from addons.addon_estoque.root.services.organization_stock_service import canonical
from addons.addon_estoque.root.services.financial_stock_contract import resolve_selected_policy, rounding
from ..model.envase import Envase


def register(lote_id, material, liters, volume_real, components, *, operation_date, kind, key, actor):
    try:
        if operation_date is not None and type(operation_date) is not date:
            raise ValueError('Data de envase inválida.')
        if kind is not None and (not isinstance(kind, str) or len(kind) > 50):
            raise ValueError('Tipo de envase inválido.')
        lote = reserve(lote_id)
        if key:
            from .envase_estoque_service import _envase_repetido
            replay = _envase_repetido(key, lote_id, material['id'], liters, operation_date, kind)
            if replay is not None:
                db.session.rollback()
                return replay
        link = context(lote_id)
        if link is None:
            raise ValueError('Vincule uma organização ao lote antes de envasar; históricos não são reatribuídos.')
        from services.core.organization_service import resolve_organization_by_code
        resolve_organization_by_code(link.organization_code)
        if (material.get('unidade_medida') or '').strip().upper() not in ('UN', 'UND', 'UNIDADE', 'UNIDADES', 'ITEM'):
            raise ValueError('Produto acabado deve usar unidade-base física UN/ITEM para entrada do envase.')
        if lote.volume_real_litros is None or lote.volume_real_litros <= 0:
            raise ValueError('Informe o volume real do lote antes do envase organizacional.')
        active = Envase.query.filter_by(lote_id=lote_id, status='registrado', is_deleted=False).order_by(Envase.id).all()
        if any(not row.producao_snapshot or row.producao_snapshot.get('version') != 2 for row in active):
            raise ValueError('Lote com envase legado requer conferência histórica.')
        measured = Decimal(str(lote.volume_real_litros))
        volume = Decimal(str(liters))
        if not measured.is_finite() or measured <= 0:
            raise ValueError('Volume real do lote deve ser positivo e finito.')
        with localcontext() as ctx:
            ctx.prec = 64
            used = sum((Decimal(row.producao_snapshot['litros_exatos']) for row in active), Decimal(0))
            if used + volume > measured:
                raise ValueError('Envase excede o volume real disponível do lote.')
            if any(Decimal(row.producao_snapshot['volume_real_lote']) != measured for row in active):
                raise ValueError('Volume real alterado após envase; preserve a base de rateio congelada.')
            consumption = consume(lote_id, actor=actor, commit=False)
            frozen = link.snapshot()
            date_text = (operation_date or date.today()).isoformat()
            if date_text < frozen['operation_date']:
                raise ValueError('Envase não pode anteceder a data do consumo do lote.')
            policy = resolve_selected_policy(link.organization_code, policy_version_id=frozen['request']['policy_version_id'], operation_date=date_text)
            total = Decimal(consumption['custo_total_insumos'])
            allocated = sum((Decimal(row.producao_snapshot['custo_cerveja']) for row in active), Decimal(0))
            remaining = total - allocated
            beer = remaining if used + volume == measured else min(remaining, (total * volume / measured).quantize(
                Decimal(1).scaleb(-policy['decimal_places']), rounding=rounding(policy)))
            units = volume / Decimal(str(volume_real))
            if units != units.to_integral_value():
                raise ValueError('Volume deve corresponder a um número inteiro de unidades do produto acabado.')
            envase = Envase(lote_id=lote_id, material_resultante_id=material['id'], quantidade_litros=liters,
                data_envase=operation_date, tipo_envase=kind, status='registrado', idempotency_key=key,
                componentes_snapshot=[], producao_snapshot={})
            db.session.add(envase); db.session.flush()
            lines, movements = [], []
            packaging = Decimal(0)
            for component in sorted(components, key=lambda c: c['material_componente_id']):
                quantity = Decimal(str(component['quantidade'])) * units
                result = estoque_service.registrar_movimentacao(component['material_componente_id'], 'saida', canonical(quantity),
                    organization_code=link.organization_code, operation_date=date_text,
                    policy_version_id=frozen['request']['policy_version_id'], actor=actor, commit=False,
                    idempotency_key=f'packaging:{envase.id}:{component["material_componente_id"]}',
                    observacoes=f'Embalagem do envase #{envase.id}')
                cost = -Decimal(result['movimentacao']['custo_total']); packaging += cost
                lines.append({'material_componente_id': component['material_componente_id'],
                    'quantidade_por_unidade': component['quantidade'], 'quantidade_total': canonical(quantity),
                    'custo_medio': canonical(cost / quantity), 'custo_linha': canonical(cost), 'movimentacao_id': result['movimentacao']['id']})
                movements.append(result)
            product = estoque_service.registrar_valor_producao(organization_code=link.organization_code, material_id=material['id'], kind='entrada',
                quantity=units, value=beer + packaging, policy=policy,
                request={'envase_id': envase.id}, snapshot={'operation_date': date_text, 'envase_id': envase.id, 'custo_cerveja': canonical(beer),
                    'custo_embalagens': canonical(packaging)}, actor=actor, key=f'finished:{envase.id}', commit=False)
            envase.componentes_snapshot = lines
            envase.producao_snapshot = {'version': 2, 'organization_code': link.organization_code,
                'currency_code': policy['currency_code'], 'policy': policy, 'operation_date': date_text,
                'material_resultante_id': material['id'], 'volume_por_unidade_litros': volume_real,
                'unidades_geradas': float(units), 'unidades_exatas': canonical(units), 'litros_exatos': canonical(volume),
                'volume_real_lote': canonical(measured), 'custo_cerveja': canonical(beer),
                'custo_embalagens': canonical(packaging), 'custo_produto': canonical(beer + packaging),
                'entrada_produto_id': product['movimentacao']['id']}
        db.session.commit()
        return {'envase': envase.to_dict(), 'ja_registrado': False, 'unidades_geradas': canonical(units),
                'componentes_baixados': len(lines), 'movimentacoes': movements, 'entrada_produto': product}
    except Exception:
        db.session.rollback()
        raise


def reverse(envase_id, reason, *, actor, usuario_id):
    try:
        initial = db.session.get(Envase, envase_id)
        if initial is None:
            raise ValueError('Envase não encontrado.')
        reserve(initial.lote_id)
        row = Envase.query.filter_by(id=envase_id).populate_existing().one()
        if row.status != 'registrado' or row.is_deleted:
            raise ValueError('Envase já cancelado ou removido.')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError('Informe um motivo de até 1000 caracteres.')
        snapshot = row.producao_snapshot
        from services.core.organization_service import resolve_organization_by_code
        resolve_organization_by_code(snapshot['organization_code'])
        product = estoque_service.consultar_movimento_organizacional(snapshot['entrada_produto_id'])
        result = estoque_service.registrar_valor_producao(organization_code=snapshot['organization_code'], material_id=product['material_id'], kind='saida',
            quantity=-Decimal(product['quantidade']), value=None, policy=snapshot['policy'],
            request={'estorno_envase_id': row.id}, snapshot={'operation_date': snapshot['operation_date'], 'reversal_of': product['id'], 'reason': reason},
            actor=actor, key=f'reverse-product:{row.id}', commit=False)
        if Decimal(result['movimentacao']['custo_total']) != -Decimal(product['custo_total']):
            raise ValueError('Custo/saldo do produto mudou; estorno exige reconciliação explícita da diferença.')
        returns = []
        for component in row.componentes_snapshot:
            original = estoque_service.consultar_movimento_organizacional(component['movimentacao_id'])
            if original is None or original['organization_code'] != snapshot['organization_code'] or original['tipo_movimentacao'] != 'saida':
                raise ValueError('Histórico de embalagem incompatível.')
            restored = estoque_service.registrar_valor_producao(organization_code=original['organization_code'], material_id=original['material_id'], kind='entrada',
                quantity=-Decimal(original['quantidade']), value=-Decimal(original['custo_total']), policy=snapshot['policy'],
                request={'estorno_envase_id': row.id, 'original_id': original['id']},
                snapshot={'operation_date': snapshot['operation_date'], 'reversal_of': original['id'], 'reason': reason}, actor=actor,
                key=f"reverse-packaging:{row.id}:{original['id']}", commit=False)
            returns.append({'saida_id': original['id'], 'entrada_id': restored['movimentacao']['id']})
        row.status = 'cancelado'; row.cancelado_em = datetime.now(timezone.utc)
        row.motivo_cancelamento = reason.strip(); row.cancelado_por_id = usuario_id
        row.estorno_snapshot = returns + [{'saida_id': result['movimentacao']['id'], 'entrada_id': product['id'], 'papel': 'produto'}]
        db.session.commit()
        return {'envase': row.to_dict(), 'devolucoes': returns}
    except Exception:
        db.session.rollback()
        raise
