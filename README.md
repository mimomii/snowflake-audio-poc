# 音声処理PoC（Snowflake Cortex）

Snowflake Cortex の音声処理機能（AI_TRANSCRIBE / AI_COMPLETE）を日本語音声で評価する検証リポジトリ。

## セットアップ

```bash
uv sync
```

Snowflake 接続設定: `~/.snowflake/connections.toml` の `[analytics]` を参照。

## 実行手順

### 1. テーブル初期化

Snowsight / SnowSQL で以下を実行:

```sql
-- 既存データを全削除する場合
-- 00_setup/reset.sql を実行

-- テーブル作成・カラム追加
-- 00_setup/create_tables.sql を実行
```

### 2. 台本・メタデータの登録

```bash
python3 00_setup/seed_reference.py --dry-run   # 確認のみ
python3 00_setup/seed_reference.py             # 本実行
```

### 3. 音声ファイルのアップロード

```bash
# ドライラン（確認のみ）
python3 01_ingest/upload_audio.py --dir data/audio/ --dry-run

# アップロード実行（既存ファイルを上書きする場合は --overwrite を付ける）
python3 01_ingest/upload_audio.py --dir data/audio/ --overwrite
```

### 4. AI_TRANSCRIBE の一括実行

```bash
python3 02_transcribe/run_batch.py --modes default
```

### 5. CER 評価

```bash
python3 03_evaluate/evaluate.py
```

### 6. テキスト分析（Step 3）

```bash
# アプローチ A: AI_SENTIMENT + AI_SUMMARIZE
python3 04_analyze/run_text_analysis.py

# アプローチ B: AI_COMPLETE（llama3.1-70b）
python3 04_analyze/run_complete_analysis.py
```

## ディレクトリ構成

```
00_setup/          DDL・リセット・シードスクリプト
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
| `DB_ANALYTICS.AUDIO_POC.REFERENCE_TEXT` | 台本・録音条件（VOICE_TYPE・ENVIRONMENT含む） |
| `DB_ANALYTICS.AUDIO_POC.EVALUATION_RESULT` | CER 評価結果 |

---

## 検証結果サマリ

### データセット

| 項目 | 内容 |
|---|---|
| ファイル数 | 12 件（sample1〜12.m4a） |
| カテゴリ | 問い合わせ×4、クレーム×4、ポジティブ×4 |
| 録音環境 | 静か×6、うるさい×6（各カテゴリ・声種に各1） |
| 話者 | 男性×6（sample1〜6）、女性×6（sample7〜12） |
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

#### ファイル別結果

| ファイル | カテゴリ | 環境 | 声種 | CER（正規化前） | CER（正規化後） |
|---|---|---|---|---|---|
| sample1.m4a | 問い合わせ | 静か | 男性 | 8.9% | 4.4% |
| sample2.m4a | 問い合わせ | うるさい | 男性 | 8.7% | 5.0% |
| sample3.m4a | クレーム | 静か | 男性 | 5.7% | 2.8% |
| sample4.m4a | クレーム | うるさい | 男性 | 9.3% | 4.0% |
| sample5.m4a | ポジティブ | 静か | 男性 | 9.6% | 4.1% |
| sample6.m4a | ポジティブ | うるさい | 男性 | 8.0% | 4.5% |
| sample7.m4a | 問い合わせ | 静か | 女性 | 9.5% | 6.1% |
| sample8.m4a | 問い合わせ | うるさい | 女性 | 10.1% | 7.6% |
| sample9.m4a | クレーム | 静か | 女性 | 17.7% | 13.3% |
| sample10.m4a | クレーム | うるさい | 女性 | 8.7% | 6.4% |
| sample11.m4a | ポジティブ | 静か | 女性 | 8.9% | 5.6% |
| sample12.m4a | ポジティブ | うるさい | 女性 | 8.0% | 3.0% |
| **平均** | | | | **9.3%** | **5.6%** |

#### カテゴリ別

| カテゴリ | 件数 | CER（正規化前） | CER（正規化後） |
|---|---|---|---|
| ポジティブ | 4 | 8.6% | 4.3% |
| 問い合わせ | 4 | 9.3% | 5.8% |
| クレーム | 4 | 10.3% | 6.6% |

- クレームが最も CER が高い傾向は前回と同様
- sample9（クレーム・静か・女性）が 17.7% と突出して高い

#### 録音環境別

| 環境 | 件数 | CER（正規化前） | CER（正規化後） |
|---|---|---|---|
| うるさい | 6 | 8.8% | 5.1% |
| 静か | 6 | 10.0% | 6.0% |

- 予想に反してうるさい環境の CER がやや低い。sample9（静か・女性・クレーム）の高 CER が静かグループ全体の平均を押し上げているためと考えられる

#### 声種別

| 声種 | 件数 | CER（正規化前） | CER（正規化後） |
|---|---|---|---|
| 男性 | 6 | 8.4% | 4.1% |
| 女性 | 6 | 10.5% | 7.0% |

- 男性の方が女性より約 2〜3 ポイント精度が高い
- sample9（女性・クレーム・静か）の外れ値が女性全体の平均を引き上げている点に注意

---

### Step 3: テキスト分析比較（アプローチ A vs B）

**注記：** 東京リージョン（`AWS_AP_NORTHEAST_1`）では AI_COMPLETE の音声マルチモーダル入力が未サポート（Snowflake のリージョン展開待ち）。
アプローチ B は AI_TRANSCRIBE の文字起こし結果をテキスト入力として AI_COMPLETE に渡す方式で実施。

| | アプローチ A | アプローチ B |
|---|---|---|
| 処理 | AI_TRANSCRIBE → AI_SENTIMENT + AI_SUMMARIZE | AI_TRANSCRIBE → AI_COMPLETE（llama3.1-70b） |
| 要約スタイル | PII を含む詳細な要約 | 内容を圧縮した簡潔な要約 |
| 1ファイルあたり処理時間 | 約 1〜9 秒（2回呼び出し） | 約 1〜10 秒（1回呼び出し） |
| 1ファイルあたりコスト | 約 $0.0033 | 約 $0.00035 |
| 出力 JSON の安定性 | 各関数の仕様通り | 全件スキーマ通りに返却 |

---

### Step 4: コスト集計

| 関数 | 件数 | クレジット | 推定 USD |
|---|---|---|---|
| AI_TRANSCRIBE | 12 | 0.046596 | $0.0932 |
| AI_SUMMARIZE | 12 | 0.011912 | $0.0238 |
| AI_SENTIMENT | 12 | 0.007638 | $0.0153 |
| AI_COMPLETE | 12 | 0.002115 | $0.0042 |
| **合計** | **48** | **0.068261** | **$0.1365** |

- AI_TRANSCRIBE がコスト全体の **68.3%** を占める（前回 6 件と同傾向）
- アプローチ A（AI_SENTIMENT + AI_SUMMARIZE）は 1 ファイルあたり約 $0.0033
- アプローチ B（AI_COMPLETE）は 1 ファイルあたり約 $0.00035 — A の **約 1/9 のコスト**
- 音声 1 時間あたりの AI_TRANSCRIBE コスト：約 $0.35 USD（Snowflake 公式レートと一致）
- 男性声の AI_TRANSCRIBE が女性声より平均 0.0006 クレジット高い（音声長の差の可能性）

---

## 制約・未解決事項

| 項目 | 状況 | 対応 |
|---|---|---|
| AI_TRANSCRIBE オプション（word / speaker） | 現バージョン未サポート | Snowflake アップデート後に再検証 |
| AI_COMPLETE 音声マルチモーダル | 東京リージョン未展開 | Snowflake のリージョン展開を待機 |
| AI_TRANSCRIBE 言語指定 | オプションキー不明（全候補が `invalid options`） | Snowflake のドキュメント更新を待機 |
| AI_COMPLETE 利用可能モデル | `llama3.1-70b` のみ動作確認済み | 他モデルは東京リージョン未展開の可能性 |
