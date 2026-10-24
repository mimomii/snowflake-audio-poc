#!/usr/bin/env python3
"""
アプローチ A: AI_TRANSCRIBE の文字起こし結果に AI_SENTIMENT / AI_SUMMARIZE を適用する。

Usage:
    python run_text_analysis.py
    python run_text_analysis.py --file sample1.m4a
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.session import get_session
from common.log import insert_run_log


def fetch_transcripts(session, file_name=None):
    where = "WHERE FUNCTION_NAME = 'AI_TRANSCRIBE' AND RESULT IS NOT NULL"
    if file_name:
        where += f" AND FILE_NAME = '{file_name}'"
    return session.sql(f"""
        SELECT RUN_ID, FILE_NAME, RESULT:text::STRING AS transcript
        FROM DB_ANALYTICS.AUDIO_POC.RUN_LOG
        {where}
        QUALIFY ROW_NUMBER() OVER (PARTITION BY FILE_NAME ORDER BY STARTED_AT DESC) = 1
        ORDER BY FILE_NAME
    """).collect()


def run_sentiment(session, text: str) -> dict:
    rows = session.sql("SELECT AI_SENTIMENT(?)", params=[text]).collect()
    query_id = session.sql("SELECT LAST_QUERY_ID()").collect()[0][0]
    raw = rows[0][0] if rows else None
    result = json.loads(raw) if isinstance(raw, str) else raw
    return result, query_id


def run_summarize(session, text: str) -> dict:
    rows = session.sql("SELECT AI_SUMMARIZE(?)", params=[text]).collect()
    query_id = session.sql("SELECT LAST_QUERY_ID()").collect()[0][0]
    raw = rows[0][0] if rows else None
    result = {"summary": raw} if raw else None
    return result, query_id


def main():
    parser = argparse.ArgumentParser(description="アプローチ A: AI_SENTIMENT + AI_SUMMARIZE")
    parser.add_argument("--file", help="対象ファイル名（省略時は全件）")
    args = parser.parse_args()

    session = get_session()
    try:
        transcripts = fetch_transcripts(session, args.file)
        if not transcripts:
            print("対象データがありません。")
            return

        print(f"\n{'='*65}")
        print(f"アプローチ A: AI_SENTIMENT + AI_SUMMARIZE  対象 {len(transcripts)} 件")
        print(f"{'='*65}")

        for row in transcripts:
            file_name  = row["FILE_NAME"]
            transcript = row["TRANSCRIPT"] or ""
            print(f"\n[{file_name}]")

            for func_name, runner in [("AI_SENTIMENT", run_sentiment),
                                       ("AI_SUMMARIZE", run_summarize)]:
                started_at = datetime.now(timezone.utc)
                result, query_id = runner(session, transcript)
                ended_at   = datetime.now(timezone.utc)
                elapsed    = (ended_at - started_at).total_seconds()

                run_id = insert_run_log(
                    session=session,
                    file_name=file_name,
                    function_name=func_name,
                    mode_or_model="approach_a",
                    options={"source_run_id": row["RUN_ID"]},
                    started_at=started_at,
                    ended_at=ended_at,
                    elapsed_sec=elapsed,
                    audio_duration_sec=None,
                    result=result,
                    error=None,
                    query_id=query_id,
                )

                preview = json.dumps(result, ensure_ascii=False)[:100] if result else "None"
                print(f"  {func_name:<15} ({elapsed:.1f}s)  {preview}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
