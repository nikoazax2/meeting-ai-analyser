-- Meeting AI Analyser - Trial tracking table
-- Server-side enforcement: one 7-day trial per (email OR hwid), per app.

create table if not exists public.meeting_ai_trials (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  email_normalized text generated always as (lower(trim(email))) stored,
  hwid text not null,
  token text not null default replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', ''),
  started_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '7 days',
  last_seen_at timestamptz default now(),
  last_seen_ip inet,
  app text not null default 'meeting-ai-analyser'
);

create unique index if not exists meeting_ai_trials_email_app_uidx
  on public.meeting_ai_trials (email_normalized, app);

create unique index if not exists meeting_ai_trials_hwid_app_uidx
  on public.meeting_ai_trials (hwid, app);

create unique index if not exists meeting_ai_trials_token_uidx
  on public.meeting_ai_trials (token);

-- RLS: no anon access. Only the edge function (service_role) reads/writes.
alter table public.meeting_ai_trials enable row level security;
