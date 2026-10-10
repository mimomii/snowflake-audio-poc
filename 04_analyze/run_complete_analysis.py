#!/usr/bin/env python3
"""
アプローチ B: AI_TRANSCRIBE の文字起こし結果を AI_COMPLETE (llama3.1-70b) に渡し
要約と感情分析を 1 回で実行する。

Usage:
    python run_complete_analysis.py
    python run_complete_analysis.py --file sample1.m4a
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.session import get_session
from common.log import insert_run_log

MODEL = "llama3.1-70b"

PROMPT_TEMPLATE = """\
以下はコールセンターの通話テキストです。
次の2点を分析し、必ず JSON 形式のみで返してください（説明文不要）。
{{
  "summary": "通話内容の要約（100文字以内）",
  "sentiment": "positive / neutral / negative のいずれか"
}}

通話テキスト:
{transcript}"""


def fetch_transcripts(session, file_name=None):
    where = "WHERE FUNCTION_NAME = 'AI_TRANSCRIBE' AND RESULT IS NOT NULL"
    if file_name:
        where += f" AND FILE_NAME = '{file_name}'"
    return session.sql(f"""
        SELECT RUN_ID, FILE_NAME, RESULT:text::STRING AS transcript
        FROM DB_ANALYTICS.AUDIO_POC.RUN_LOG
        {where}
        ORDER BY FILE_NAME
    """).collect()


def run_complete(session, transcript: str):
    prompt = PROMPT_TEMPLATE.format(transcript=transcript)
    rows = session.sql("SELECT AI_COMPLETE(?, ?)", params=[MODEL, prompt]).collect()
    query_id = session.sql("SELECT LAST_QUERY_ID()").collect()[0][0]
    raw = rows[0][0] if rows else None
    try:
        result = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        result = {"raw_response": raw}
    return result, query_id


def main():
    parser = argparse.ArgumentParser(description="アプローチ B: AI_COMPLETE で要約＋感情分析")
    parser.add_argument("--file", help="対象ファイル名（省略時は全件）")
    args = parser.parse_args()

    session = get_session()
    try:
        transcripts = fetch_transcripts(session, args.file)
        if not transcripts:
            print("対象データがありません。")
            return

        print(f"\n{'='*65}")
        print(f"アプローチ B: AI_COMPLETE ({MODEL})  対象 {len(transcripts)} 件")
        print(f"{'='*65}")

        for row in transcripts:
            file_name  = row["FILE_NAME"]
            transcript = row["TRANSCRIPT"] or ""
            print(f"\n[{file_name}]")

            started_at = datetime.now(timezone.utc)
            result, query_id = run_complete(session, transcript)
            ended_at   = datetime.now(timezone.utc)
            elapsed    = (ended_at - started_at).total_seconds()

            run_id = insert_run_log(
                session=session,
                file_name=file_name,
                function_name="AI_COMPLETE",
                mode_or_model=f"approach_b/{MODEL}",
                options={"source_run_id": row["RUN_ID"], "model": MODEL},
                started_at=started_at,
                ended_at=ended_at,
                elapsed_sec=elapsed,
                audio_duration_sec=None,
                result=result,
                error=None,
                query_id=query_id,
            )

            preview = json.dumps(result, ensure_ascii=False)[:120] if result else "None"
            print(f"  AI_COMPLETE ({elapsed:.1f}s)  {preview}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
