-- Run this in your Supabase SQL Editor (supabase.com → project → SQL Editor)

CREATE TABLE IF NOT EXISTS sessions (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at    timestamptz DEFAULT now(),
  pm_context    text        NOT NULL,
  persona_role  text,
  score         integer,
  score_breakdown   jsonb,   -- {pain_discovery, question_quality, metric_coverage}
  flagged_questions jsonb,   -- [{quality, question, reason}]
  revealed_pains    jsonb,   -- {pain_id: reveal_level}
  missed_pains      jsonb,   -- [{id, content}]
  metrics_covered   integer,
  total_questions   integer,
  report            text
);

-- Index for fast retrieval of recent sessions
CREATE INDEX IF NOT EXISTS sessions_created_at_idx ON sessions (created_at DESC);
