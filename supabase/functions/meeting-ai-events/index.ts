// Meeting AI Analyser - anonymous product telemetry
//
//   POST /meeting-ai-events  { hwid, event, props?, app_version?, email? }
//
// Purpose: answer "where do trials actually die?". Today the funnel is blind
// between "trial started" and "bought a license", which is exactly the stretch
// where users are lost (Claude not configured, no audio device, no analysis).
//
// Deliberately minimal: no IP, no audio, no transcript, no meeting content.
// A daily unique index on (hwid, event, day) caps volume per install.

import { createClient } from "npm:@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, x-client-info, apikey, content-type",
  "access-control-allow-methods": "POST, OPTIONS",
};

// Allowlist: an unknown event name is dropped, so a stale client can never
// pollute the funnel metrics with typos or renamed events.
const EVENTS = new Set([
  "app_launched",        // app started
  "trial_started",       // email submitted, trial created
  "claude_configured",   // CLI detected or API key saved
  "analysis_success",    // first structured summary produced  <- activation
  "analysis_failed",     // Claude call failed (props.reason)
  "transcription_start", // audio capture running
  "meeting_completed",   // >= 5 min of transcription in one session
  "buy_clicked",         // clicked Buy from inside the app
  "license_activated",   // key accepted
  "trial_expired_seen",  // saw the expiry wall
]);

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

  const body = await req.json().catch(() => ({}));

  const hwid = String(body.hwid ?? "").trim();
  const event = String(body.event ?? "").trim();
  const email = String(body.email ?? "").trim().toLowerCase() || null;
  const appVersion = String(body.app_version ?? "").trim().slice(0, 32) || null;

  if (hwid.length < 16 || hwid.length > 128) return json({ error: "invalid hwid" }, 400);
  if (!EVENTS.has(event)) return json({ ok: true, ignored: true });

  // props: shallow, small, string values only.
  const props: Record<string, string> = {};
  if (body.props && typeof body.props === "object") {
    for (const [k, v] of Object.entries(body.props).slice(0, 10)) {
      props[String(k).slice(0, 40)] = String(v).slice(0, 200);
    }
  }

  await supabase
    .from("meeting_ai_events")
    .insert({ hwid, email_normalized: email, event, props, app_version: appVersion })
    .select()
    .maybeSingle();
  // Conflict on the daily unique index is expected and fine - first write wins.

  // Activation is the single metric that matters between install and purchase:
  // a trial that never produced one summary will never buy.
  if (event === "analysis_success") {
    await supabase
      .from("meeting_ai_trials")
      .update({ activated_at: new Date().toISOString() })
      .eq("hwid", hwid)
      .is("activated_at", null);
  }

  if (appVersion) {
    await supabase
      .from("meeting_ai_trials")
      .update({ app_version: appVersion })
      .eq("hwid", hwid);
  }

  return json({ ok: true });
});

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json", ...CORS },
  });
}
