// Meeting AI Analyser - LemonSqueezy webhook
//
//   POST /meeting-ai-webhook   (configured in LemonSqueezy > Settings > Webhooks)
//
// Marks a trial as converted the moment the order lands. Without this, buyers
// keep receiving "your trial expires tomorrow" emails, which is the fastest way
// to make a new customer regret paying.
//
// Required secret: LEMONSQUEEZY_WEBHOOK_SECRET (the signing secret you set when
// creating the webhook). Subscribe to: order_created.

import { createClient } from "npm:@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const SECRET = Deno.env.get("LEMONSQUEEZY_WEBHOOK_SECRET") ?? "";

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

  const raw = await req.text();
  const signature = req.headers.get("x-signature") ?? "";

  if (!SECRET || !(await verify(raw, signature))) {
    return json({ error: "invalid signature" }, 401);
  }

  const payload = JSON.parse(raw);
  const eventName = payload?.meta?.event_name ?? "";
  const attrs = payload?.data?.attributes ?? {};

  const email = String(attrs.user_email ?? "").trim().toLowerCase();
  if (!email) return json({ ok: true, ignored: "no email" });

  if (eventName === "order_created" || eventName === "license_key_created") {
    const { data } = await supabase
      .from("meeting_ai_trials")
      .update({ converted_at: new Date().toISOString() })
      .eq("email_normalized", email)
      .is("converted_at", null)
      .select("id");

    return json({ ok: true, event: eventName, matched: data?.length ?? 0 });
  }

  return json({ ok: true, ignored: eventName });
});

/** LemonSqueezy signs the raw body with HMAC-SHA256, hex encoded. */
async function verify(raw: string, signature: string): Promise<boolean> {
  if (!signature) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(raw));
  const expected = [...new Uint8Array(mac)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  // Constant-time compare.
  if (expected.length !== signature.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) {
    diff |= expected.charCodeAt(i) ^ signature.charCodeAt(i);
  }
  return diff === 0;
}

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json" },
  });
}
