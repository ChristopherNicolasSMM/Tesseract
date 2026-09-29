"""Limpa dados de BrewStation e Estoque para recadastro/importacao.

Uso (com o aplicativo parado):
    python scripts/reset_brewstation_sqlite.py instance/tesseract_dev.db
    python scripts/reset_brewstation_sqlite.py instance/tesseract_dev.db --execute

O primeiro comando apenas mostra as contagens. --execute cria backup SQLite
antes de apagar dados em uma unica transacao. Nao remove tabelas/migrations.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys


TABLES = (
    # Receitas, de-para e historico de producao.
    'tesseract_brewstation_mashctrl_recipe',
    'tesseract_brewstation_mashctrl_recipe_ingredient',
    'tesseract_brewstation_mashctrl_recipe_step',
    'tesseract_brewstation_mashctrl_fermentation_step',
    'tesseract_brewstation_mashctrl_water_profile',
    'tesseract_brewstation_mashctrl_recipe_history',
    'tesseract_brewstation_mashctrl_ingredient_mapping',
    'tesseract_brewstation_mashctrl_session',
    'tesseract_brewstation_mashctrl_session_step',
    'tesseract_brewstation_mashctrl_session_log',
    'tesseract_brewstation_mashctrl_session_alarm',
    'tesseract_brewstation_mashctrl_rule_log',
    # Envase e precificacao dependem dos lotes e materiais antigos.
    'tesseract_brewstation_env_envase',
    'tesseract_brewstation_env_item_envase',
    'tesseract_brewstation_env_calculo_precificacao',
    'tesseract_brewstation_env_item_custo_ingrediente',
    # Especificacoes dos materiais e estado da integracao.
    'tesseract_brewstation_ingr_malte',
    'tesseract_brewstation_ingr_lupulo',
    'tesseract_brewstation_ingr_levedura',
    'tesseract_brewstation_ingr_preco_padrao_insumo',
    'tesseract_brewstation_brewfather_inventory_link',
    'tesseract_brewstation_brewfather_sync',
    # Material + unidades, compras/cotacoes e o ledger/saldo correspondente.
    'tesseract_estoque_material',
    'tesseract_estoque_material_unidade',
    'tesseract_estoque_composicao',
    'tesseract_estoque_movimentacao',
    'tesseract_estoque_saldo',
    'tesseract_estoque_item_pedido_compra',
    'tesseract_estoque_pedido_compra',
    'tesseract_estoque_item_cotacao',
    'tesseract_estoque_item_processo_cotacao',
    'tesseract_estoque_cotacao',
    'tesseract_estoque_processo_cotacao',
)

REQUIRED = {
    'tesseract_estoque_material',
    'tesseract_brewstation_mashctrl_recipe',
    'alembic_version',
}

# Referencia nullable numa configuracao preservada. Todas as sessoes saem.
DETACH = {('tesseract_brewstation_mashctrl_rule', 'session_id')}
WEAK_COLUMNS = {
    'material_id', 'material_resultante_id', 'material_pai_id',
    'material_componente_id', 'recipe_id', 'lote_id',
    'source_recipe_step_id', 'source_recipe_ingredient_id',
}


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def inventory(conn: sqlite3.Connection):
    existing = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )}
    missing = REQUIRED - existing
    if missing:
        raise RuntimeError('Tabelas obrigatorias ausentes: ' + ', '.join(sorted(missing)))
    targets = set(TABLES) & existing
    columns = {
        table: {row[1] for row in conn.execute(f'PRAGMA table_info({q(table)})')}
        for table in existing
    }
    foreign_keys = {
        table: [(row[2], row[3]) for row in conn.execute(f'PRAGMA foreign_key_list({q(table)})')]
        for table in existing
    }
    return existing, targets, columns, foreign_keys


def check_references(conn, existing, targets, columns, foreign_keys):
    for table in sorted(existing - targets):
        for parent, column in foreign_keys[table]:
            if parent not in targets or (table, column) in DETACH:
                continue
            count = conn.execute(
                f'SELECT COUNT(*) FROM {q(table)} WHERE {q(column)} IS NOT NULL'
            ).fetchone()[0]
            if count:
                raise RuntimeError(
                    f'{table}.{column} referencia dados a excluir ({count} linhas); '
                    'amplie o escopo apos revisar esta dependencia.'
                )
        for column in sorted(columns[table] & WEAK_COLUMNS):
            if (table, column) in DETACH:
                continue
            count = conn.execute(
                f'SELECT COUNT(*) FROM {q(table)} WHERE {q(column)} IS NOT NULL'
            ).fetchone()[0]
            if count:
                raise RuntimeError(
                    f'Referencia fraca fora do reset: {table}.{column} ({count} linhas). '
                    'Revise antes de apagar os materiais/receitas.'
                )


def delete_order(targets, foreign_keys):
    children = {table: set() for table in targets}
    for child in targets:
        for parent, _ in foreign_keys[child]:
            if parent in targets and parent != child:
                children[parent].add(child)
    ordered, active, done = [], set(), set()

    def visit(table):
        if table in active:
            raise RuntimeError('Ciclo de chaves estrangeiras no escopo de limpeza')
        if table in done:
            return
        active.add(table)
        for child in sorted(children[table]):
            visit(child)
        active.remove(table)
        done.add(table)
        ordered.append(table)

    for table in sorted(targets):
        visit(table)
    return ordered


def run(db_path: Path, execute: bool = False) -> Path | None:
    db_path = db_path.expanduser().resolve()
    if not db_path.is_file():
        raise RuntimeError(f'Banco nao encontrado: {db_path}')
    # mode=rw impede criar um banco vazio quando o caminho esta incorreto.
    conn = sqlite3.connect(db_path.as_uri() + '?mode=rw', uri=True, timeout=5)
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        existing, targets, columns, foreign_keys = inventory(conn)
        check_references(conn, existing, targets, columns, foreign_keys)
        order = delete_order(targets, foreign_keys)
        counts = {table: conn.execute(f'SELECT COUNT(*) FROM {q(table)}').fetchone()[0]
                  for table in order}
        print(f'Banco: {db_path}')
        print('Tabelas e linhas a excluir:')
        for table in order:
            if counts[table]:
                print(f'  {table}: {counts[table]}')
        print(f'Total: {sum(counts.values())} linhas em {len(order)} tabelas do escopo')
        print('Preservados: usuarios, configuracoes, YeastBank, plantas/dispositivos, '
              'fornecedores, fabricantes, categorias, origens, tipos e catalogo de unidades.')
        if not execute:
            print('Previa apenas. Para executar, repita com --execute e o sistema parado.')
            return None
        backup_path = db_path.with_name(
            db_path.name + '.backup-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite'
        )
        with sqlite3.connect(backup_path) as backup:
            conn.backup(backup)
        print(f'Backup: {backup_path}')
        try:
            conn.execute('BEGIN IMMEDIATE')
            for table, column in sorted(DETACH):
                if table in existing and column in columns[table]:
                    conn.execute(f'UPDATE {q(table)} SET {q(column)} = NULL '
                                 f'WHERE {q(column)} IS NOT NULL')
            # Verifica de novo sob o lock antes de apagar.
            check_references(conn, existing, targets, columns, foreign_keys)
            for table in order:
                conn.execute(f'DELETE FROM {q(table)}')
            violations = conn.execute('PRAGMA foreign_key_check').fetchall()
            if violations:
                raise RuntimeError(f'Chaves estrangeiras invalidas apos limpeza: {violations[:5]}')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        print('Limpeza concluida. Tabelas e versao do Alembic preservadas.')
        return backup_path
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path, help='Caminho do SQLite (instance/tesseract_dev.db)')
    parser.add_argument('--execute', action='store_true', help='Faz backup e apaga os dados listados')
    args = parser.parse_args()
    try:
        run(args.database, args.execute)
    except (RuntimeError, sqlite3.Error) as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
