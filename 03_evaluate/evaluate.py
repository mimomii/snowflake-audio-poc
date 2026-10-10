#!/usr/bin/env python3
"""
RUN_LOG の文字起こし結果と REFERENCE_TEXT の台本を比較して CER を算出し
EVALUATION_RESULT に保存する。

Usage:
    python evaluate.py                          # 未評価の全 RUN_ID を処理
    python evaluate.py --run-id <uuid>          # 特定の RUN_ID のみ
"""

import argparse
import re
import sys
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

import editdistance

sys.path.insert(0, str(Path(__file__).parent.parent))
from common.session import get_session


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[。、！？・「」『』【】()（）…　\s]", "", text)
    return text


def cer_detail(ref: str, hyp: str) -> dict:
    """文字レベルの編集距離から CER と内訳を返す。"""
    dist = editdistance.eval(ref, hyp)
    ref_len = len(ref)
    cer = dist / ref_len if ref_len > 0 else 0.0

    # 内訳は近似値（Levenshtein の合計距離から比率で按分）
    hyp_len = len(hyp)
    if ref_len == 0:
        return {"cer": 0.0, "dist": 0, "ref_len": 0, "hyp_len": hyp_len,
                "substitutions": 0, "insertions": 0, "deletions": 0}

    net_diff = hyp_len - ref_len
    # dist = S + I + D,  I - D = net_diff
    # 近似: S = dist - max(net_diff, 0) - max(-net_diff, 0) を下限0で調整
    deletions    = max(0, -net_diff)
    insertions   = max(0,  net_diff)
    substitutions = max(0, dist - insertions - deletions)
    # 残差を substitution に吸収（近似）
    remainder = dist - substitutions - insertions - deletions
    substitutions += remainder

    return {
        "cer": cer,
        "dist": dist,
        "ref_len": ref_len,
        "hyp_len": hyp_len,
        "substitutions": substitutions,
        "insertions": insertions,
        "deletions": deletions,
    }


def fetch_unevaluated(session, run_id_filter=None):
    where = "WHERE r.RESULT IS NOT NULL"
    if run_id_filter:
        where += f" AND r.RUN_ID = '{run_id_filter}'"
    else:
        # 既評価の RUN_ID は除外
        where += """
            AND r.RUN_ID NOT IN (SELECT RUN_ID FROM DB_ANALYTICS.AUDIO_POC.EVALUATION_RESULT)
        """
    sql = f"""
        SELECT r.RUN_ID, r.FILE_NAME, r.MODE_OR_MODEL,
               r.RESULT:text::STRING AS transcript,
               t.REFERENCE_TEXT
        FROM DB_ANALYTICS.AUDIO_POC.RUN_LOG r
        JOIN DB_ANALYTICS.AUDIO_POC.REFERENCE_TEXT t
          ON r.FILE_NAME = t.FILE_NAME
        {where}
        ORDER BY r.FILE_NAME, r.MODE_OR_MODEL
    """
    return session.sql(sql).collect()


def insert_eval(session, row: dict):
    sql = """
        INSERT INTO DB_ANALYTICS.AUDIO_POC.EVALUATION_RESULT (
            EVAL_ID, RUN_ID, FILE_NAME, MODE_OR_MODEL,
            CER_RAW, CER_NORMALIZED,
            REF_CHAR_COUNT, HYP_CHAR_COUNT,
            SUBSTITUTIONS, INSERTIONS, DELETIONS
        )
        SELECT ?, ?, ?, ?,
               ?, ?,
               ?, ?,
               ?, ?, ?
    """
    session.sql(sql, params=[
        row["eval_id"], row["run_id"], row["file_name"], row["mode_or_model"],
        row["cer_raw"], row["cer_normalized"],
        row["ref_char_count"], row["hyp_char_count"],
        row["substitutions"], row["insertions"], row["deletions"],
    ]).collect()


def main():
    parser = argparse.ArgumentParser(description="CER 評価を実行して EVALUATION_RESULT に保存")
    parser.add_argument("--run-id", help="特定の RUN_ID のみ評価（省略時は未評価の全件）")
    args = parser.parse_args()

    session = get_session()
    try:
        rows = fetch_unevaluated(session, run_id_filter=args.run_id)
        if not rows:
            print("評価対象がありません（既評価済みか、対応する REFERENCE_TEXT がありません）。")
            return

        print(f"\n{'='*70}")
        print(f"評価対象: {len(rows)} 件")
        print(f"{'='*70}")
        print(f"{'ファイル':<20} {'モード':<10} {'CER_RAW':>8} {'CER_NORM':>9} {'台本':>6} {'結果':>6}")
        print(f"{'─'*70}")

        for r in rows:
            ref  = r["REFERENCE_TEXT"] or ""
            hyp  = r["TRANSCRIPT"]     or ""

            raw  = cer_detail(ref, hyp)
            norm = cer_detail(normalize(ref), normalize(hyp))

            record = {
                "eval_id":        str(uuid.uuid4()),
                "run_id":         r["RUN_ID"],
                "file_name":      r["FILE_NAME"],
                "mode_or_model":  r["MODE_OR_MODEL"],
                "cer_raw":        round(raw["cer"],  4),
                "cer_normalized": round(norm["cer"], 4),
                "ref_char_count": raw["ref_len"],
                "hyp_char_count": raw["hyp_len"],
                "substitutions":  raw["substitutions"],
                "insertions":     raw["insertions"],
                "deletions":      raw["deletions"],
            }
            insert_eval(session, record)

            print(f"{r['FILE_NAME']:<20} {r['MODE_OR_MODEL']:<10}"
                  f" {record['cer_raw']:>7.1%} {record['cer_normalized']:>8.1%}"
                  f" {raw['ref_len']:>6} {raw['hyp_len']:>6}")

        print(f"{'─'*70}")

        # サマリ集計
        results = session.sql("""
            SELECT
                MODE_OR_MODEL,
                ROUND(AVG(CER_RAW), 4)        AS AVG_CER_RAW,
                ROUND(AVG(CER_NORMALIZED), 4) AS AVG_CER_NORM,
                COUNT(*)                       AS N
            FROM DB_ANALYTICS.AUDIO_POC.EVALUATION_RESULT
            GROUP BY MODE_OR_MODEL
            ORDER BY MODE_OR_MODEL
        """).collect()

        print(f"\n{'モード':<10} {'平均CER(RAW)':>12} {'平均CER(正規化)':>14} {'件数':>4}")
        print(f"{'─'*44}")
        for row in results:
            print(f"{row['MODE_OR_MODEL']:<10} {float(row['AVG_CER_RAW']):>11.1%}"
                  f" {float(row['AVG_CER_NORM']):>13.1%} {row['N']:>4}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
