#!/usr/bin/env python3
"""
Upload local audio files to AUDIO_STAGE.

Usage:
    python upload_audio.py --file path/to/audio.wav [--dry-run]
    python upload_audio.py --dir path/to/dir/ [--mode word] [--dry-run]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.session import get_session
from common.utils import get_audio_info, check_constraints, estimate_cost, format_size, format_duration

STAGE = "@DB_ANALYTICS.RAW.AUDIO_STAGE"
AUDIO_EXTENSIONS = {".wav", ".mp3", ".mp4", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


def collect_files(file_arg, dir_arg):
    files = []
    if file_arg:
        files.append(Path(file_arg))
    if dir_arg:
        p = Path(dir_arg)
        for ext in AUDIO_EXTENSIONS:
            files.extend(p.glob(f"*{ext}"))
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description="Upload audio files to AUDIO_STAGE")
    parser.add_argument("--file", help="アップロードするファイルパス")
    parser.add_argument("--dir", help="音声ファイルが入ったディレクトリ")
    parser.add_argument("--mode", default="default", choices=["default", "word", "speaker"],
                        help="予定する transcribe モード（制約チェック用）")
    parser.add_argument("--dry-run", action="store_true", help="確認のみ。アップロードは行わない")
    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("--file または --dir が必要です")

    files = collect_files(args.file, args.dir)
    if not files:
        print("対象ファイルが見つかりませんでした。")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"対象ファイル: {len(files)} 件  （モード: {args.mode}）")
    print(f"{'='*60}")

    has_warning = False
    known_durations = []

    for f in files:
        if not f.exists():
            print(f"\n{f.name}  ⚠ ファイルが見つかりません")
            continue

        info = get_audio_info(str(f))
        warnings = check_constraints(str(f), mode=args.mode)

        print(f"\n{f.name}")
        print(f"  サイズ   : {format_size(info['size_bytes'])}")
        print(f"  再生時間 : {format_duration(info['duration_sec'])}")

        if warnings:
            has_warning = True
            for w in warnings:
                print(f"  ⚠ {w}")

        if info["duration_sec"]:
            known_durations.append(info["duration_sec"])

    if known_durations:
        cost = estimate_cost(known_durations)
        total_dur = sum(known_durations)
        print(f"\n{'─'*60}")
        print(f"合計再生時間 : {format_duration(total_dur)}")
        print(f"推定トークン : {cost['total_tokens']:,}  （各ファイル最低10秒換算）")
        print(f"推定コスト   : ${cost['estimated_cost_usd']:.4f} USD")

    if args.dry_run:
        print("\n[ドライラン] ファイルはアップロードされません。")
        return

    if has_warning:
        ans = input("\n制約警告があります。続行しますか？ [y/N]: ")
        if ans.strip().lower() != "y":
            print("中断しました。")
            sys.exit(0)

    print("\nアップロード中...")
    session = get_session()
    try:
        for f in files:
            if not f.exists():
                continue
            rows = session.sql(
                f"PUT 'file://{f.resolve()}' {STAGE} AUTO_COMPRESS=FALSE OVERWRITE=FALSE"
            ).collect()
            for row in rows:
                print(f"  {row['source']}: {row['status']}")

        print("\nステージの現在の内容:")
        for row in session.sql(f"LIST {STAGE}").collect():
            print(f"  {row['name']}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
