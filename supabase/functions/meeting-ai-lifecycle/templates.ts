// Meeting AI Analyser - trial lifecycle email copy.
//
// Rules this copy follows, because they are what makes trial email convert:
//   - one job per email, one link
//   - written from a person, not a brand ("I read every reply")
//   - the not-activated track sells nothing: it fixes the setup first
//   - the activated track sells, because they have already seen the value
//
// Change SENDER_NAME / FROM below to whatever you want on the envelope.

export const SENDER_NAME = "Nicolas";
export const FROM = "Nicolas <nicolas@meeting-ai-analyser.com>";
export const REPLY_TO = "nicolas@meeting-ai-analyser.com";
export const SITE = "https://www.meeting-ai-analyser.com";
export const CHECKOUT =
  "https://meetingai.lemonsqueezy.com/checkout/buy/08d1e75e-f0be-4522-94d6-08def3bf62ce";

// Create this discount in LemonSqueezy before the win-back email goes out.
export const WINBACK_CODE = "COMEBACK20";
export const WINBACK_PRICE = "23";
export const FULL_PRICE = "29";

export type Audience = "all" | "activated" | "not_activated";

export interface Step {
  key: string;
  audience: Audience;
  /** Days after started_at. Negative values are days before expires_at. */
  offsetDays: number;
  anchor: "start" | "expiry";
  subject: string;
  preheader: string;
  body: (ctx: Ctx) => string;
}

export interface Ctx {
  daysLeft: number;
  unsubscribeUrl: string;
}

// ------------------------------------------------------------------ sequence

export const STEPS: Step[] = [
  {
    key: "d0_welcome",
    audience: "all",
    anchor: "start",
    offsetDays: 0.02, // ~30 minutes in
    subject: "One setting, then your next meeting writes itself",
    preheader: "Connect Claude once. Everything after that is automatic.",
    body: () => `
<p>Your 7-day trial is active. There is exactly one thing to set up, and it takes about two minutes.</p>

<p>Transcription already runs on its own, locally. The AI summaries need a Claude connection, so pick whichever you already have:</p>

<p><strong>You already pay for Claude</strong> (Pro, Max or Team)<br>
Install Claude Code, run <code>claude</code> once in a terminal to sign in, then restart the app. No extra cost on top of your plan.</p>

<p><strong>You would rather not install a CLI</strong><br>
Open <strong>Settings</strong> in the app and paste an Anthropic API key from console.anthropic.com. No CLI, no subscription. It costs a few cents per meeting.</p>

<p>Then join any call. Teams, Zoom, Meet, Webex, a phone call on speaker. Nothing joins the meeting and nobody sees a recorder. After about a minute, the first summary appears on the right.</p>

${cta("Open the app", "http://localhost:5555")}

<p>If that panel stays empty, hit reply and tell me what you see. I read every message.</p>`,
  },

  {
    key: "d1_setup",
    audience: "not_activated",
    anchor: "start",
    offsetDays: 1,
    subject: "Your analysis panel is still empty",
    preheader: "It is almost always one of three things. All three are quick.",
    body: () => `
<p>Your trial started yesterday and the app has not produced a summary yet. In practice it is almost always one of these three:</p>

<p><strong>1. Claude Code is installed but not signed in.</strong><br>
Open a terminal, type <code>claude</code>, sign in once, restart the app.</p>

<p><strong>2. Claude Code is not installed at all.</strong><br>
Skip it entirely. Open <strong>Settings</strong> in the app, paste an Anthropic API key, save. That path needs no CLI and no subscription.</p>

<p><strong>3. No audio is reaching the app.</strong><br>
Windows needs an active playback device. If you are on Bluetooth headphones, switch to your speakers once and check that text starts scrolling on the left.</p>

<p>Quick way to tell them apart: if text <em>is</em> scrolling on the left, capture works fine and only the Claude connection needs fixing.</p>

${cta("Open Settings", "http://localhost:5555")}

<p>Reply with what you are seeing and I will tell you which one it is. Usually a one-line answer.</p>`,
  },

  {
    key: "d3_help",
    audience: "not_activated",
    anchor: "start",
    offsetDays: 3,
    subject: "Want me to just look at it with you?",
    preheader: "Your trial clock is running and you have not gotten value yet.",
    body: (c) => `
<p>You are ${c.daysLeft} days into the trial and the app still has not produced a summary. That is my problem, not yours.</p>

<p>Two options, both fine by me:</p>

<p><strong>Tell me what is on your screen.</strong> Reply to this email with what the analysis panel says. Most setups get fixed in one exchange.</p>

<p><strong>Or let the clock reset.</strong> If now is a bad week, say the word and I will extend your trial so you get a real 7 days once you have a meeting to test it on. No catch, just reply "extend".</p>

<p>I would genuinely rather fix this than have you leave thinking the product does not work.</p>`,
  },

  {
    key: "d3_tips",
    audience: "activated",
    anchor: "start",
    offsetDays: 3,
    subject: "Three things people miss in the first week",
    preheader: "Small habits that make the summaries much better.",
    body: () => `
<p>Your summaries are running, so here are the three things that make the biggest difference once the basics work:</p>

<p><strong>1. Trigger an analysis manually at the end of a call.</strong><br>
The automatic pass runs on a timer. Hitting analyse right before people hang up gives you a clean, complete debrief instead of one that stops 40 seconds short.</p>

<p><strong>2. Let it run through the small talk.</strong><br>
Decisions get made in the last five minutes and in the "one last thing" after the agenda ends. That is exactly the part people forget to write down.</p>

<p><strong>3. Use it on calls in a language you are not comfortable in.</strong><br>
This is the use case people write to me about most. Live transcription plus translation turns a call you would have survived into one you can actually steer.</p>

<p>What are you using it for? Genuinely curious. One line back is plenty, and it shapes what I build next.</p>`,
  },

  {
    key: "d5_case",
    audience: "all",
    anchor: "start",
    offsetDays: 5,
    subject: "Why there is no bot in your meetings",
    preheader: "The design decision behind the whole product.",
    body: () => `
<p>Two days left on your trial, so here is the reasoning behind the one thing that makes this product different.</p>

<p>Otter, Fireflies and tl;dv all work by sending a bot into your call. That bot appears in the participant list. Everyone sees it. In a lot of companies IT blocks it outright, and in client calls it changes the conversation the moment people notice they are being recorded by a third party.</p>

<p>Meeting AI Analyser captures the audio your computer is already playing. Nothing joins the call. Nobody sees anything. The audio is transcribed on your own machine and never leaves it, and only the text is sent to Claude for the summary.</p>

<p>That is also why it is a one-time ${FULL_PRICE} EUR rather than a monthly seat: there is no server of mine processing your meetings, so there is nothing for me to bill you for every month.</p>

${cta(`Keep it for ${FULL_PRICE} EUR once`, CHECKOUT)}

<p>14-day money-back guarantee, no questions asked.</p>`,
  },

  {
    key: "d6_expiring",
    audience: "all",
    anchor: "expiry",
    offsetDays: -1,
    subject: "Your trial ends tomorrow",
    preheader: `${FULL_PRICE} EUR once, then it is yours for good.`,
    body: () => `
<p>Your trial ends tomorrow. After that, transcription and analysis stop until a license key is entered.</p>

<p>The license is <strong>${FULL_PRICE} EUR, paid once</strong>. Not per month, not per user, not per hour of audio. You keep the version you bought forever, updates included, and there is a 14-day refund if it turns out not to fit.</p>

<p>For comparison, the cloud tools that do roughly the same thing run 10 to 30 EUR per user per <em>month</em>, and they put a bot in your calls to do it.</p>

${cta(`Get the license - ${FULL_PRICE} EUR`, CHECKOUT)}

<p>Your key arrives by email straight after checkout. Paste it into the app, and everything picks up exactly where it left off.</p>

<p>If you are not buying, I would still like to know why. One line, brutally honest, is worth a lot to me.</p>`,
  },

  {
    key: "d8_winback",
    audience: "all",
    anchor: "expiry",
    offsetDays: 1,
    subject: `Last thing, then I stop emailing you`,
    preheader: `${WINBACK_PRICE} EUR if you want it. Otherwise no hard feelings.`,
    body: () => `
<p>Your trial has expired and you did not buy, which is completely fine. This is the last email I will send you.</p>

<p>If the price was the sticking point, here is <strong>20% off</strong> with the code <strong>${WINBACK_CODE}</strong> at checkout, which brings it to ${WINBACK_PRICE} EUR once.</p>

${cta(`Use ${WINBACK_CODE} - ${WINBACK_PRICE} EUR`, `${CHECKOUT}?checkout[discount_code]=${WINBACK_CODE}`)}

<p>If it was something else, I would really like to know what. Wrong tool for your meetings? Setup too fiddly? Summaries not good enough? Reply with a few words and I will read it properly. That feedback is worth more to me than the sale.</p>

<p>Either way, thanks for giving it a run.</p>`,
  },
];

// ------------------------------------------------------------------ rendering

function cta(label: string, url: string): string {
  return `<p style="margin:28px 0">
  <a href="${url}" style="background:#d97757;color:#fff;text-decoration:none;padding:12px 22px;border-radius:8px;display:inline-block;font-weight:600">${label}</a>
</p>`;
}

export function renderHtml(step: Step, ctx: Ctx): string {
  return `<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f6f6f5">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">${step.preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f6f5;padding:32px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:12px;padding:32px">
<tr><td style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;font-size:16px;line-height:1.6;color:#1f2328">
${step.body(ctx)}
<p style="margin-top:28px">&mdash; ${SENDER_NAME}<br>
<span style="color:#6b7280;font-size:14px">Meeting AI Analyser</span></p>
</td></tr>
</table>
<p style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;font-size:12px;color:#9ca3af;max-width:560px;margin:16px auto 0;text-align:center">
You are getting this because you started a free trial of Meeting AI Analyser.<br>
<a href="${ctx.unsubscribeUrl}" style="color:#9ca3af">Unsubscribe</a> &middot;
<a href="${SITE}" style="color:#9ca3af">meeting-ai-analyser.com</a>
</p>
</td></tr>
</table>
</body></html>`;
}

export function renderText(step: Step, ctx: Ctx): string {
  const plain = step
    .body(ctx)
    .replace(/<a[^>]*href="([^"]*)"[^>]*>([^<]*)<\/a>/g, "$2: $1")
    .replace(/<br\s*\/?>/g, "\n")
    .replace(/<\/p>/g, "\n\n")
    .replace(/<[^>]+>/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return `${plain}\n\n-- ${SENDER_NAME}\nMeeting AI Analyser\n\nUnsubscribe: ${ctx.unsubscribeUrl}`;
}
