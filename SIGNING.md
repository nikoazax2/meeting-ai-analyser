# Code signing — removing the SmartScreen wall

## The problem

`MeetingAIAnalyser-Setup.exe` is unsigned. Every person who downloads it sees:

> **Windows protected your PC**
> Microsoft Defender SmartScreen prevented an unrecognized app from starting.
> Publisher: Unknown publisher

To continue they must click *More info*, then *Run anyway*. Two extra clicks,
past a red-flag security warning, on software that records their meetings.

This sits at the worst possible point in the funnel: after someone has read the
whole landing page, decided to try it, and clicked download. Everything spent
getting them there is lost at the last step, and it disproportionately loses
exactly the cautious, corporate-laptop users this product is aimed at.

Signing is the single highest-leverage product fix available.

---

## What to buy

Two things narrow the choice:

- Since June 2023 the private key must live on FIPS 140-2 Level 2 hardware — a
  USB token or a cloud HSM. You cannot just keep a `.pfx` on disk any more.
- Since August 2024 SmartScreen treats OV and EV certificates identically;
  reputation builds from download volume either way. **Do not pay for EV.**

| Option | Price | Verdict |
| --- | --- | --- |
| **Certum Code Signing in the Cloud** (OV, individual) | ~€100–150/yr | **Start here.** EU CA, issues to individuals, cloud signing via SimplySign so no USB token. |
| Sectigo / SSL.com OV via reseller | ~$220–270/yr | Works, more expensive, usually wants a token or their eSigner cloud. |
| [Azure Artifact Signing](https://azure.microsoft.com/en-us/products/artifact-signing) | ~$10/mo | Cheapest by far, **but individual developers in France are not eligible** — individuals are limited to the US and Canada. Only opens up if you sign as a registered EU company. |

If you ever register a company for this product, revisit Azure Artifact Signing:
EU **organizations** are eligible and $10/month beats everything else.

> Identity validation takes a few days on any of these. Start it now, not the
> week you want to launch.

---

## Wiring it in

`build.bat` and `installer.iss` are already set up. Signing turns on when the
`SIGN_TOOL` environment variable is set, and stays off otherwise so local test
builds keep working.

Set it to your full signtool command, with `$f` where the file goes:

```bat
set SIGN_TOOL=signtool.exe sign /fd SHA256 /tr http://time.certum.pl /td SHA256 /n "YOUR CERT SUBJECT" $f
```

Then `build.bat` signs `MeetingAIAnalyser.exe` before packaging, and Inno Setup
signs the installer and the uninstaller.

Always include the `/tr` timestamp URL. Without it every binary you ship stops
validating the day the certificate expires.

Also set `AppPublisher` in `installer.iss` to **exactly** the certificate
subject — it currently defaults to `Meeting AI Analyser`. A mismatch means the
UAC prompt shows a different name from the certificate, which looks worse than
no name at all.

Verify:

```bat
signtool verify /pa /v dist\MeetingAIAnalyser-Setup.exe
```

---

## Signing is necessary, not instant

A brand-new certificate has no reputation. The first builds may still warn until
enough people download them. What changes immediately is the prompt: it names a
verified publisher instead of saying *Unknown publisher*, which is most of the
trust gap. Reputation then accrues, and it carries across versions — so ship the
same certificate consistently and never let it lapse.

Two things that help while reputation builds, both free:

1. Submit each release to
   [Microsoft's malware analysis portal](https://www.microsoft.com/en-us/wdsi/filesubmission)
   as a developer requesting a false-positive review. Turnaround is usually a
   day or two and it clears warnings faster.
2. Tell people what to expect on the download page. A warning you predicted
   reads as honesty; the same warning unannounced reads as malware. This is
   already written into `download.html` on the landing site.
