// Meeting AI Analyser - trial lifecycle emails
//
//   POST /meeting-ai-lifecycle/run          (cron, needs x-cron-secret)
//   POST /meeting-ai-lifecycle/run?dry=1    dry run, sends nothing
//   POST /meeting-ai-lifecycle/test         { email, step } send one to yourself
//   GET  /meeting-ai-lifecycle/unsubscribe?t=<trial token>
//
// Required secrets:
//   RESEND_API_KEY   from resend.com, sending domain must be verified
//   CRON_SECRET      any long random string, also used by the pg_cron job
//
// Safety rails that matter on first deploy:
//   - a step is only sent if it came due in the last 48h, so switching this on
//     never blasts the whole back catalogue of old trials
//   - one email per trial per run
//   - unique index on (trial_id, step) makes double sends impossible

import { createClient } from "npm:@supabase/supabase-js@2";
import {
  Ctx,
  FROM,
  REPLY_TO,
  renderHtml,
  renderText,
  Step,
  STEPS,
} from "./templates.ts";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") ?? "";
const CRON_SECRET = Deno.env.get("CRON_SECRET") ?? "";
const FUNCTION_BASE = `${Deno.env.get("SUPABASE_URL")}/functions/v1/meeting-ai-lifecycle`;

const DAY = 86_400_000;
const STALE_AFTER_MS = 2 * DAY; // don't send an email that came due long ago
const MAX_PER_RUN = 40;         // Resend free tier is 100/day

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const action = url.pathname.split("/").filter(Boolean).pop();

  if (action === "unsubscribe") return await unsubscribe(url);
  if (action === "test") return await sendTest(req);

  if (action === "run") {
    if (!CRON_SECRET || req.headers.get("x-cron-secret") !== CRON_SECRET) {
      return json({ error: "forbidden" }, 403);
    }
    return await run(url.searchParams.get("dry") === "1");
  }

  return json({ error: "unknown action" }, 404);
});

// ------------------------------------------------------------------ the run

async function run(dry: boolean) {
  const now = Date.now();

  const { data: trials, error } = await supabase
    .from("meeting_ai_trials")
    .select("id, email, token, started_at, expires_at, activated_at")
    .is("converted_at", null)
    .is("unsubscribed_at", null)
    // Trials started without an email carry a synthetic @trial.invalid address.
    .not("email", "like", "%@trial.invalid")
    .gte("started_at", new Date(now - 25 * DAY).toISOString())
    .order("started_at", { ascending: false })
    .limit(500);

  if (error) return json({ error: error.message }, 500);
  if (!trials?.length) return json({ ok: true, considered: 0, sent: 0 });

  const { data: alreadySent } = await supabase
    .from("meeting_ai_emails")
    .select("trial_id, step")
    .in("trial_id", trials.map((t) => t.id));

  const sentSet = new Set((alreadySent ?? []).map((r) => `${r.trial_id}:${r.step}`));

  const results: unknown[] = [];
  let sent = 0;

  for (const trial of trials) {
    if (sent >= MAX_PER_RUN) break;

    const step = dueStep(trial, sentSet, now);
    if (!step) continue;

    const daysLeft = Math.max(
      0,
      Math.ceil((new Date(trial.expires_at).getTime() - now) / DAY),
    );
    const ctx: Ctx = {
      daysLeft,
      unsubscribeUrl: `${FUNCTION_BASE}/unsubscribe?t=${trial.token}`,
    };

    if (dry) {
      results.push({ email: trial.email, step: step.key, dry: true });
      sent++;
      continue;
    }

    // Claim the slot first. A conflict means a concurrent run took it.
    const { data: claim, error: claimErr } = await supabase
      .from("meeting_ai_emails")
      .insert({ trial_id: trial.id, email: trial.email, step: step.key, status: "sending" })
      .select("id")
      .maybeSingle();

    if (claimErr || !claim) continue;

    const res = await sendEmail(trial.email, step, ctx);

    if (res.ok) {
      await supabase
        .from("meeting_ai_emails")
        .update({ status: "sent", provider_id: res.id ?? null })
        .eq("id", claim.id);
      sent++;
      results.push({ email: trial.email, step: step.key, id: res.id });
    } else {
      // Release the slot so the next run retries this step.
      await supabase.from("meeting_ai_emails").delete().eq("id", claim.id);
      results.push({ email: trial.email, step: step.key, error: res.error });
    }
  }

  return json({ ok: true, considered: trials.length, sent, results });
}

/** First step this trial is due for, or null. */
function dueStep(
  trial: { id: string; started_at: string; expires_at: string; activated_at: string | null },
  sentSet: Set<string>,
  now: number,
): Step | null {
  const started = new Date(trial.started_at).getTime();
  const expires = new Date(trial.expires_at).getTime();
  const activated = trial.activated_at !== null;

  for (const step of STEPS) {
    if (sentSet.has(`${trial.id}:${step.key}`)) continue;
    if (step.audience === "activated" && !activated) continue;
    if (step.audience === "not_activated" && activated) continue;

    const dueAt = step.anchor === "start"
      ? started + step.offsetDays * DAY
      : expires + step.offsetDays * DAY;

    if (now < dueAt) continue;              // not yet
    if (now - dueAt > STALE_AFTER_MS) continue; // missed the window, skip quietly

    return step;
  }
  return null;
}

// ------------------------------------------------------------------ sending

async function sendEmail(to: string, step: Step, ctx: Ctx) {
  if (!RESEND_API_KEY) return { ok: false, error: "RESEND_API_KEY not set" };

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: FROM,
      to: [to],
      reply_to: REPLY_TO,
      subject: step.subject,
      html: renderHtml(step, ctx),
      text: renderText(step, ctx),
      headers: {
        "List-Unsubscribe": `<${ctx.unsubscribeUrl}>`,
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
      },
    }),
  });

  const payload = await res.json().catch(() => ({}));
  if (!res.ok) return { ok: false, error: payload?.message ?? `http ${res.status}` };
  return { ok: true, id: payload?.id as string | undefined };
}

async function sendTest(req: Request) {
  if (!CRON_SECRET || req.headers.get("x-cron-secret") !== CRON_SECRET) {
    return json({ error: "forbidden" }, 403);
  }
  const body = await req.json().catch(() => ({}));
  const to = String(body.email ?? "").trim();
  const stepKey = String(body.step ?? "d0_welcome");
  const step = STEPS.find((s) => s.key === stepKey);
  if (!to || !step) return json({ error: "email and a valid step required" }, 400);

  const res = await sendEmail(to, step, {
    daysLeft: 3,
    unsubscribeUrl: `${FUNCTION_BASE}/unsubscribe?t=preview`,
  });
  return json(res, res.ok ? 200 : 500);
}

// ------------------------------------------------------------------ unsubscribe

async function unsubscribe(url: URL) {
  const token = url.searchParams.get("t") ?? "";
  if (token && token !== "preview") {
    await supabase
      .from("meeting_ai_trials")
      .update({ unsubscribed_at: new Date().toISOString() })
      .eq("token", token);
  }
  return new Response(
    `<!doctype html><meta charset="utf-8">
<title>Unsubscribed</title>
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:460px;margin:15vh auto;text-align:center;color:#1f2328">
  <h1 style="font-size:22px">You are unsubscribed</h1>
  <p style="color:#6b7280;line-height:1.6">You will not get any more emails about your
  Meeting AI Analyser trial. Your license and the app itself are unaffected.</p>
</div>`,
    { headers: { "content-type": "text/html; charset=utf-8" } },
  );
}

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { "content-type": "application/json" },
  });
}
