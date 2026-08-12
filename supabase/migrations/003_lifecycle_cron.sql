-- Meeting AI Analyser - hourly trigger for the lifecycle email engine.
--
-- Run this AFTER deploying the meeting-ai-lifecycle function and setting its
-- secrets. Replace <CRON_SECRET> below with the same value you set as the
-- CRON_SECRET function secret.
--
-- Hourly is the right cadence: each email fires within an hour of coming due,
-- and because a trial's clock starts when the user was actually at their
-- computer, sends land at a sane local hour without any timezone handling.

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Idempotent: drop a previous schedule if you are re-running this.
select cron.unschedule('meeting-ai-lifecycle')
where exists (select 1 from cron.job where jobname = 'meeting-ai-lifecycle');

select cron.schedule(
  'meeting-ai-lifecycle',
  '7 * * * *',   -- every hour at :07, off the busy top-of-hour
  $$
  select net.http_post(
    url     := 'https://wdcyabcpczqlpvpwrgws.supabase.co/functions/v1/meeting-ai-lifecycle/run',
    headers := jsonb_build_object(
                 'Content-Type', 'application/json',
                 'x-cron-secret', '<CRON_SECRET>'
               ),
    body    := '{}'::jsonb
  );
  $$
);

-- Check it is registered:
--   select jobname, schedule, active from cron.job;
-- Check recent runs:
--   select * from cron.job_run_details order by start_time desc limit 10;
-- Check what the function actually did:
--   select step, count(*), max(sent_at) from public.meeting_ai_emails group by 1;
