"""Storage repositories for database operations and query isolation."""

from __future__ import annotations

import json
import time
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.storage.models import (
    AlertModel,
    AuditEventModel,
    DetectionModel,
    MitigationModel,
    ObservationModel,
    ThresholdConfigModel,
)


def _current_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ObservationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        source_id: str,
        timestamp: str,
        window_seconds: float,
        feature_schema_version: str,
        features: dict,
    ) -> ObservationModel:
        obs = ObservationModel(
            source_id=source_id,
            timestamp=timestamp,
            window_seconds=window_seconds,
            feature_schema_version=feature_schema_version,
            features_json=json.dumps(features),
            created_at=_current_timestamp(),
        )
        self.session.add(obs)
        self.session.commit()
        self.session.refresh(obs)
        return obs

    def get_by_id(self, obs_id: int) -> ObservationModel | None:
        return self.session.get(ObservationModel, obs_id)

    def list_recent(self, limit: int = 50) -> list[ObservationModel]:
        stmt = select(ObservationModel).order_by(desc(ObservationModel.id)).limit(limit)
        return list(self.session.scalars(stmt).all())


class DetectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        event_id: str,
        observation_id: int | None,
        model_version: str,
        feature_schema_version: str,
        prediction: str,
        score_type: str,
        score: float,
        traffic_threshold_exceeded: bool,
        policy_decision: str,
        mitigation_mode: str,
        timestamp: str,
    ) -> DetectionModel:
        detection = DetectionModel(
            event_id=event_id,
            observation_id=observation_id,
            model_version=model_version,
            feature_schema_version=feature_schema_version,
            prediction=prediction,
            score_type=score_type,
            score=score,
            traffic_threshold_exceeded=traffic_threshold_exceeded,
            policy_decision=policy_decision,
            mitigation_mode=mitigation_mode,
            timestamp=timestamp,
            created_at=_current_timestamp(),
        )
        self.session.add(detection)
        self.session.commit()
        self.session.refresh(detection)
        return detection

    def get_by_event_id(self, event_id: str) -> DetectionModel | None:
        stmt = select(DetectionModel).where(DetectionModel.event_id == event_id)
        return self.session.scalars(stmt).first()

    def list_recent(self, limit: int = 50, offset: int = 0) -> list[DetectionModel]:
        stmt = (
            select(DetectionModel)
            .order_by(desc(DetectionModel.id))
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())


class AlertRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        detection_id: int | None,
        severity: str,
        title: str,
        description: str,
        source_id: str,
        timestamp: str,
    ) -> AlertModel:
        alert = AlertModel(
            alert_id=f"alt_{uuid4().hex[:12]}",
            detection_id=detection_id,
            severity=severity,
            title=title,
            description=description,
            source_id=source_id,
            timestamp=timestamp,
            status="active",
        )
        self.session.add(alert)
        self.session.commit()
        self.session.refresh(alert)
        return alert

    def get_by_id(self, alert_id: str) -> AlertModel | None:
        stmt = select(AlertModel).where(AlertModel.alert_id == alert_id)
        return self.session.scalars(stmt).first()

    def list_filtered(
        self,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AlertModel]:
        stmt = select(AlertModel)
        if severity:
            stmt = stmt.where(AlertModel.severity == severity)
        if status:
            stmt = stmt.where(AlertModel.status == status)
        stmt = stmt.order_by(desc(AlertModel.id)).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def count_filtered(
        self,
        severity: str | None = None,
        status: str | None = None,
    ) -> int:
        stmt = select(func.count(AlertModel.id))
        if severity:
            stmt = stmt.where(AlertModel.severity == severity)
        if status:
            stmt = stmt.where(AlertModel.status == status)
        return self.session.scalar(stmt) or 0


class MitigationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        detection_id: int | None,
        target_ip: str,
        target_port: int | None,
        action_type: str,
        rate_limit_pps: int,
        duration_seconds: int,
        status: str = "proposed",
        mode: str = "simulation",
    ) -> MitigationModel:
        now = _current_timestamp()
        mitigation = MitigationModel(
            action_id=f"act_{uuid4().hex[:12]}",
            detection_id=detection_id,
            target_ip=target_ip,
            target_port=target_port,
            action_type=action_type,
            rate_limit_pps=rate_limit_pps,
            duration_seconds=duration_seconds,
            status=status,
            mode=mode,
            created_at=now,
            updated_at=now,
        )
        self.session.add(mitigation)
        self.session.commit()
        self.session.refresh(mitigation)
        return mitigation

    def get_by_action_id(self, action_id: str) -> MitigationModel | None:
        stmt = select(MitigationModel).where(MitigationModel.action_id == action_id)
        return self.session.scalars(stmt).first()

    def update_status(
        self,
        action_id: str,
        new_status: str,
        cancelled_at: str | None = None,
        expires_at: str | None = None,
    ) -> MitigationModel | None:
        mitigation = self.get_by_action_id(action_id)
        if not mitigation:
            return None
        mitigation.status = new_status
        mitigation.updated_at = _current_timestamp()
        if cancelled_at:
            mitigation.cancelled_at = cancelled_at
        if expires_at:
            mitigation.expires_at = expires_at
        self.session.commit()
        self.session.refresh(mitigation)
        return mitigation

    def list_filtered(
        self,
        status: str | None = None,
        mode: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MitigationModel]:
        stmt = select(MitigationModel)
        if status:
            stmt = stmt.where(MitigationModel.status == status)
        if mode:
            stmt = stmt.where(MitigationModel.mode == mode)
        stmt = stmt.order_by(desc(MitigationModel.id)).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def count_filtered(
        self,
        status: str | None = None,
        mode: str | None = None,
    ) -> int:
        stmt = select(func.count(MitigationModel.id))
        if status:
            stmt = stmt.where(MitigationModel.status == status)
        if mode:
            stmt = stmt.where(MitigationModel.mode == mode)
        return self.session.scalar(stmt) or 0

    def get_active_or_simulated(self) -> list[MitigationModel]:
        stmt = select(MitigationModel).where(
            MitigationModel.status.in_(["proposed", "simulated", "applied"])
        )
        return list(self.session.scalars(stmt).all())


class ThresholdConfigRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active(self) -> ThresholdConfigModel:
        stmt = (
            select(ThresholdConfigModel)
            .where(ThresholdConfigModel.is_active.is_(True))
            .order_by(desc(ThresholdConfigModel.id))
        )
        config = self.session.scalars(stmt).first()
        if not config:
            config = ThresholdConfigModel(
                version="v1.0.0",
                is_active=True,
                pps_threshold=5000.0,
                bps_threshold=10_000_000.0,
                syn_pps_threshold=500.0,
                syn_ack_ratio_threshold=5.0,
                rf_probability_threshold=0.75,
                iforest_score_threshold=0.2664,
                updated_by="system",
                created_at=_current_timestamp(),
            )
            self.session.add(config)
            self.session.commit()
            self.session.refresh(config)
        return config

    def update(self, updated_by: str, updates: dict) -> ThresholdConfigModel:
        current = self.get_active()
        current.is_active = False

        new_version = f"v{uuid4().hex[:6]}"
        new_config = ThresholdConfigModel(
            version=new_version,
            is_active=True,
            pps_threshold=float(updates.get("pps_threshold", current.pps_threshold)),
            bps_threshold=float(updates.get("bps_threshold", current.bps_threshold)),
            syn_pps_threshold=float(
                updates.get("syn_pps_threshold", current.syn_pps_threshold)
            ),
            syn_ack_ratio_threshold=float(
                updates.get("syn_ack_ratio_threshold", current.syn_ack_ratio_threshold)
            ),
            rf_probability_threshold=float(
                updates.get(
                    "rf_probability_threshold", current.rf_probability_threshold
                )
            ),
            iforest_score_threshold=float(
                updates.get("iforest_score_threshold", current.iforest_score_threshold)
            ),
            updated_by=updated_by,
            created_at=_current_timestamp(),
        )
        self.session.add(new_config)
        self.session.commit()
        self.session.refresh(new_config)
        return new_config


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def log(
        self,
        event_type: str,
        action: str,
        actor: str,
        details: dict,
    ) -> AuditEventModel:
        event = AuditEventModel(
            event_id=f"aud_{uuid4().hex[:12]}",
            event_type=event_type,
            action=action,
            actor=actor,
            details_json=json.dumps(details),
            timestamp=_current_timestamp(),
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def list_filtered(
        self,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEventModel]:
        stmt = select(AuditEventModel)
        if event_type:
            stmt = stmt.where(AuditEventModel.event_type == event_type)
        stmt = stmt.order_by(desc(AuditEventModel.id)).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def count_filtered(self, event_type: str | None = None) -> int:
        stmt = select(func.count(AuditEventModel.id))
        if event_type:
            stmt = stmt.where(AuditEventModel.event_type == event_type)
        return self.session.scalar(stmt) or 0
