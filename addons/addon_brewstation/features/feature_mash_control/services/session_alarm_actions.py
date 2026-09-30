"""Ações de alarmes de sessão. Extensão manual, não gerada pelo CrudGen."""
from datetime import datetime, timezone
from sqlalchemy import update

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog


class SessionAlarmNotFound(ValueError):
    pass


def acknowledge_alarm(plant_id: int, session_id: int, alarm_id: int, user_id: int) -> dict:
    """Reconhece uma vez, preservando o primeiro operador/horário e seu log."""
    alarm = (BrewSessionAlarm.query.join(BrewSession).join(BrewPlant)
             .filter(BrewSessionAlarm.id == alarm_id, BrewSessionAlarm.session_id == session_id,
                     BrewSession.plant_id == plant_id, BrewSessionAlarm.is_deleted.is_(False),
                     BrewSession.is_deleted.is_(False), BrewPlant.is_deleted.is_(False)).first())
    if alarm is None:
        raise SessionAlarmNotFound("Alarme desta sessão e planta não encontrado.")
    try:
        result = db.session.execute(
            update(BrewSessionAlarm)
            .where(BrewSessionAlarm.id == alarm_id, BrewSessionAlarm.session_id == session_id,
                   BrewSessionAlarm.is_deleted.is_(False), BrewSessionAlarm.is_acknowledged.is_(False))
            .values(is_acknowledged=True, acknowledged_at=datetime.now(timezone.utc), acknowledged_by=user_id)
            .execution_options(synchronize_session=False)
        )
        changed = result.rowcount == 1
        if changed:
            db.session.add(BrewSessionLog(
                session_id=session_id, source="user", log_level="info",
                message=f"Alarme #{alarm_id} reconhecido pelo operador #{user_id}.",
                detail_json={"action": "acknowledge_alarm", "alarm_id": alarm_id, "user_id": user_id},
            ))
        db.session.commit()
        db.session.refresh(alarm)
    except Exception:
        db.session.rollback()
        raise
    return {"ja_reconhecido": not changed, "alarme": alarm.to_dict()}
