-- Meeting AI Analyser - Product telemetry + trial lifecycle
--
-- Adds three things the funnel was missing:
--   1. meeting_ai_events   : anonymous in-app telemetry (where do trials die?)
--   2. lifecycle columns   : activation, conversion, unsubscribe, acquisition source
--   3. meeting_ai_emails   : idempotent log of lifecycle emails already sent
--
-- Run in the Supabase SQL editor, or `supabase db push`.

-- ---------------------------------------------------------------- 1. Telemetry

create table if not exists public.meeting_ai_events (
  id            bigint generated always as identity primary key,
  hwid          text not null,
  email_normalized text,
  event         text not null,
  props         jsonb not null default '{}'::jsonb,
  app_version   text,
  created_at    timestamptz not null default now()
);

create index if not exists meeting_ai_events_event_time_idx
  on public.meeting_ai_events (event, created_at desc);
create index if not exists meeting_ai_events_hwid_idx
  on public.meeting_ai_events (hwid, created_at desc);
create index if not exists meeting_ai_events_email_idx
  on public.meeting_ai_events (email_normalized)
  where email_normalized is not null;

-- One row per (hwid, event) per day keeps volume bounded even if a client loops.
create unique index if not exists meeting_ai_events_daily_uidx
  on public.meeting_ai_events (hwid, event, (created_at::date));

alter table public.meeting_ai_events enable row level security;

-- ------------------------------------------------- 2. Lifecycle columns

alter table public.meeting_ai_trials
  add column if not exists activated_at    timestamptz,  -- first successful AI analysis
  add column if not exists converted_at    timestamptz,  -- became a paying customer
  add column if not exists unsubscribed_at timestamptz,
  add column if not exists source          text,         -- utm_source / referrer at download
  add column if not exists app_version     text;

create index if not exists meeting_ai_trials_expires_idx
  on public.meeting_ai_trials (expires_at);
create index if not exists meeting_ai_trials_started_idx
  on public.meeting_ai_trials (started_at desc);

-- ------------------------------------------------- 3. Lifecycle email log

create table if not exists public.meeting_ai_emails (
  id          bigint generated always as identity primary key,
  trial_id    uuid not null references public.meeting_ai_trials(id) on delete cascade,
  email       text not null,
  step        text not null,       -- d0_welcome | d1_setup | d3_value | d5_proof | d6_expiring | d8_winback
  sent_at     timestamptz not null default now(),
  provider_id text,
  status      text not null default 'sent'
);

-- Idempotency: a given trial can never receive the same step twice.
create unique index if not exists meeting_ai_emails_trial_step_uidx
  on public.meeting_ai_emails (trial_id, step);

alter table public.meeting_ai_emails enable row level security;

-- ------------------------------------------------- 4. Funnel view

create or replace view public.meeting_ai_funnel as
select
  date_trunc('week', t.started_at)::date            as week,
  count(*)                                          as trials_started,
  count(*) filter (where t.activated_at is not null) as activated,
  count(*) filter (where t.converted_at is not null) as converted,
  round(100.0 * count(*) filter (where t.activated_at is not null)
        / nullif(count(*), 0), 1)                   as activation_rate_pct,
  round(100.0 * count(*) filter (where t.converted_at is not null)
        / nullif(count(*), 0), 1)                   as conversion_rate_pct
from public.meeting_ai_trials t
group by 1
order by 1 desc;

-- ------------------------------------------------- 5. Backfill activation

-- Mark any trial that already produced a successful analysis as activated.
update public.meeting_ai_trials t
set activated_at = e.first_seen
from (
  select email_normalized, min(created_at) as first_seen
  from public.meeting_ai_events
  where event = 'analysis_success'
  group by email_normalized
) e
where t.email_normalized = e.email_normalized
  and t.activated_at is null;
