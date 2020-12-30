# Stewardship 2021

Much of this is directly copied from the Stewardship 2020 folder.  Only some of it has been updated for Stewardship 2021 so far.

## Overall architecture

There's a bunch of Python scripts in this directory which were used to
run the entire campaign.  All of this was run by hand by Jeff Squyres.
Each script was usually tweaked before each run for its specific use.
This is *not* a "canned" solution where you push a single button an
all the magic happens -- it's a pretty manual process, and is
hand-tweaked as needed.

For the 2021 Stewardship campaign, the following schedule was used:

* Aug 15/16: Will have final list of ministries
* Aug 15/16 or 22/23: Parishioners get a full timeline of stewardship renewal events
* Mon Aug 24: Do a trial run with Stewardship committee
    * Let’s just do Stewardship -- not PPC/FAC/etc.
* Aug 29/30: Overall drive start date:
    * Prayerful reflection, etc.
    * NOTE: Derby is Sep 5/6
* Fri Sep 18: Send snail mail packets to people who don’t have email
* Sat Sep 19: Send initial emails (before 5:30pm mass)
* Sep 19/20: Ministry fair
* Sep 26/27: Stewardship celebration
* Tue 29 Sep: 1st reminder email
* Tue 6 Oct: 2nd reminder email
* Tue 13 Oct: 3rd reminder email
* Tue 20 Oct: 4th reminder email
* Thu 29 Oct: “Last call” reminder email -- "Electronic submission is open through Oct 31."
* Mon 2 Nov: Turn off submission
* ...after...: send "thank you" emails

There are a few main scripts in this directory:

* `make-and-send-emails.py`: This is the script that sends out the
  individual emails to PDS Families for the initial round and for all
  the subsequent reminders.
* `nightly-reports.py`: This script runs the nightly reports, uploads
  Google Sheets, and sends emails with `.csv` files suitable for
  importing into PDS.
* `copy-while-running.zsh`: This script should be run while
  `make-and-send-emails.py` is running.  It continually scp's
  `cookies.sqlite3` to the web site.  The reason for this is because
  the `make-and-send-email` script takes a while to run (~20 mins) --
  continually copying the cookies as we send allows recipients to
  click on the links in their email "immediately" after receiving it.
* `pledge-fullfillment-report.py`: This script was run once at the end of the campaign.  It emits a spreadsheet that needs to be massaged by the business manager and imported into PDS with pledge frequency and mechanism information.

There were some "helper" scripts, too:

* `helpers.py`: Some common / shared Python routines invoked by
  multiple `.py` scripts.
* `constants.py`: Common constants shared by multiple `.py` scripts.
* `print-member.py`: Trivial debugging script to print out a given PDS
  Member or Family.  It was just used to help write / debug the other
  scripts.
* `print-ministries.py`: Trivial script to print out all the PDS
  ministries.  It was just used to make the Jotform that lists all the
  ministries.
* `salutations.py`: trivial script to print all Heads of Households / Spouses into a CSV.  It's more of a test script than a production script.

There was an important outside-of-this-system element to the process,
too: a good number of people submitted paper Stewardship cards (in
addition to or instead of using the electronic process).  Any Family
that submitted a paper card had their PDS Family status set to "2021
Stewardship".  This was done in a timely manner: e.g., if they
submitted a paper card at mass on the weekend, they were entered in
PDS on Monday (i.e., before the reminder emails were sent on Tuesday).

## Setup

### PDS Data

The PDS data is pretty much the same as it's always been: download the SQLite3 database from Epiphany and use that with the Python scripts contained herein.

### Redirecting web site

For Stewardship 2021, we setup a Digital Ocean Linux (Ubuntu 20.04) droplet at $5/mo.  The sole purpose of this web site is to convert the cookie links from parishioner emails to the Jotform URLs that will pre-populate all the forms out at Jotform.

The redirecting PHP code is pretty darn simple:

1. Accept an inbound cookie.
1. Look up that cookie in a local SQLite3 database.
1. If found:
    1. Extract the ID from the cookie
    1. Look up the latest URL for that ID (there may be multiple URLs for a given ID; each one will be time-stamped)
    1. HTTP redirect out to that URL
1. If not found, display an appropriate warning/error message.

There's very little decision-making capability in the PHP itself -- effectively, most decisions it makes are included in the SQLite3 database.  The intent is that the PHP is fairly simple / stupid.

The Droplet is setup as Ubuntu 20.04 running Apache.  Its vhost is setup for `api.epiphanycatholicchurch.org`.  I used the LetsEncrypt.org `certbot` to setup SSL on the server, which setup a corresponding cron job to keep the certificates refreshed.  All obvious external URLs for the host are set to HTTP redirect to https://epiphanycatholicchurch.org/ (i.e., links that don't come from emails to parishioners).

## Initial email

Sample command line to send the initial email:

```
./make-and-send-emails.py \
    --smtp-auth-file auth-file.txt \
    --email-content initial-email.html \
    --all \
    --cookie-db cookies.sqlite3 --append \
    |& tee out.txt
scp cookies.sqlite3 api.epiphanycatholicchurch.org:stewardship-2021-data
```

The SMTP auth file contains a single username:password that
authenticates to Google's SMTP relay service (it's *any* ECC Google
account).  This allows us to send from any `@ecc.org` email address (not
just the one that authenticated).

The email is a file that was made from an email Jordan composed in Constant Contact and sent to me.  I extracted the raw HTML and saved it in the file.  I then tweaked the HTML a bit:

1. Removed the Constant Contact footer.
1. Changed the content of the message to be what Angie wanted.
1. Added various `{foo}` Python variable substitutions.

Note that the graphics I used in the emails are from the Constant
Contact email that Jordan sent to me.  I.e., I'm using IMG links that
point out to Constant Contact.  This means that most parishioners will
see the graphics without me needing to do anything.  The alternative
is to include the graphics as attachments to the email itself, and
have the IMG tags refer to those inline attachments.

NOTE: We specifically opted *not* to use inline/embedded images, mainly for two reasons:

1. Most other commercial vendors do not seem to do this.  When I surveyed my INBOX in September 2019, I couldn't find any commercial senders who sent their images as attachments and linked to them inline from the body HTML.  This seems to indicate that it's an industry practice to use image linking (vs. image embedding).
1. When you inline-attach images, Gmail (at least) shows all the attachments at the bottom of the mail (as attachments).  Meaning: the user will see the images twice -- once embedded in the message, and then again at the bottom (in a possibly unordered, jumbled fashion -- just as a list of attachments).  This kinda destroys the look and feel of a carefully-constructed, beautiful email.  Which therefore kinda defeats the point.

## Jotform

We used Jotform.com as our web form processing vendor.  We used the
$39/mo "Silver" plan to get up to 10,000 submissions per month, and
downgraded back to the free tier when we were done.

We tied each Jotform to a Google Sheet: Jotform will immediately
inject a new row on the Sheet immediately upon form submission.  Not
only is this convenient from a "we loves the Google Sheets"
perspective, it also gets the data out of Jotform (so that we don't
have to continually pay $39/mo just to access the submission data).

The Jotform was a fairly large form that included multiple pages:

1. An intro page
1. 7 Member Ministry update pages
1. A family pledge update page

### Reply email

The Jotform was configured to send back a "Thanks, we got your submission!" email upon submitting.  We passed a hidden field with the PDS Family Head of Household + Spouse emails; that hidden field was used as the "to" address for the email.

Sending the email upon submission was a great way for people to know for 100% sure that ECC got their submission.

### Intro page

This was a fairly boilerplate page -- welcome to the stewardship drive, blah blah blah.

Note that due to a bug at Jotform, all the images on the Jotform were hosted at the Digital Ocean Droplet.  See https://www.jotform.com/answers/2534755-Prepopulate-URL-inconsistent-behaviour-on-Safari-and-Chrome-browsers-across-macOS-and-iOS for more details.  Hence, if you look at the 2021 Jotform, you'll now see lots of broken graphics.  This is expected.

### Member Ministry update pages

We had 7 Member Ministry pages because the majority of the parish has 7 Members or less in their PDS Families.  I ran a quick Python query to do this counting: there were only a handful of Families with 8 or more Members.  These Familes were handled manually by Mary (e.g., she ran reports showing their ministries and worked with those Families directly).

We show the Member their name (in read-only fields) and then a series of
tables -- one table for each group of ministries.

The tables have the the ministry names as the rows and then there are
3 additional radio button columns:

- I PARTICIPATE in this ministry.
- I'm INTERESTED in participating.  Please contact me!
- I'm NO LONGER INVOLVED / not interested in this ministry.

We pre-filled in these columns:

- If a PDS Member is active in a given ministry, we set the
  "PARTICIPATE column.
- Otherwise, we set the "NO LONGER INVOLVED" column.

***NOTE:*** due to having *7* Member Ministry forms in a single Jotform led to an explosion of fields that needed to be pre-filled.  It was absolutely necessary to override all the grid field names to be shorter than their defaults.  The grids were all shortened to 3 letters.  If we went much longer than that, the Jotform back-end would not accept all the field values that we pre-populated via the URL.

### Family Pledge Form

We show some read-only information at the top of the page:

- Family name
- Family's 2020 pledge
- How much the Family has contributed so far during CY2020

Then there were several more fields for input:

- Your family's 2021 total ANNUAL pledge:

If that value is greater than 0, we show additional input fields:

- How would you like to fulfill your 2021 pledge?
  - Radio buttons for: weekly, monthly, quarterly, one annual
- I/we would like to GIVE by (choose all that apply):
  - Bank draft (online bill pay through my bank)
  - Online giving: credit card (via Epiphany's WeShare service)
  - Online giving: ACH (via Epiphany's WeShare service)
  - A gift of stock to Epiphany
  - An IRA distribution directly to Epiphany
  - Offertory envelopes
  - Other

### Why not Google Forms?

We did not use Google Forms because of three limitations:

1. There is no good way to pre-fill-in a form.  Jotform allows us to
   submit specifically-formatted URLs with the data to pre-fill in
   each form field.
1. Google Forms also do not allow us to have "hidden" fields.  Jotform
   allows us to pass the MID/FID through the form without the user
   seeing it.
1. Google Forms does not have "read only" fields.  We show users their
   name, their previous pledge info, ...etc. on the Jotforms, and do
   not allow them to change these values -- they are information only.

It would be great to stay entirely within the Google ecosystem, but
Google Forms simply aren't powerful / flexible enough.

## Reminder emails

Sample command line to send reminder emails.  Note the addition of
`--unsubmitted`.  This causes us to download the Jotform Google Sheets
(the URLs for these Google Sheets are in `constants.py`) and calculate
which PDS Families still needs to get a reminder email:

```
./make-and-send-emails.py \
    --smtp-auth-file auth-file.txt \
    --email-content 1st-reminder-email.html \
    --unsubmitted \
    --cookie-db cookies.sqlite3 --append \
    |& tee out.txt
scp cookies.sqlite3 api.epiphanycatholicchurch.org:stewardship-2021-data
```

Notes:

1. The `--unsubmitted` option makes it only send emails to Families
who:
    * have something that wasn't submitted (e.g., any Member in that
      Family doesn't have a Ministry submission, or there is no Family
      pledge submission), *AND*
    * do not have the "2021 Stewardship" Family status set (i.e., they
      did not submit a paper stewardship card)
1. The email file has a slightly different text message, and also uses `{member_links_reminders}` and `{family_pledge_link_reminder}`, which adds "(already submitted)" or "(net yet submitted)" annotations to each of the ministry and pledging links.
2. The `--ministry-spreadsheet` and `--pledge-spreadsheet` options are necessary for:
    1. `--unsubmitted`
    1. Using `{member_links_reminders}` and `{family_pledge_link_reminder}` in the email content

## Cookies file

The cookies SQLite3 file contains the redirects.  It is used by the PHP running on the web server (see above for a more detailed description).

It is very, very important to *append* to this file every time you run so that all the old cookies are preserved (e.g., so that if a parishioner clicks on a link from the first email they got, it still works).

Also, sending all the emails takes time.  E.g., as of September 2019, there are 1200+ active families at Epiphany (which means ~1200 emails must get sent -- each of which take about a second).  Some people may receive the email and click on the links before all the emails have been sent.  Meaning: before the cookies.sqlite3 file has been finalized.

The `copy-while-running.zsh` script makes a copy of the `cookies.sqlite3` database and then safely `scp`s it out to the web server every 5 seconds.  The intent is to run `copy-while-running.zsh` out to the web server while you are running the `make-and-send-emails.py` script.  This keeps continually renewing the `cookies.sqlite3` out on the web sever frequently so that it is ready if someone clicks on their links immediately after receiving the email.

Note: the `copy-while-running.zsh` script makes a "safe" SCP out to the web server by `scp`ing the cookies file to a temporary location (because it takes time to `scp` it out there -- `cookies.sqlite3` will grow over time, and can take 10-60 seconds to `scp` out to the web server) and then running an `ssh` to move the newly-`scp`ed file to its final location where the web server/PHP will read it.

## Nightly reports

The `nightly-reports.py` script contains several reports.  Some of
them were run "nightly" (see below), whereas others were
hand-uncommented and run manually/on-demand.

### Comments report

The comments report was run via cron at 12:07am on Mon-Fri mornings.

On Tuesday-Friday mornings, it reported on the prior 24 hours.  On
Monday morning, it reported on everything since Friday morning.

The comments report makes a simple Google Sheet with the non-empty
comments that were submitted on the Ministry Update Jotform and the
Pledge Jotform.  These are all put into a single Sheet on the
assumption that a human needs to look at these comments during the
campaign, because parishioners tended to ask questions, make requests,
etc.

Hence, we needed to send a (work)daily report to the staff to let them
handle these comments in a timely fashion (vs. waiting until the end
of the campaign and handling all the comments at once).

### Statistics report

Run via cron at the same frequency as the comments report.

This just shows some statistics over the entire duration of the
campaign so far, including a PDF graph shows some progression lines.

### Family pledge results report

This report emits both a CSV and -- just for good measure -- a Google
Sheet with the pledging data.

For the 2021 campaign, it was only run once: at the end of the
campaign.  The ECC business manager successfully imported the CSV to
PDS -- woo hoo!

Honestly, this report should probably be its own `.py` file (and have some of the common routines in `nightly-reports.py` moved into `helpers.py`)

### Family status CSV report

This report emits a CSV that is solely used to set the PDS Family
status to "2021 Stewardship" of any PDS Family who submitted anything
via electronic stewardship at all (any Member Ministry update and/or
Family Pledge form).

For the 2021 campaign, it was only run once: at the end of the
campaign.  The ECC business manager successfully imported the CSV to
PDS -- woo hoo!

***NOTE:**** This report *must* be run and imported to PDS only *AFTER*
the entire campaign is done.  Otherwise, it will screw up the
"reminder" email calculations.

Honestly, this report should probably be its own `.py` file (and have some of the common routines in `nightly-reports.py` moved into `helpers.py`)

### Ministry update report

This report emits an XLSX for each ministry that contains all Members who submitted a change in their ministry status compared to PDS.  Each Member listed in a ministry's spreadsheet will be one of four cases:

1. "Interested": all Members who are _not_
   already active in a given ministry, but marked the "interested"
   column.
1. "No longer interested": all Members who _are_
   active in a ministry, but marked the "not interested" column.
1. "Inconsistent / human must review": data from
   two cases that human staff members / volunteer must review:
   1. The Member is marked in PDS as "active" in a ministry, but the
      Member marked "Interested" on the form.
   1. The Member is _not_ marked in PDS as "active" in a ministry, but
      the Member marked "Participate" on the form.

These XLSX reports are summarily reviewed by humans to check for obvious errors before we run the `interested-ministry-spreadsheets.py` and `squish-ministry-sheets-into-one.py` reports.  Specifically, the XLSX files were uploaded to Google Drive and converted to Google Sheets.

The ECC staff then hand-checked these sheets for errors, inconsistencies, and resolved the two "inconsistent" data cases.  They edited the Google Sheets in place:

1. They deleted rows that were flat-out wrong / known to be incorrect.
1. They resolved the 2 ambiguous cases by editing the "Category" column -- e.g., resetting it to "Interested" or "No longer interested"

Honestly, this report should probably be its own `.py` file (and have some of the common routines in `nightly-reports.py` moved into `helpers.py`)

## Squish ministry spreadsheets

The `squish-ministry-sheets-into-one.py` script downloads all the Google Sheets from a Google Drive folder (i.e., the folder where all the XLSX sheets were uploaded in the "Ministry update report") and makes one giant spreadsheet containing the union of all the data from all the Google Sheets.

It writes a local file named `worksheet-rollup.xlsx`.

## Interested ministry spreadsheet report

The `interested-ministry-spreadsheets.py` script reads PDS data -- i.e., it _must be run after all the new "interested" statuses have been set in PDS! -- and emits an XLSX spreadsheet per ministry for all the people who indicated that they were "interested" in a ministry.

These XLSX sheets were uploaded to Google Drive / converted to Google Sheets, and then given to ministry leaders.  The ministry leaders called these people to follow up on their interest.

## Pledge fullfillment report

In 2019, we had a `pledge-fullfillment-report.py` script that emitted a CSV.

It does not look like we used this in 2020.  I think Mary directly took the pledge data from the main Jotform Google Sheet output.  That Google Sheet had the FID and all the family data that she needed -- she could just directly slice the rows/columns out of that sheet that she needed.

No Python needed!
