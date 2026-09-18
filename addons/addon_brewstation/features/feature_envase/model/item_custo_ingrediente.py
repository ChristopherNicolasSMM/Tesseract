"""
addons/addon_brewstation/features/feature_envase/model/item_custo_ingrediente.py

Linha de detalhe (por Material) de um CalculoPrecificacao — mostra pro
usuário se o preço usado foi o realmente pago (ItemPedidoCompra) ou o
padrão configurado por tipo de insumo (feature_ingredientes), em vez
de esconder isso (proposta-precificacao-envase.md §5).
"""
from core.db import db
from annotations import label, plural, required, choices, enum_field, min_value, weak_ref

_MATERIAL_RESOLVER = "addons.addon_estoque.root.services.material_lookup.get_material"


@label("Item de Custo de Ingrediente")
@plural("item_custo_ingredientes")
@enum_field("origem_preco", options=["real", "padrao", "sem_preco"])
@choices("origem_preco", label="Origem do Preço")
@required("calculo_id", message="Cálculo é obrigatório")
@min_value("quantidade", 0, message="Quantidade não pode ser negativa")
@weak_ref("material_id", resolver=_MATERIAL_RESOLVER, options="materials")
class ItemCustoIngrediente(db.Model):
    __tablename__ = "item_custo_ingrediente"

    id = db.Column(db.Integer, primary_key=True)

    calculo_id = db.Column(
        db.Integer, db.ForeignKey("calculo_precificacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    calculo = db.relationship("CalculoPrecificacao", backref=db.backref("itens", lazy=True))

    material_id = db.Column(db.Integer, nullable=True, index=True)  # SEM FK - addon_estoque

    quantidade = db.Column(db.Float, nullable=False)
    preco_unitario_usado = db.Column(db.Float, nullable=False, default=0.0)
    custo_total = db.Column(db.Float, nullable=False, default=0.0)

    # real = veio de ItemPedidoCompra (preço realmente pago); padrao =
    # caiu no PrecoPadraoInsumo (feature_ingredientes); sem_preco =
    # nenhum dos dois (não é malte/lupulo/levedura e nunca foi comprado).
    origem_preco = db.Column(db.String(20), nullable=False, default="sem_preco")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "calculo_id": self.calculo_id,
            "material_id": self.material_id,
            "quantidade": self.quantidade,
            "preco_unitario_usado": self.preco_unitario_usado,
            "custo_total": self.custo_total,
            "origem_preco": self.origem_preco,
        }

    def __repr__(self) -> str:
        return f"<ItemCustoIngrediente calculo_id={self.calculo_id} material_id={self.material_id}>"
