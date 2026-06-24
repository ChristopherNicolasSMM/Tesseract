"""
addons/addon_brewstation/features/feature_mash_control/model/dashboard_widget.py

Widget posicionado em um DashboardLayout, opcionalmente ligado a uma
Function do device_manager (FK cross-Feature, mesmo Addon — permitido).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Widget de Dashboard")
@plural("dashboard_widgets")
@required("widget_type", message="Tipo do widget é obrigatório")
class DashboardWidget(db.Model):
    __tablename__ = "widget"

    id = db.Column(db.Integer, primary_key=True)

    layout_id = db.Column(db.Integer, db.ForeignKey("layout.id"), nullable=False)
    layout = db.relationship("DashboardLayout", backref=db.backref(
        "widgets", lazy=True, cascade="all, delete-orphan", order_by="DashboardWidget.z_index"
    ))

    widget_type = db.Column(db.String(50), nullable=False)
    label_text = db.Column(db.String(200), nullable=True)  # "label" renomeado (colide com @label)
    svg_asset_key = db.Column(db.String(100), nullable=True)

    x = db.Column(db.Float, default=100, nullable=True)
    y = db.Column(db.Float, default=100, nullable=True)
    width = db.Column(db.Float, default=120, nullable=True)
    height = db.Column(db.Float, default=140, nullable=True)
    rotation = db.Column(db.Float, default=0.0, nullable=True)
    z_index = db.Column(db.Integer, default=1, nullable=True)

    # FK cross-Feature (mash_control -> device_manager), mesmo Addon — permitido.
    device_function_id = db.Column(db.Integer, db.ForeignKey("function.id"), nullable=True)
    device_function = db.relationship("DeviceFunction", backref=db.backref("dashboard_widgets", lazy=True))

    config_json = db.Column(db.JSON, default=lambda: {})
    is_visible = db.Column(db.Boolean, default=True, nullable=False)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "layout_id": self.layout_id,
            "widget_type": self.widget_type,
            "label_text": self.label_text,
            "svg_asset_key": self.svg_asset_key,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "rotation": self.rotation,
            "z_index": self.z_index,
            "device_function_id": self.device_function_id,
            "config_json": self.config_json or {},
            "is_visible": self.is_visible,
            "is_deleted": self.is_deleted,
        }

    def __repr__(self) -> str:
        return f"<DashboardWidget {self.widget_type} layout_id={self.layout_id}>"
