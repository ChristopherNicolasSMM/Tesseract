"""Repara FKs duplicadas sem refletir as duplicatas pelo parser do SQLite."""
from collections import defaultdict
import sqlalchemy as sa


def repair_model_builder_foreign_keys(operations):
    connection=operations.get_bind()
    if connection.dialect.name!='sqlite':return
    inspector=sa.inspect(connection)
    names=set(inspector.get_table_names())
    for name in ('tesseract_model_definition','tesseract_model_field_definition'):
        if name not in names:continue
        raw=list(connection.exec_driver_sql('PRAGMA foreign_key_list("'+name+'")').mappings())
        grouped=defaultdict(list)
        for row in raw:grouped[row['id']].append(row)
        unique={}
        for rows in grouped.values():
            rows=sorted(rows,key=lambda row:row['seq'])
            signature=(rows[0]['table'],tuple(r['from'] for r in rows),tuple(r['to'] for r in rows),rows[0]['on_update'],rows[0]['on_delete'],rows[0]['match'])
            unique[signature]=rows
        if len(unique)==len(grouped):continue
        if connection.exec_driver_sql('PRAGMA foreign_keys').scalar():
            raise RuntimeError('Reparo SQLite exige foreign_keys=OFF antes da transação de migração, como as demais recriações batch.')
        meta=sa.MetaData();columns=[]
        for col in inspector.get_columns(name):
            columns.append(sa.Column(col['name'],col['type'],primary_key=bool(col.get('primary_key')),nullable=col['nullable'],
                server_default=sa.text(col['default']) if col.get('default') is not None else None))
        table=sa.Table(name,meta,*columns)
        for signature,rows in unique.items():
            target,local,remote,onupdate,ondelete,match=signature
            if target not in meta.tables:sa.Table(target,meta,*[sa.Column(col,sa.Integer) for col in set(remote)])
            fk_name='fk_model_definition_parent_id' if local==('parent_model_definition_id',) else 'fk_model_field_definition_child_id' if local==('child_model_definition_id',) else None
            table.append_constraint(sa.ForeignKeyConstraint(list(local),[target+'.'+col for col in remote],name=fk_name,onupdate=onupdate,ondelete=ondelete))
        for constraint in inspector.get_unique_constraints(name):
            table.append_constraint(sa.UniqueConstraint(*constraint['column_names'],name=constraint['name']))
        for check in inspector.get_check_constraints(name):table.append_constraint(sa.CheckConstraint(check['sqltext'],name=check['name']))
        for index in inspector.get_indexes(name):
            if index.get('duplicates_constraint'):continue
            sa.Index(index['name'],*[table.c[col] for col in index['column_names']],unique=index['unique'],**index.get('dialect_options',{}))
        with operations.batch_alter_table(name,copy_from=table,recreate='always'):
            pass
        inspector=sa.inspect(connection)
