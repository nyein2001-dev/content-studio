# Sources - A Bit Inside, 2026-10-13

Topic: **Attackers heated hundreds of French supermarket fridges to 50 °C by hijacking the
store's refrigeration controller.**

All sources below were fetched over the network on **13 October 2026**; the HTTP status is the
real response code recorded by `src/brain/verify.py` and re-checked by `src/qa.py` in the same
run. Nothing in this file is quoted for more than fifteen words, and every `paraphrase` is our
own wording, not the source's.

---

## 1. Verified (stated by a primary or authoritative source)

### 1.1 CERT-FR / ANSSI - alert CERTFR-2026-ALE-012
- **URL:** https://www.cert.ssi.gouv.fr/alerte/CERTFR-2026-ALE-012/ (HTTP 200, 22,554 bytes)
- **Publisher:** CERT-FR, the French national CSIRT, part of ANSSI. Primary.
- **First version:** 12 October 2026. **Last version read:** 13 October 2026.
- **Used for:** `alert_id`, `alert_advice`, `alert_broader`, `alert_still_going`, `unknowns`.
- **Paraphrase:** CERT-FR says it knows of numerous compromises of remote installation
  controllers in the Danfoss AK-SM and AK-SC series, and also lists Copeland xweb and Dixell
  xweb among affected systems. It states that exposing a management interface to the internet
  is contrary to good practice, tells operators to remove the internet exposure and restore
  access only through a secure VPN, and notes that filtering contractors' source IPs on a
  firewall is an emergency measure rather than a lasting one. For suspected compromise it
  lists a factory reset, reconfiguration, a firmware update and a change of default passwords.
  It carries an explicit warning that attack campaigns against this equipment are probably
  still under way. The alert names **no CVE**, no cause and no actor; its risk field reads that
  the editor did not specify it.
- **Honest hedge:** the alert says the exposure is "in general" bad practice. It does not say
  the internet exposure is how this attack happened, and the video does not say it either.

### 1.2 Claroty Team82 - the research and the retailer's account
- **URL:** https://www.claroty.com/blog/france-supermarket-hacks-expose-risks-of-internet-facing-refrigeration-systems
  (HTTP 200, 132,846 bytes, published 12 October 2026)
- **Publisher:** Claroty Team82, the industrial-security research group that found and privately
  disclosed the flaws. Primary for the research; secondary for the retailer's account.
- **Used for:** `attack_temp_c`, `attack_temp_f`, `intermarche_stores`, `exposed_controllers`,
  `vendor_fix_release`, `code_of_the_day`.
- **Paraphrase:** the research found three flaws in the AK-SM 800A platform's embedded web
  management interface: a hidden "code-of-the-day" authentication mechanism that could be used
  to bypass normal authentication, a command-injection flaw leading to remote code execution,
  and a flaw letting an authenticated user inject Nginx configuration directives. The team
  disclosed privately and Danfoss shipped a firmware version in **August 2025** that addressed
  them. Their initial internet scan of exposed AK-SM 800A devices turned up **2,765**. On the
  incident, Groupe Mousquetaire's Intermarché said **150 of its stores** were hit and that the
  temperature controls were remotely pushed to **50 °C / 122 °F**, causing food waste and
  losses the company puts in the hundreds of thousands of euros.
- **Honest hedge:** Claroty itself says it is unknown how many of those 2,765 devices have since
  been updated or are still exposed. The video says "researchers counted", not "there are".

### 1.3 NVD - CVE-2025-41450
- **URL:** https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2025-41450 (HTTP 200)
- **Publisher:** NIST National Vulnerability Database. Primary.
- **Record:** published 8 May 2025, last modified 17 June 2026.
- **Used for:** `cve_auth_bypass`, `cve_cvss`, `fixed_in_version`.
- **Paraphrase:** an improper-authentication flaw (CWE-305) affecting the Danfoss AK-SM 8xxA
  series **prior to version 4.2**, CVSS 3.1 base score **8.2**, severity **HIGH**, network
  attack vector, no privileges required.
- **Note:** the CISA advisory page for this flaw (ICSA-25-140-03) returned HTTP 403 to an
  automated request, so it is deliberately **not** cited. The NVD record is used instead.

### 1.4 The Hacker News - incident timeline and the vendor's account
- **URL:** https://thehackernews.com/2026/10/attackers-heat-french-supermarket.html
  (HTTP 200, published 13 October 2026)
- **Publisher:** trade press. Secondary, but it is the page that carries the retailers' own
  statements and the CERT-FR alert wording, and it is corroborated below.
- **Used for:** `attack_night`, `legacy_model_a`, `legacy_model_b`, `eol_year_a`, `eol_year_b`,
  `current_model`, `second_fix_version`, `prosecutor`, `unknowns`, and as the corroborating
  source for `attack_temp_c` and `intermarche_stores`.
- **Paraphrase:** attackers took remote control of fridges and freezers at hundreds of French
  supermarkets on the night of **11 October**; the cases were put into defrost and heated to as
  much as **50 °C**. CERT-FR's alert of 12 October tells operators to disconnect the controllers
  or filter access. Danfoss told AFP most of the units hit were older products that no longer
  receive software or security updates, naming the **AK-SM 800** (end of life **May 2021**) and
  the **AK-SC 355** (phased out **2016**); some current **AK-SM 800A** units were also hit, on
  outdated firmware. CVE-2025-41450 is an authentication bypass before 4.2;
  CVE-2025-41451 is command injection and CVE-2025-41452 a denial-of-service, both needing a
  login and both fixed in **4.3.1**. The Paris prosecutor opened an inquiry on its own
  initiative. Neither the authorities nor Danfoss has named an actor or a route in, and
  CERT-FR had published no indicators of compromise as of 13 October.
- **Corroboration:** the store-count figure is independently reported by Reuters and AFP with
  different scopes (about 150 Intermarche stores per Reuters; at least 300 for Intermarché and
  Netto together per AFP). The video says "about 150 stores" and attributes it to the chain.

### 1.5 RWP Ventures - independent incident briefing
- **URL:** https://rwp-ventures.blog/posts/2026-10-13-danfoss-ak-sm-certfr-ale-012/
  (HTTP 200, published 13 October 2026)
- **Used for:** corroborating `prosecutor`.
- **Paraphrase:** an independent analyst confirms the Paris prosecutor's inquiry was opened on
  its own initiative, and stresses that CERT-FR's alert names no CVE and that the 2025 AK-SM
  800A CVEs are background rather than a confirmed exploit path for this weekend.

---

## 2. Explained, simplified or illustrative

These are things the video shows that the sources do **not** publish. Each one is labelled
ILLUSTRATIVE on screen, and none of them is ever spoken as a fact.

| id | what we show | why it is ours | how it is labelled |
|---|---|---|---|
| `normal_case_temp` (4 °C) | the flat "healthy" band on the temperature chart | no source consulted publishes the set points of the affected stores' cases; four degrees is a rounded illustration of a chilled case, chosen only to make the gap legible | the chart carries ILLUSTRATIVE; the narration never says "4 degrees" |
| `attack_duration_h` (6 h) | the width of the highlighted overnight window on the chart | sources date the intrusion to the night of 11 October but do not publish a duration | the window carries ILLUSTRATIVE |
| `delta_temp` (46 °C) | the gap between the illustrative band and the sourced 50 °C | arithmetic mixing one sourced number with one illustrative number, computed by the same code that draws the chart | shown only on an ILLUSTRATIVE chart |
| `code_of_the_day` drawing | a calendar page flipping to a generated code | the sources name the mechanism but never publish the algorithm; the video does not claim to know it | the mechanism card is labelled ILLUSTRATIVE |
| every store, case, controller, probe, valve, cable and router | all of the artwork | every graphic in this video is drawn as vector art by `src/render` from mathematical primitives; nothing is a photograph, a screenshot or a third-party image | the video description states all graphics are illustrative |

---

## 3. What we deliberately did not claim

- **Not** which vulnerability was used. CERT-FR named none, Danfoss linked none of the 2025
  CVEs to this attack, and the video says so on screen.
- **Not** who did it. No group has claimed responsibility.
- **Not** an exact store total. Outlets' figures differ in scope; the video uses the chain's own
  "about 150" and says "about".
- **Not** that the controllers were patched in August 2025 *because of* this attack. The
  August 2025 firmware predates the incident by more than a year.
- **Not** that end-of-life means unpatchable-and-therefore-immune. It means no fixes are issued
  any more, which is why CERT-FR's first instruction is to disconnect rather than patch.
- **Not** that Danfoss was breached. Danfoss says it is aware of incidents affecting a limited
  number of systems; no source says its own systems were entered.