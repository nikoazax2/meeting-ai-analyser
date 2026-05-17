// Meeting AI Analyser - Trial edge function
// Endpoints:
//   POST /meeting-ai-trial/start    { email, hwid } -> { status, token, expires_at, days_left }
//   POST /meeting-ai-trial/validate { token, hwid } -> { valid, status, expires_at, days_left }
//
// Uses service_role to bypass RLS on public.meeting_ai_trials.

import { createClient } from "npm:@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const APP = "meeting-ai-analyser";

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, x-client-info, apikey, content-type",
  "access-control-allow-methods": "POST, OPTIONS",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS });
  }
  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  const url = new URL(req.url);
  const action = url.pathname.split("/").filter(Boolean).pop();
  const body = await req.json().catch(() => ({}));

  try {
    if (action === "start") return await startTrial(body, req);
    if (action === "validate") return await validateTrial(body);
    return json({ error: "Unknown action" }, 400);
  } catch (e) {
    return json({ error: String(e?.message ?? e) }, 500);
  }
});

async function startTrial(body: any, req: Request) {
  const email = String(body.email ?? "").trim().toLowerCase();
  const hwid = String(body.hwid ?? "").trim();

  if (!email || !hwid) return json({ error: "email and hwid required" }, 400);
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return json({ error: "invalid email" }, 400);
  }
  if (hwid.length < 16 || hwid.length > 128) {
    return json({ error: "invalid hwid" }, 400);
  }

  // Existing row by email
  const { data: byEmail } = await supabase
    .from("meeting_ai_trials")
    .select("*")
    .eq("email_normalized", email)
    .eq("app", APP)
    .maybeSingle();

  // Existing row by hwid
  const { data: byHwid } = await supabase
    .from("meeting_ai_trials")
    .select("*")
    .eq("hwid", hwid)
    .eq("app", APP)
    .maybeSingle();

  const existing = byEmail ?? byHwid;

  if (existing) {
    // Same identity (email AND hwid match): return token regardless of status.
    if (
      existing.email_normalized === email && existing.hwid === hwid
    ) {
      const expired = new Date(existing.expires_at).getTime() < Date.now();
      return json({
        status: expired ? "expired" : "active",
        token: existing.token,
        expires_at: existing.expires_at,
        days_left: daysLeft(existing.expires_at),
      });
    }
    // Mismatch: block (one of email/hwid is already used by a different combo)
    const expired = new Date(existing.expires_at).getTime() < Date.now();
    return json({
      status: "already_used",
      message: expired
        ? "A previous trial for this email or computer has expired."
        : "A trial is already active for this email or computer.",
      expires_at: existing.expires_at,
    });
  }

  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null;
  const { data: created, error } = await supabase
    .from("meeting_ai_trials")
    .insert({ email, hwid, last_seen_ip: ip })
    .select()
    .single();

  if (error || !created) {
    return json({ error: error?.message ?? "insert failed" }, 500);
  }

  return json({
    status: "active",
    token: created.token,
    expires_at: created.expires_at,
    days_left: daysLeft(created.expires_at),
  });
}

async function validateTrial(body: any) {
  const token = String(body.token ?? "").trim();
  const hwid = String(body.hwid ?? "").trim();
  if (!token || !hwid) {
    return json({ valid: false, error: "token and hwid required" }, 400);
  }

  const { data: row } = await supabase
    .from("meeting_ai_trials")
    .select("*")
    .eq("token", token)
    .eq("app", APP)
    .maybeSingle();

  if (!row || row.hwid !== hwid) {
    return json({ valid: false, status: "not_found" });
  }

  const expired = new Date(row.expires_at).getTime() < Date.now();

  // Best-effort last_seen update (don't fail if it errors)
  await supabase
    .from("meeting_ai_trials")
    .update({ last_seen_at: new Date().toISOString() })
    .eq("id", row.id);

  return json({
    valid: !expired,
    status: expired ? "expired" : "active",
    expires_at: row.expires_at,
    days_left: daysLeft(row.expires_at),
  });
}

function daysLeft(expiresAt: string): number {
  const ms = new Date(expiresAt).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / 86_400_000));
}

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json", ...CORS },
  });
}
