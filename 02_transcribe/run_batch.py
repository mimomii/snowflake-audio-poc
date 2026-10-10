#!/usr/bin/env python3
"""
全ステージファイル × 全モードで AI_TRANSCRIBE を一括実行し RUN_LOG に保存する。

Usage:
    python run_batch.py [--modes default word speaker] [--files sample1.m4a ...]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.session import get_session
from common.log import insert_run_log
from run_transcribe import list_stage_files, run_ai_transcribe, _MODE_OPTIONS

MODES = ["default", "word", "speaker"]


def main():
    parser = argparse.ArgumentParser(description="AI_TRANSCRIBE 一括実行")
    parser.add_argument("--modes", nargs="+", choices=MODES, default=MODES)
    parser.add_argument("--files", nargs="+", help="対象ファイルを絞る場合に指定（省略時は全ファイル）")
    args = parser.parse_args()

    session = get_session()
    try:
        stage_files = list_stage_files(session)
        targets = args.files if args.files else stage_files
        unknown = [f for f in targets if f not in stage_files]
        if unknown:
            print(f"エラー: ステージに存在しないファイル: {unknown}")
            sys.exit(1)

        total = len(targets) * len(args.modes)
        print(f"\n対象: {len(targets)} ファイル × {len(args.modes)} モード = {total} 実行\n")

        results_summary = []
        n = 0
        for file_name in targets:
            for mode in args.modes:
                n += 1
                options = _MODE_OPTIONS[mode]
                print(f"[{n}/{total}] {file_name}  mode={mode} ...", end=" ", flush=True)

                started_at = datetime.now(timezone.utc)
                try:
                    result, error, query_id = run_ai_transcribe(session, file_name, options)
                except Exception as e:
                    print(f"FAILED ({e})")
                    results_summary.append((file_name, mode, "FAILED", str(e)))
                    continue

                ended_at = datetime.now(timezone.utc)
                elapsed_sec = (ended_at - started_at).total_seconds()

                run_id = insert_run_log(
                    session=session,
                    file_name=file_name,
                    function_name="AI_TRANSCRIBE",
                    mode_or_model=mode,
                    options=options,
                    started_at=started_at,
                    ended_at=ended_at,
                    elapsed_sec=elapsed_sec,
                    audio_duration_sec=None,
                    result=result,
                    error=error,
                    query_id=query_id,
                )

                status = "ERROR" if error else "OK"
                print(f"{status}  ({elapsed_sec:.1f}s)  run_id={run_id[:8]}...")
                results_summary.append((file_name, mode, status, run_id))

        print(f"\n{'='*60}")
        print(f"{'ファイル':<20} {'モード':<10} {'状態':<8} {'RUN_ID / エラー'}")
        print(f"{'─'*60}")
        for file_name, mode, status, detail in results_summary:
            print(f"{file_name:<20} {mode:<10} {status:<8} {detail}")
        print(f"{'='*60}")

        ok = sum(1 for _, _, s, _ in results_summary if s == "OK")
        print(f"\n完了: {ok}/{total} 成功")

    finally:
        session.close()


if __name__ == "__main__":
    main()
