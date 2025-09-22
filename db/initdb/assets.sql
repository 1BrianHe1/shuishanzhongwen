-- 先创建 schema
CREATE SCHEMA IF NOT EXISTS content;

-- 在 content schema 下创建枚举类型
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE t.typname = 'media_type' AND n.nspname = 'content'
  ) THEN
    CREATE TYPE content.media_type AS ENUM ('image','audio','video','subtitle','other');
  END IF;
END$$;

-- 在 content schema 下创建表
CREATE TABLE IF NOT EXISTS content.asset (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  media_kind       content.media_type NOT NULL,
  url              TEXT,
  file_path        TEXT,
  mime_type        TEXT,
  size_bytes       BIGINT,
  width            INT,
  height           INT,
  duration_ms      INT,
  checksum_sha256  VARCHAR(64),
  meta             JSONB,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引也加 schema 前缀
CREATE INDEX IF NOT EXISTS idx_asset_kind ON content.asset(media_kind);

CREATE UNIQUE INDEX IF NOT EXISTS ux_asset_checksum
  ON content.asset(checksum_sha256, size_bytes)
  WHERE checksum_sha256 IS NOT NULL;
