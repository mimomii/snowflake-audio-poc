#!/usr/bin/env python3
"""
Run AI_TRANSCRIBE on a file in AUDIO_STAGE and save results to RUN_LOG.

Usage:
    python run_transcribe.py --mode default --file consultation.wav [--dry-run]
    python run_transcribe.py --mode word    --file consultation.wav
    python run_transcribe.py --mode speaker --file consultation.wav
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.session import get_session
from common.log import insert_run_log
from common.utils import estimate_cost, format_duration

STAGE = "DB_ANALYTICS.RAW.AUDIO_STAGE"

# Step 0 検証結果: 現バージョンの AI_TRANSCRIBE はオプションキーを受け付けない（空オブジェクトのみ有効）。
# word タイムスタンプ・話者分離は現時点で未サポート。Snowflake アップデート後に再検証が必要。
_MODE_OPTIONS = {
    "default": {},
    "word":    {},
    "speaker": {},
}


def list_stage_files(session) -> list[str]:
    rows = session.sql(f"LIST @{STAGE}").collect()
    return [row["name"].split("/")[-1] for row in rows]


def get_stage_file_duration(session, file_name: str) -> float | None:
    rows = session.sql(f"""
        SELECT LAST_VALUE(AUDIO_DURATION_SEC) IGNORE NULLS OVER (ORDER BY CREATED_AT)
        FROM DB_ANALYTICS.AUDIO_POC.RUN_LOG
        WHERE FILE_NAME = ?
        LIMIT 1
    """, params=[file_name]).collect()
    if rows and rows[0][0] is not None:
        return float(rows[0][0])
    return None


def run_ai_transcribe(session, file_name: str, options: dict) -> tuple[dict | None, dict | None, str]:
    options_sql = json.dumps(options).replace("'", "\\'")
    sql = f"""
        SELECT AI_TRANSCRIBE(
            TO_FILE('@{STAGE}', ?),
            PARSE_JSON('{options_sql}')
        ) AS result
    """
    rows = session.sql(sql, params=[file_name]).collect()
    query_id = session.sql("SELECT LAST_QUERY_ID()").collect()[0][0]

    raw = rows[0]["RESULT"] if rows else None
    if raw is None:
        return None, None, query_id

    parsed = json.loads(raw) if isinstance(raw, str) else raw
    error = parsed.get("error") if isinstance(parsed, dict) else None
    result = {k: v for k, v in parsed.items() if k != "error"} if isinstance(parsed, dict) else parsed
    return result, error, query_id


def main():
    parser = argparse.ArgumentParser(description="AI_TRANSCRIBE を実行して RUN_LOG に保存する")
    parser.add_argument("--mode", required=True, choices=["default", "word", "speaker"])
    parser.add_argument("--file", required=True, help="ステージ上のファイル名（例: consultation.wav）")
    parser.add_argument("--audio-duration", type=float, help="音声の再生時間（秒）。未指定時は RUN_LOG から取得を試みる")
    parser.add_argument("--dry-run", action="store_true", help="推定コストを表示して実行しない")
    args = parser.parse_args()

    options = _MODE_OPTIONS[args.mode]

    session = get_session()
    try:
        stage_files = list_stage_files(session)
        if args.file not in stage_files:
            print(f"エラー: '{args.file}' がステージに見つかりません。")
            print(f"ステージ上のファイル: {stage_files}")
            sys.exit(1)

        duration_sec = args.audio_duration or get_stage_file_duration(session, args.file)

        print(f"\n{'='*60}")
        print(f"ファイル : {args.file}")
        print(f"モード   : {args.mode}")
        print(f"オプション: {json.dumps(options, ensure_ascii=False)}")
        print(f"再生時間 : {format_duration(duration_sec)}")

        if duration_sec:
            cost = estimate_cost([duration_sec])
            print(f"推定トークン : {cost['total_tokens']:,}")
            print(f"推定コスト   : ${cost['estimated_cost_usd']:.4f} USD")
        else:
            print("推定コスト   : 再生時間不明のため算出不可")

        if args.dry_run:
            print("\n[ドライラン] 実行しません。")
            return

        ans = input("\nAI_TRANSCRIBE を実行しますか？ [y/N]: ")
        if ans.strip().lower() != "y":
            print("中断しました。")
            sys.exit(0)

        print("\n実行中...")
        started_at = datetime.now(timezone.utc)
        result, error, query_id = run_ai_transcribe(session, args.file, options)
        ended_at = datetime.now(timezone.utc)
        elapsed_sec = (ended_at - started_at).total_seconds()

        run_id = insert_run_log(
            session=session,
            file_name=args.file,
            function_name="AI_TRANSCRIBE",
            mode_or_model=args.mode,
            options=options,
            started_at=started_at,
            ended_at=ended_at,
            elapsed_sec=elapsed_sec,
            audio_duration_sec=duration_sec,
            result=result,
            error=error,
            query_id=query_id,
        )

        print(f"\n完了。")
        print(f"RUN_ID   : {run_id}")
        print(f"QUERY_ID : {query_id}")
        print(f"処理時間 : {elapsed_sec:.1f} 秒")

        if error:
            print(f"⚠ エラーあり: {json.dumps(error, ensure_ascii=False)}")
        elif result:
            text = result.get("text", "")
            preview = text[:200] + ("..." if len(text) > 200 else "")
            print(f"\n文字起こし（先頭200字）:\n{preview}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
