-- Step 0: RUN_LOG のみ作成
-- Step 1: REFERENCE_TEXT 追加
-- EVALUATION_RESULT は Step 2 以降で追加

USE SCHEMA DB_ANALYTICS.AUDIO_POC;

CREATE TABLE IF NOT EXISTS RUN_LOG (
    RUN_ID             VARCHAR(36)   NOT NULL,
    FILE_NAME          VARCHAR       NOT NULL,
    FUNCTION_NAME      VARCHAR       NOT NULL,       -- AI_TRANSCRIBE / AI_COMPLETE / AI_SENTIMENT
    MODE_OR_MODEL      VARCHAR,                      -- default / word / speaker / モデル名
    OPTIONS            VARIANT,                      -- 実行時オプション（JSON）
    STARTED_AT         TIMESTAMP_LTZ NOT NULL,
    ENDED_AT           TIMESTAMP_LTZ,
    ELAPSED_SEC        FLOAT,
    AUDIO_DURATION_SEC FLOAT,
    RESULT             VARIANT,                      -- 文字起こし・分析結果（JSON）
    ERROR              VARIANT,                      -- return_error_details の出力
    QUERY_ID           VARCHAR,                      -- CORTEX_AI_FUNCTIONS_USAGE_HISTORY との結合キー
    CREATED_AT         TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_RUN_LOG PRIMARY KEY (RUN_ID)
);

-- Step 1: 台本・録音条件
CREATE TABLE IF NOT EXISTS REFERENCE_TEXT (
    FILE_NAME           VARCHAR       NOT NULL,
    REFERENCE_TEXT      VARCHAR       NOT NULL,
    LANGUAGE            VARCHAR       DEFAULT 'ja',
    SPEAKERS            INT           DEFAULT 1,
    CATEGORY            VARCHAR,                        -- 問い合わせ / クレーム / ポジティブ
    ENVIRONMENT         VARCHAR,                        -- 静か / うるさい
    VOICE_TYPE          VARCHAR,                        -- 男性 / 女性
    PII_COUNT           INT,                            -- PII 情報の件数
    DOMAIN_TERM_COUNT   INT,                            -- 専門用語の件数
    NOTES               VARCHAR,
    CREATED_AT          TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_REFERENCE_TEXT PRIMARY KEY (FILE_NAME)
);

-- 既存テーブルへの追加（初回実行時はスキップされる）
ALTER TABLE IF EXISTS REFERENCE_TEXT ADD COLUMN IF NOT EXISTS VOICE_TYPE VARCHAR;

-- Step 2: CER 評価結果
CREATE TABLE IF NOT EXISTS EVALUATION_RESULT (
    EVAL_ID             VARCHAR(36)   NOT NULL,
    RUN_ID              VARCHAR(36)   NOT NULL,         -- RUN_LOG との結合キー
    FILE_NAME           VARCHAR       NOT NULL,
    MODE_OR_MODEL       VARCHAR,
    CER_RAW             FLOAT,                          -- 正規化前 CER
    CER_NORMALIZED      FLOAT,                          -- 正規化後 CER（句読点・空白除去）
    REF_CHAR_COUNT      INT,                            -- 台本の文字数
    HYP_CHAR_COUNT      INT,                            -- 文字起こし結果の文字数
    SUBSTITUTIONS       INT,
    INSERTIONS          INT,
    DELETIONS           INT,
    CREATED_AT          TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_EVALUATION_RESULT PRIMARY KEY (EVAL_ID)
);
