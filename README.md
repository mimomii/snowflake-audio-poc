# 音声処理PoC（Snowflake Cortex）

Snowflake Cortex の音声処理機能（AI_TRANSCRIBE / AI_COMPLETE）を日本語音声で評価する検証リポジトリ。

## セットアップ

```bash
uv sync
```

Snowflake 接続設定: `~/.snowflake/connections.toml` の `[analytics]` を参照。

## 実行手順

### 1. テーブル作成

```bash
python3 -c "
import snowflake.connector
# 00_setup/create_tables.sql を実行
"
```

### 2. 音声ファイルのアップロード

```bash
# ドライラン（確認のみ）
python3 01_ingest/upload_audio.py --dir data/audio/ --dry-run

# アップロード実行
python3 01_ingest/upload_audio.py --dir data/audio/
```

### 3. AI_TRANSCRIBE の一括実行

```bash
python3 02_transcribe/run_batch.py --modes default
```

### 4. CER 評価

```bash
python3 03_evaluate/evaluate.py
```

### 5. テキスト分析（Step 3）

```bash
# アプローチ A: AI_SENTIMENT + AI_SUMMARIZE
python3 04_analyze/run_text_analysis.py

# アプローチ B: AI_COMPLETE（llama3.1-70b）
python3 04_analyze/run_complete_analysis.py
```

## ディレクトリ構成

```
00_setup/          DDL（テーブル作成）
01_ingest/         音声ファイルのアップロード
02_transcribe/     AI_TRANSCRIBE 実行・一括バッチ
03_evaluate/       CER 算出・EVALUATION_RESULT 保存
04_analyze/        AI_SENTIMENT / AI_SUMMARIZE / AI_COMPLETE 実行
05_cost/           コスト集計 SQL
common/            共通処理（セッション、ログ、ユーティリティ）
data/audio/        音声ファイル（ローカル）
data/scripts/      台本テキスト（ローカル）
docs/              検証計画
```

## Snowflake リソース

| リソース | 内容 |
|---|---|
| `DB_ANALYTICS.RAW.AUDIO_STAGE` | 音声ファイル置き場（SSE 暗号化） |
| `DB_ANALYTICS.AUDIO_POC.RUN_LOG` | 実行ログ（全関数共通） |
| `DB_ANALYTICS.AUDIO_POC.REFERENCE_TEXT` | 台本・録音条件 |
| `DB_ANALYTICS.AUDIO_POC.EVALUATION_RESULT` | CER 評価結果 |

---

## 検証結果サマリ

### データセット

| 項目 | 内容 |
|---|---|
| ファイル数 | 6 件（sample1〜6.m4a） |
| 合計再生時間 | 約 8 分 |
| カテゴリ | 問い合わせ×2、クレーム×2、ポジティブ×2 |
| 録音環境 | 静かな室内、話者1名（日本語） |
| PII 件数 | 各ファイル 5 件 |
| 専門用語（銀行） | 各ファイル 5 件 |

---

### Step 0: スモークテスト

- テーブル作成・ステージアップロード・AI_TRANSCRIBE 実行・RUN_LOG 保存を確認

**制約事項（Step 0 検証で判明）**

| 項目 | 内容 |
|---|---|
| ステージ暗号化 | デフォルト CSE では AI_TRANSCRIBE が動作しない。SSE（`SNOWFLAKE_SSE`）が必須 |
| AI_TRANSCRIBE オプション | 現バージョン（`AI_TRANSCRIBE$V4`）はオプション引数なし（`{}` のみ有効）。word タイムスタンプ・話者分離・言語指定は未サポート |

---

### Step 2: AI_TRANSCRIBE 精度評価（CER）

**実行モード: default のみ**（word / speaker は現バージョン未サポート）

| ファイル | カテゴリ | CER（正規化前） | CER（正規化後） |
|---|---|---|---|
| sample1.m4a | 問い合わせ | 8.9% | 4.4% |
| sample2.m4a | 問い合わせ | 8.5% | 4.7% |
| sample3.m4a | クレーム | 19.2% | 14.6% |
| sample4.m4a | クレーム | 14.7% | 10.0% |
| sample5.m4a | ポジティブ | 21.7% | 17.0% |
| sample6.m4a | ポジティブ | 13.8% | 9.2% |
| **平均** | | **14.5%** | **10.0%** |

**カテゴリ別傾向**

| カテゴリ | 平均 CER（正規化前） | 平均 CER（正規化後） |
|---|---|---|
| 問い合わせ | 8.7% | 4.6% |
| クレーム | 17.0% | 12.3% |
| ポジティブ | 17.8% | 13.1% |

- 問い合わせ系は精度が高い。クレーム・ポジティブ系は感情的な発話や固有名詞の多さが影響している可能性がある
- 正規化後は約 4〜5 ポイント改善 → 句読点の差異が CER を押し上げていた

---

### Step 3: テキスト分析比較（アプローチ A vs B）

**注記：** 東京リージョン（`AWS_AP_NORTHEAST_1`）では AI_COMPLETE の音声マルチモーダル入力が未サポート（Snowflake のリージョン展開待ち）。
アプローチ B は AI_TRANSCRIBE の文字起こし結果をテキスト入力として AI_COMPLETE に渡す方式で実施。

| | アプローチ A | アプローチ B |
|---|---|---|
| 処理 | AI_TRANSCRIBE → AI_SENTIMENT + AI_SUMMARIZE | AI_TRANSCRIBE → AI_COMPLETE（llama3.1-70b） |
| 感情分析一致率 | 基準 | 5/6（83%） |
| 要約スタイル | PII を含む詳細な要約 | 内容を圧縮した簡潔な要約 |
| 1ファイルあたり処理時間 | 約 6〜8 秒（2回呼び出し） | 約 1〜3 秒（1回呼び出し） |
| 出力 JSON の安定性 | 各関数の仕様通り | 全件スキーマ通りに返却 |

**感情分析の相違（sample2）**

- A（AI_SENTIMENT）: `neutral`（文体が冷静なため）
- B（AI_COMPLETE）: `negative`（「急いで電話した」等の状況を読んで判定）

---

### Step 4: コスト集計

| 関数 | 件数 | クレジット | 推定 USD |
|---|---|---|---|
| AI_TRANSCRIBE | 6 | 0.023308 | $0.0466 |
| AI_SUMMARIZE | 6 | 0.005950 | $0.0119 |
| AI_SENTIMENT | 6 | 0.003742 | $0.0075 |
| AI_COMPLETE | 6 | 0.001057 | $0.0021 |
| **合計** | **24** | **0.034057** | **$0.0681** |

- AI_TRANSCRIBE がコスト全体の **68%** を占める
- アプローチ A（AI_SENTIMENT + AI_SUMMARIZE）は 1 ファイルあたり約 $0.0032
- アプローチ B（AI_COMPLETE）は 1 ファイルあたり約 $0.0004 — A の **約 1/8 のコスト**
- 音声 1 時間あたりの AI_TRANSCRIBE コスト：約 $0.35 USD（Snowflake 公式レートと一致）

---

## 制約・未解決事項

| 項目 | 状況 | 対応 |
|---|---|---|
| AI_TRANSCRIBE オプション（word / speaker） | 現バージョン未サポート | Snowflake アップデート後に再検証 |
| AI_COMPLETE 音声マルチモーダル | 東京リージョン未展開 | Snowflake のリージョン展開を待機 |
| AI_TRANSCRIBE 言語指定 | オプションキー不明（全候補が `invalid options`） | Snowflake のドキュメント更新を待機 |
| AI_COMPLETE 利用可能モデル | `llama3.1-70b` のみ動作確認済み | 他モデルは東京リージョン未展開の可能性 |
