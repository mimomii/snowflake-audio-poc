#!/usr/bin/env python3
"""
REFERENCE_TEXT テーブルに新データセット（sample1〜12）のメタデータと台本を登録する。

Usage:
    python seed_reference.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.session import get_session

SCRIPTS_DIR = Path(__file__).parent.parent / "data" / "scripts"

# カテゴリ / 環境 / 声種別メタデータ
METADATA = {
    "sample1.m4a":  ("問い合わせ", "静か",    "男性", "高橋健一（男性）住宅ローン繰上返済"),
    "sample2.m4a":  ("問い合わせ", "うるさい", "男性", "小林大輔（男性）海外送金"),
    "sample3.m4a":  ("クレーム",   "静か",    "男性", "林健太（男性）遅延損害金"),
    "sample4.m4a":  ("クレーム",   "うるさい", "男性", "斎藤茂樹（男性）支店統合・ATM廃止"),
    "sample5.m4a":  ("ポジティブ", "静か",    "男性", "石川雄一（男性）カフェ開業融資お礼"),
    "sample6.m4a":  ("ポジティブ", "うるさい", "男性", "長谷川悠斗（男性）バンキングアプリ感想"),
    "sample7.m4a":  ("問い合わせ", "静か",    "女性", "渡辺真由美（女性）教育ローン"),
    "sample8.m4a":  ("問い合わせ", "うるさい", "女性", "松本彩花（女性）NISA口座"),
    "sample9.m4a":  ("クレーム",   "静か",    "女性", "山田沙織（女性）デビットカード不正利用"),
    "sample10.m4a": ("クレーム",   "うるさい", "女性", "中島美穂（女性）口座維持手数料"),
    "sample11.m4a": ("ポジティブ", "静か",    "女性", "岡田紗希（女性）外貨両替お礼"),
    "sample12.m4a": ("ポジティブ", "うるさい", "女性", "森田節子（女性）定期満期お礼"),
}

PII_COUNT         = 5
DOMAIN_TERM_COUNT = 5


def load_script(file_name: str) -> str:
    stem = Path(file_name).stem          # "sample1"
    txt  = SCRIPTS_DIR / f"{stem}.txt"
    if not txt.exists():
        raise FileNotFoundError(f"台本が見つかりません: {txt}")
    return txt.read_text(encoding="utf-8").strip()


def main():
    parser = argparse.ArgumentParser(description="REFERENCE_TEXT を INSERT する")
    parser.add_argument("--dry-run", action="store_true", help="確認のみ。DB には書き込まない")
    args = parser.parse_args()

    print(f"\n{'='*65}")
    print(f"REFERENCE_TEXT シード  対象 {len(METADATA)} 件  dry-run={args.dry_run}")
    print(f"{'='*65}")

    rows = []
    for file_name, (category, environment, voice_type, notes) in METADATA.items():
        try:
            ref_text = load_script(file_name)
        except FileNotFoundError as e:
            print(f"  ERROR: {e}")
            sys.exit(1)
        rows.append({
            "file_name":         file_name,
            "reference_text":    ref_text,
            "language":          "ja",
            "speakers":          1,
            "category":          category,
            "environment":       environment,
            "voice_type":        voice_type,
            "pii_count":         PII_COUNT,
            "domain_term_count": DOMAIN_TERM_COUNT,
            "notes":             notes,
        })
        print(f"  {file_name:<14} [{category}] [{environment}] [{voice_type}]  {len(ref_text)}文字")

    if args.dry_run:
        print("\n[ドライラン] DB には書き込みません。")
        return

    session = get_session()
    try:
        sql = """
            INSERT INTO DB_ANALYTICS.AUDIO_POC.REFERENCE_TEXT (
                FILE_NAME, REFERENCE_TEXT, LANGUAGE, SPEAKERS,
                CATEGORY, ENVIRONMENT, VOICE_TYPE,
                PII_COUNT, DOMAIN_TERM_COUNT, NOTES
            )
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        """
        for row in rows:
            session.sql(sql, params=[
                row["file_name"], row["reference_text"], row["language"], row["speakers"],
                row["category"], row["environment"], row["voice_type"],
                row["pii_count"], row["domain_term_count"], row["notes"],
            ]).collect()

        count = session.sql(
            "SELECT COUNT(*) AS N FROM DB_ANALYTICS.AUDIO_POC.REFERENCE_TEXT"
        ).collect()[0]["N"]
        print(f"\nINSERT 完了: REFERENCE_TEXT に {count} 件登録済み")
    finally:
        session.close()


if __name__ == "__main__":
    main()
