# 音声処理PoC 検証計画

---

## Step 0: スモークテスト

### 目的
公式サンプル音声1本で、アップロードから文字起こし・ログ保存までの一連の流れが動作することを確認する。  
本番データを使う前に、スクリプト・テーブル・権限の問題をすべてつぶす。

### 手順
1. `00_setup/create_tables.sql` を実行して `RUN_LOG` を作成する
2. 公式サンプル音声をローカルに保存する
   - `https://docs.snowflake.com/static/samples/cortex/audio/consultation.wav`
3. `upload_audio.py` でステージへ PUT し、LIST で確認する
4. `run_transcribe.py` で default / word / speaker の3モードを順に実行し、`RUN_LOG` に保存する
5. 最大45分後に `SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY` を確認する
6. 結果を README.md のサマリ表に記録する

### 記録する項目
- 各モードの RUN_ID、QUERY_ID、処理時間（elapsed_sec）
- 各モードの文字起こし結果（先頭200字）
- エラーの有無と内容
- CORTEX_AI_FUNCTIONS_USAGE_HISTORY の確認結果（反映された/されなかった）

### 完了条件
- 3モードすべてが正常終了（ERROR カラムが NULL）
- `RUN_LOG` に3件のレコードが保存されている
- 各レコードに QUERY_ID が記録されている
- README.md のサマリ表が埋まっている

---

## Step 1: データセット準備

### 目的
自社音声で評価するためのデータセットを準備する。  
録音条件をばらつかせることで、AI_TRANSCRIBE の性能特性と限界を多面的に把握する。

### 手順
1. 音声ファイルを10〜20本収集する。以下の条件をできるだけ網羅する:
   - クリアな音声（オフィス、静かな会議室）
   - ノイズあり（雑音、BGM）
   - 電話品質（8kHz、低ビットレート）
   - 複数話者（2名以上）
   - 日英混在
   - 短いファイル（10秒未満を含む）
2. このうち5〜10本について、手動で正解テキストを作成する（`REFERENCE_TEXT` テーブルに登録）
3. `upload_audio.py` で全ファイルをステージへアップロードする
4. `00_setup/create_tables.sql` に追記した `REFERENCE_TEXT` テーブルを作成し、正解テキストを INSERT する

### 記録する項目
- 各ファイルの録音条件（ノイズレベル、話者数、言語、録音環境）を `REFERENCE_TEXT.NOTES` に記載
- 正解テキスト作成者・作成日
- ファイル数、合計再生時間

### 完了条件
- 音声ファイルが10本以上ステージに配置されている
- うち5本以上の正解テキストが `REFERENCE_TEXT` に登録されている
- ファイルの録音条件にばらつきがある

---

## Step 2: AI_TRANSCRIBE 3モード比較

### 目的
default / word / speaker の3モードを同一ファイルで実行し、出力形式・精度・処理時間の違いを定量的に比較する。

### 手順
1. Step 1 のデータセット全ファイルを対象に、3モードを実行する
   - `run_transcribe.py --mode default --file <file>`（全ファイル）
   - `run_transcribe.py --mode word --file <file>`（全ファイル）
   - `run_transcribe.py --mode speaker --file <file>`（複数話者ファイルを中心に）
2. 正解テキストがあるファイルについて `evaluate.py` で CER を算出し、`EVALUATION_RESULT` に保存する
3. speaker モードについては話者分離レポートを出力して目視確認する

### 記録する項目
- モード別の CER（正規化前・後）
- モード別の平均処理時間
- word モードの単語ごと信頼度スコアの分布
- speaker モードの話者分離精度（目視評価）
- エラー率（NULL 返却または error フィールドがあったファイルの割合）
- 特記事項（専門用語・固有名詞・日英混在での挙動）

### 完了条件
- 全ファイル × 3モードの実行ログが `RUN_LOG` に保存されている
- 正解テキストありファイルの CER が `EVALUATION_RESULT` に保存されている
- モード比較の考察が docs/ に記載されている

---

## Step 3: AI_COMPLETE 音声直接分析との比較

### 目的
以下の2つのアプローチを同一ファイルで比較し、精度・コスト・柔軟性の観点で評価する。

| アプローチ | 処理 | Cortex 呼び出し |
|---|---|---|
| A（2段階） | AI_TRANSCRIBE → AI_SENTIMENT / AI_SUMMARIZE | 2回 |
| B（直接） | AI_COMPLETE（音声を直接入力） | 1回 |

### 手順
1. `run_complete_audio.py` で AI_COMPLETE を実行する（要約・感情分析タスク）
   - Step 0 で使ったモデルを起点に、利用可能なモデルを確認して選択する
2. `run_text_analysis.py` で AI_TRANSCRIBE 結果に AI_SENTIMENT / AI_SUMMARIZE を適用する
3. 同一ファイルの A/B 結果を並べてレビューする

### 記録する項目
- アプローチ別の出力品質（要約の完全性、感情分析の正確さ）
- アプローチ別の合計コスト
- アプローチ別の合計処理時間
- AI_COMPLETE が返す構造化 JSON の安定性（スキーマ通りに返ってくるか）

### 完了条件
- A/B 両アプローチの実行ログが `RUN_LOG` に保存されている
- コスト・品質・柔軟性の観点で比較した考察が docs/ に記載されている

---

## Step 4: 評価・コスト集計・レポート作成

### 目的
Step 2〜3 の結果を横断的に集計し、業務利用の可否を判断できる最終レポートを作成する。

### 手順
1. `evaluate.py` で全 RUN_ID の CER を再算出する（正規化ルールを最終版に固定）
2. `cost_report.sql` を実行し、ファイル別・モード別のコストを集計する
3. ACCOUNT_USAGE の反映遅延を考慮し、最終実行から45分以上経過後に再実行する
4. README.md に結果サマリを記載する

### 記録する項目
- モード別の平均 CER（正規化前・後）
- ファイル条件別の CER（ノイズ有無、話者数、日英混在）
- 音声1時間あたりの AI クレジットコスト（モード別）
- WH 稼働コスト（合計・セッション別）
- 運用上の制約（エラーが多い条件、上限に抵触したケース）

### 完了条件
- `EVALUATION_RESULT` に全評価が保存されている
- コスト集計クエリが `05_cost/cost_report.sql` に保存されており再実行可能
- README.md のサマリが最終版になっている
- 業務利用可否の判断材料として必要な情報が docs/ にそろっている
