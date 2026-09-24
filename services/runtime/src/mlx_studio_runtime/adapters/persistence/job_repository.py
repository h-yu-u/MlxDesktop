"""Background job persistence."""

import json
import time
from typing import Any

from mlx_studio_runtime.adapters.persistence.sqlite_database import SQLiteDatabase


class JobRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def save(self, item: dict[str, Any]) -> None:
        now = int(time.time())
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO jobs(id,kind,state,model_id,request_json,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    item["id"],
                    item["kind"],
                    item["state"],
                    item.get("modelId"),
                    json.dumps(item.get("request", {})),
                    now,
                    now,
                ),
            )

    def update(self, job_id: str, state: str, error_code: str | None = None) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE jobs SET state=?,error_code=?,updated_at=? WHERE id=?",
                (state, error_code, int(time.time()), job_id),
            )

    def recover_interrupted(self, error_code: str) -> int:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE jobs SET state='failed',error_code=?,updated_at=? "
                "WHERE state IN ('queued','preparing','running','cancelling')",
                (error_code, int(time.time())),
            )
        return cursor.rowcount

    def list(self) -> list[dict[str, Any]]:
        rows = self.database.connection.execute(
            "SELECT id,kind,state,model_id,error_code,created_at,updated_at "
            "FROM jobs ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
        return [
            {
                "id": row[0],
                "kind": row[1],
                "state": row[2],
                "modelId": row[3],
                "errorCode": row[4],
                "createdAt": row[5],
                "updatedAt": row[6],
            }
            for row in rows
        ]
