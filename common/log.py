import json
import uuid
from datetime import datetime

from snowflake.snowpark import Session

_TABLE = "DB_ANALYTICS.AUDIO_POC.RUN_LOG"


def insert_run_log(
    session: Session,
    file_name: str,
    function_name: str,
    mode_or_model: str | None,
    options: dict | None,
    started_at: datetime,
    ended_at: datetime,
    elapsed_sec: float,
    audio_duration_sec: float | None,
    result: dict | None,
    error: dict | None,
    query_id: str | None,
) -> str:
    run_id = str(uuid.uuid4())

    sql = f"""
        INSERT INTO {_TABLE} (
            RUN_ID, FILE_NAME, FUNCTION_NAME, MODE_OR_MODEL,
            OPTIONS, STARTED_AT, ENDED_AT, ELAPSED_SEC,
            AUDIO_DURATION_SEC, RESULT, ERROR, QUERY_ID
        )
        SELECT ?, ?, ?, ?,
            PARSE_JSON(NULLIF(?, 'null')), ?, ?, ?,
            ?, PARSE_JSON(NULLIF(?, 'null')), PARSE_JSON(NULLIF(?, 'null')), ?
    """
    session.sql(sql, params=[
        run_id, file_name, function_name, mode_or_model,
        _to_json(options), started_at, ended_at, elapsed_sec,
        audio_duration_sec,
        _to_json(result),
        _to_json(error),
        query_id,
    ]).collect()

    return run_id


def _to_json(value) -> str:
    return json.dumps(value) if value is not None else "null"
