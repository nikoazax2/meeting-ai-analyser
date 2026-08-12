# v1.3.0 — Getting started actually works now

This release is almost entirely about the first five minutes. Several things
were quietly stopping people before they ever saw the product work.

## The trial no longer asks for your email

Starting the trial is now one click. There is still an email field, but it is
optional and clearly marked as such — it is only used to send setup help and a
reminder before the trial ends.

Asking for an email on the very first screen of an app whose whole point is that
nothing leaves your machine was a contradiction, and it was stopping most people
from ever getting in.

## The app works when our server does not

If the licensing server was unreachable — corporate proxy, VPN, captive wifi, or
an outage on our side — the trial screen failed and the app became completely
unusable, with no way past it.

The trial now falls back to a local 7-day grant when the server cannot be
reached. A local-first product should never be bricked by someone else's server.

## Analysis failures now tell you what to do

When the AI analysis could not run, the panel just stayed empty forever. No
message, no explanation, nothing to act on.

It now names the actual problem and the fix, in the panel itself:

- Claude Code not installed
- Claude Code installed but not signed in
- no Anthropic API key configured
- API key rejected, or the account is out of credit
- Anthropic unreachable
- analysis timed out

## Fixed: analysis could die silently

When Claude Code was not found, the analysis thread called `sys.exit()`. Because
it runs as a daemon thread, that killed the thread without a word — the app kept
running, the panel stayed empty, and nothing indicated anything was wrong. For
anyone without Claude Code installed, the AI half of the product was silently
dead from launch.

## Anonymous usage events, opt-out

The app now reports a small set of events — launched, analysis succeeded,
analysis failed and why — so setup problems can be found and fixed instead of
guessed at.

It never sends audio, transcripts, analyses or any meeting content. Turn it off
in Settings at any time.

---

**Windows will warn you that the publisher is unknown.** The installer is not
code-signed yet; a certificate is in progress. Click *More info* → *Run anyway*.
