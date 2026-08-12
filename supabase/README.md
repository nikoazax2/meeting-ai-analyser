# Backend deployment — telemetry + lifecycle emails

Three things get deployed here. Do them in order; the whole thing is about
40 minutes, most of it waiting on DNS.

| What | Why it matters |
| --- | --- |
| `meeting-ai-events` | Tells you where trials die. Today that stretch is invisible. |
| `meeting-ai-lifecycle` | Emails trial users. Currently **zero** emails are ever sent. |
| `meeting-ai-webhook` | Marks buyers as converted so they stop getting trial emails. |

---

## 1. Database

Run in the Supabase SQL editor, in order:

1. `migrations/002_telemetry_and_lifecycle.sql`
2. `migrations/003_lifecycle_cron.sql` — **after** step 3 below, and replace
   `<CRON_SECRET>` first.

Then run `queries.sql` → **Q1**. That single number tells you whether the next
month should go into distribution or into conversion.

---

## 2. Resend (email sending)

1. Sign up at [resend.com](https://resend.com) — free tier is 3 000 emails/month,
   100/day, which is far more than you need at this stage.
2. **Domains → Add domain** → `meeting-ai-analyser.com`.
3. Add the DKIM, SPF and DMARC records it gives you at your DNS provider.
   Do not skip DMARC — Gmail and Yahoo require it for bulk senders, and
   without it your trial emails land in spam, which is worse than not sending.
4. Wait for the domain to show **Verified** (usually minutes, up to a few hours).
5. **API Keys → Create** → copy it.

Set the sender address in `functions/meeting-ai-lifecycle/templates.ts`
(`FROM` and `REPLY_TO`). Use a real inbox you read — several emails in the
sequence ask for a reply, and those replies are the best product feedback
you will get.

---

## 3. Deploy the functions

```bash
npx supabase login
npx supabase link --project-ref wdcyabcpczqlpvpwrgws

npx supabase secrets set RESEND_API_KEY=re_xxxxxxxx
npx supabase secrets set CRON_SECRET=$(openssl rand -hex 32)     # keep this value
npx supabase secrets set LEMONSQUEEZY_WEBHOOK_SECRET=whsec_xxxx  # from step 4

npx supabase functions deploy meeting-ai-events   --no-verify-jwt
npx supabase functions deploy meeting-ai-lifecycle --no-verify-jwt
npx supabase functions deploy meeting-ai-webhook   --no-verify-jwt
```

`--no-verify-jwt` is required: the desktop app and LemonSqueezy both call these
without a Supabase user session.

**Send yourself every email before switching the cron on:**

```bash
for step in d0_welcome d1_setup d3_help d3_tips d5_case d6_expiring d8_winback; do
  curl -X POST "https://wdcyabcpczqlpvpwrgws.supabase.co/functions/v1/meeting-ai-lifecycle/test" \
    -H "x-cron-secret: $CRON_SECRET" -H "Content-Type: application/json" \
    -d "{\"email\":\"you@example.com\",\"step\":\"$step\"}"
done
```

Then a dry run against real data — sends nothing, shows exactly who would get what:

```bash
curl -X POST "https://wdcyabcpczqlpvpwrgws.supabase.co/functions/v1/meeting-ai-lifecycle/run?dry=1" \
  -H "x-cron-secret: $CRON_SECRET"
```

Only once that output looks right, run `003_lifecycle_cron.sql`.

---

## 4. LemonSqueezy webhook

**Settings → Webhooks → Add endpoint**

- URL: `https://wdcyabcpczqlpvpwrgws.supabase.co/functions/v1/meeting-ai-webhook`
- Signing secret: generate one, set it as `LEMONSQUEEZY_WEBHOOK_SECRET`
- Events: `order_created`

Also create the win-back discount referenced by the last email:
**Discounts → New** → code `COMEBACK20`, 20% off, no expiry.

---

## Safety rails already built in

- A step only sends if it came due in the **last 48 hours**. Turning the engine
  on will not blast your existing back catalogue of old trials.
- One email per trial per run, 40 per run maximum.
- A unique index on `(trial_id, step)` makes a double send impossible even if
  two runs overlap.
- Buyers and unsubscribers are excluded by the query itself.
- One-click unsubscribe, plus `List-Unsubscribe` headers.

To email the existing backlog of old trials, do it deliberately as a one-off
campaign — export them with **Q9** in `queries.sql`. Do not loosen the 48h rule.

---

## Privacy

Telemetry sends an event name, the app version, the existing hardware id and the
trial email. Never audio, transcripts, analyses or meeting content. Users can
turn it off in Settings (`telemetry: false`).

`privacy.html` on the landing page needs a paragraph covering both the telemetry
and the trial emails before this goes live.
