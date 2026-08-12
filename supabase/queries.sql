-- Meeting AI Analyser - the numbers that decide what to work on next.
-- Paste any block into the Supabase SQL editor.
-- Start with Q1: it tells you whether you have a traffic problem or a
-- conversion problem, and those need completely different work.

-- ============================================================ Q1. THE ONE NUMBER
-- Trials started, ever. Compare against 2 sales.
--   < 30 trials   -> traffic problem. Nobody reaches the product. Go distribute.
--   30-100 trials -> ~2-6% conversion. Below the 10-20% norm for a 7-day trial.
--   > 100 trials  -> conversion problem. They try it and leave. Fix onboarding.
select
  count(*)                                                   as trials_total,
  count(*) filter (where started_at > now() - interval '30 days') as last_30d,
  count(*) filter (where started_at > now() - interval '7 days')  as last_7d,
  min(started_at)::date                                      as first_trial,
  max(started_at)::date                                      as latest_trial
from public.meeting_ai_trials;

-- ============================================================ Q2. WEEKLY FUNNEL
-- Needs migration 002 + a released build with telemetry.
-- activation_rate is the number to watch: a trial that never produced one
-- summary has seen nothing worth 29 EUR.
select * from public.meeting_ai_funnel limit 12;

-- ============================================================ Q3. ARE THEY ALIVE?
-- last_seen_at only updates when the app calls home, so it is a real usage
-- signal. Trials that never came back after day 1 died at setup.
select
  count(*)                                                              as trials,
  count(*) filter (where last_seen_at > started_at + interval '1 day')  as returned_after_d1,
  count(*) filter (where last_seen_at > started_at + interval '3 days') as returned_after_d3,
  round(100.0 * count(*) filter (where last_seen_at > started_at + interval '1 day')
        / nullif(count(*), 0), 1)                                       as pct_returned_d1
from public.meeting_ai_trials
where started_at < now() - interval '3 days';

-- ============================================================ Q4. WHERE IT BREAKS
-- Requires telemetry. Every failure reason, most common first. This is the
-- shortlist of what to fix in the product, ranked by lost revenue.
select
  props->>'reason' as failure_reason,
  count(distinct hwid) as installs_affected,
  count(*) as occurrences
from public.meeting_ai_events
where event = 'analysis_failed'
group by 1
order by installs_affected desc;

-- ============================================================ Q5. STEP-BY-STEP DROP-OFF
-- Absolute counts per funnel step. The biggest gap between two consecutive
-- rows is the single most expensive problem you have.
with steps as (
  select unnest(array[
    'app_launched', 'trial_started', 'claude_configured',
    'transcription_start', 'analysis_success', 'buy_clicked', 'license_activated'
  ]) as event, generate_series(1, 7) as ord
)
select
  s.ord, s.event,
  count(distinct e.hwid) as installs
from steps s
left join public.meeting_ai_events e on e.event = s.event
group by s.ord, s.event
order by s.ord;

-- ============================================================ Q6. ACTIVATED BUT NOT BUYING
-- People who got real value and still did not pay. If this list is long, the
-- problem is price, packaging or the absence of a reminder - not the product.
-- These are also your best candidates for a personal email asking why.
select email, started_at::date, expires_at::date, activated_at::date, last_seen_at
from public.meeting_ai_trials
where activated_at is not null
  and converted_at is null
  and expires_at < now()
order by started_at desc
limit 50;

-- ============================================================ Q7. ACQUISITION SOURCE
-- Populated once download.html passes ?src= through to the trial.
-- Tells you which channel produces buyers, not just clicks.
select
  coalesce(source, '(unknown)') as source,
  count(*) as trials,
  count(*) filter (where activated_at is not null) as activated,
  count(*) filter (where converted_at is not null) as paid
from public.meeting_ai_trials
group by 1
order by trials desc;

-- ============================================================ Q8. EMAILS SENT
-- Sanity check on the lifecycle engine once it is deployed.
select step, count(*) as sent, max(sent_at) as last_sent
from public.meeting_ai_emails
group by 1
order by 1;

-- ============================================================ Q9. EXPORT THE LIST
-- Everyone who ever tried the product and did not buy: your warm audience for
-- a relaunch announcement. Export as CSV from the results panel.
select email, started_at::date as tried_on,
       (activated_at is not null) as got_value
from public.meeting_ai_trials
where converted_at is null
  and unsubscribed_at is null
order by started_at desc;
