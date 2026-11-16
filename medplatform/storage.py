"""A1 storage read seam, not A2 ingest/quality/matching business endpoints."""
from .auth import DemoAuthority, Principal
from .database import Database
from .errors import AppError


class SourceReader:
    def __init__(self, db: Database, authority: DemoAuthority):
        self.db, self.authority = db, authority

    def read(self, principal: Principal, patient_id: str, environment: str):
        self.authority.require_patient(principal, patient_id, "records:read")
        if environment != "demo":
            raise AppError(403, "ENVIRONMENT_FORBIDDEN", "演示身份不能访问真实数据")
        with self.db.connection(readonly=True) as conn:
            rows = [dict(row) for row in conn.execute(
                "SELECT * FROM source_events WHERE patient_id=? AND data_environment=? ORDER BY occurred_at,event_id",
                (patient_id, environment))]
        self.authority.require_patient(principal, patient_id, "records:read")
        return rows
