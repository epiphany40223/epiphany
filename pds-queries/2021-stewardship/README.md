# Stewardship 2020

## Overall architecture

There's a bunch of Python scripts in this directory which were used to
run the entire campaign.  All of this was run by hand by Jeff Squyres.
Each script was usually tweaked before each run for its specific use.
This is *not* a "canned" solution where you push a single button an
all the magic happens -- it's a pretty manual process, and is
hand-tweaked as needed.

For the 2020 Stewardship campaign, the following schedule was used:

* Friday, September 27: initial emails sent
* Tuesday, October 8: 1st reminder emails sent
* Tuesday, October 15: 2nd reminder emails sent
* Tuesday, October 22: 3rd reminder emails sent
* Tuesday, October 29: 4th reminder emails sent
* Friday, November 1: online form submissions closed, final reports
  run, data distributed to ECC staff
* Saturday, November 2: "thank you" emails sent

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
* `send-thank-you-emails.py`: This script was run once after the
  campaign was over to send a "thank you" email to everyone who
  participated in stewardship.  See below for thoughts on this.
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

There was an important outside-of-this-system element to the process,
too: a good number of people submitted paper Stewardship cards (in
addition to or instead of using the electronic process).  Any Family
that submitted a paper card had their PDS Family status set to "2020
Stewardship".  This was done in a timely manner: e.g., if they
submitted a paper card at mass on the weekend, they were entered in
PDS on Monday (i.e., before the reminder emails were sent on Tuesday).

## Setup

### PDS Data

The PDS data is pretty much the same as it's always been: download the SQLite3 database from Epiphany and use that with the Python scripts contained herein.

### Redirecting web site

For Stewardship 2020, we setup a Digital Ocean Linux (Ubuntu 18.04) droplet at $5/mo.  The sole purpose of this web site is to convert the cookie links from parishioner emails to the Jotform URLs that will pre-populate all the forms out at Jotform.

The redirecting PHP code is pretty darn simple:

1. Accept an inbound cookie.
1. Look up that cookie in a local SQLite3 database.
1. If found:
    1. Extract the ID from the cookie
    1. Look up the latest URL for that ID (there may be multiple URLs for a given ID; each one will be time-stamped)
    1. HTTP redirect out to that URL
1. If not found, display an appropriate warning/error message.

There's very little decision-making capability in the PHP itself -- effectively, most decisions it makes are included in the SQLite3 database.  The intent is that the PHP is fairly simple / stupid.

The Droplet is setup as Ubuntu 18.04 running Apache.  Its vhost is setup for `redirect.epiphanycatholicchurch.org`.  I used the LetsEncrypt.org `certbot` to setup SSL on the server, which setup a corresponding cron job to keep the certificates refreshed.  All obvious external URLs for the host are set to HTTP redirect to https://epiphanycatholicchurch.org/ (i.e., links that don't come from emails to parishioners).

## Initial email

Sample command line to send the initial email:

```
./make-and-send-emails.py \
    --email-content initial-email.html \
    --all \
    --cookie-db cookies.sqlite3 --append \
    |& tee out.txt
scp cookies.sqlite3 redirect.epiphanycatholicchurch.org:stewardship-2020-data
```

The email is a file that was made from an email Jordan composed in Constant Contact and sent to me.  I extracted the raw HTML and saved it in the file.  I then tweaked the HTML a bit:

1. Removed the Constant Contact footer.
1. Added `Dear {family_names} household:`
1. Added:
```
<div><br></div>
<ol>
{member_links}
</ol>
<div><br></div>
```
1. Used `{family_pledge_link}` for the family pledge link.

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

There were two Jotforms.

### Ministry Update Form

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

### Family Pledge Form

We show some read-only information at the top of the form:

- Family name
- Family's 2019 pledge
- How much the Family has contributed so far during CY2019

Then there were several more fields for input:

- Your family's 2020 total ANNUAL pledge:

If that value is greater than 0, we show additional input fields:

- How would you like to fulfill your 2020 pledge?
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
    --email-content 1st-reminder-email.html \
    --unsubmitted \
    --cookie-db cookies.sqlite3 --append \
    |& tee out.txt
scp cookies.sqlite3 redirect.epiphanycatholicchurch.org:stewardship-2020-data
```

Notes:

1. The `--unsubmitted` option makes it only send emails to Families
who:
    * have something that wasn't submitted (e.g., any Member in that
      Family doesn't have a Ministry submission, or there is no Family
      pledge submission), *AND*
    * do not have the "2020 Stewardship" Family status set (i.e., they
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

For the 2020 campaign, it was only run once: at the end of the
campaign.  The ECC business manager successfully imported the CSV to
PDS -- woo hoo!

Honestly, this report should probably be its own `.py` file (and have some of the common routines in `nightly-reports.py` moved into `helpers.py`)

### Family status CSV report

This report emits a CSV that is solely used to set the PDS Family
status to "2020 Stewardship" of any PDS Family who submitted anything
via electronic stewardship at all (any Member Ministry update and/or
Family Pledge form).

For the 2020 campaign, it was only run once: at the end of the
campaign.  The ECC business manager successfully imported the CSV to
PDS -- woo hoo!

***NOTE:**** This report *must* be run and imported to PDS only *AFTER*
the entire campaign is done.  Otherwise, it will screw up the
"reminder" email calculations.

Honestly, this report should probably be its own `.py` file (and have some of the common routines in `nightly-reports.py` moved into `helpers.py`)

### Ministry update CSV report

This report emits 3 CSVs and Google Sheets:

1. "Interested" report: a CSV showing all Members who are _not_
   already active in a given ministry, but marked the "interested"
   column.
   * *INTENT:* This report is summarily reviewed by a human to check
     for obvious errors and then is imported into PDS.  Staff can then
     run PDS reports to see who is newly-interested in their
     ministries.
1. "No longer interested" report: a CSV showing all Members who _are_
   active in a ministry, but marked the "not interested" column.
   * *INTENT*: This data is given to staff to review.  Staff almost
      always want to see the details of who is leaving their
      ministries before we actually take them out in PDS.  Once
      this spreadsheet has been edited to fix any human errors and/or
      other issues, it needs to be manually entered into PDS (due to
      the way PDS imports data, we cannot import this CSV directly --
      it would create a new Ministry Row on a Member, rather than
      closing out an existing Ministry Row).
1. "Inconsistent / human must review" report: a CSV showing data from
   two cases that human staff members / volunteer must review.
   * *INTENT*: A human staff member and/or volunteer must review this
      data before it can be hand-entered into PDS.  Specifically,
      there are two cases that arise from the Ministry Update
      submitted data -- where the Member submitted is not consistent
      with our PDS database:
      1. The Member is marked in PDS as "active" in a ministry, but the
         Member marked "Interested" on the form.
      1. The Member is _not_ marked in PDS as "active" in a ministry, but
         the Member marked "Participate" on the form.

This report was manually run twice during the 2020 campaign:

1. Approximately halfway through the campaign (so that human reviews
of the data could begin).
1. After the campaign ended.

Although these reports were run twice, nothing was imported into PDS
until after the campaign was over (e.g., the "INTERESTED" CSV was
imported all at once after the campaign was over).

Honestly, this report should probably be its own `.py` file (and have some of the common routines in `nightly-reports.py` moved into `helpers.py`)

## Pledge fullfillment report

The `pledge-fullfillment-report.py` script emits a CSV containing:

1. A column indicating whether a Family changed their envelope status or not (i.e., either starting envelopes or stopping envelopes).
1. A column of keywords to add (these keywords will need to be changed each yet)
    * There are frequency keywords (weekly, monthly, quarterly, annual).  If the frequency changes, keywords will be denoted that they must be deleted -- but we don't think that PDS import will delete keywords.  These will need to be hand-entered in PDS.
    * There are also mechanism keywords (credit card 2020, ACH 2020, ... etc.).  Since these are per-year keywords, there will never be any deletions.  Note that we allowed Families to indicate multiple mechanisms on the Jotform, so there may be multiple rows/2020 keywords to add for a single Family.
1. If Families typed something in the "Other" field, it will show up as an "OTHER" comment.  A human staff member will need to react to those -- they are clearly not for import.

-------

# Reflections after the campaign

I'm writing this section on November 2, after all emails and reports
have been run and distributed.

## Feedback from parishioners

The majority of feedback was positive.  Some people weren't happy,
though.  I saw 2-3 comments from parishioners who insisted that the
system did not accept their submissions.  ...but I saw their
submissions in the Jotform Google Sheets -- so I'm not exactly sure
what the parishioner was referring to (I sent followup emails when
requested, but did not hear back from the parishioners with details on
exactly why they though that their submissions were not recorded).

The only thing that I can think of is that the parishioners may have
seen the "PLEASE READ" and warning icons after their submission and
either did not read the text (which told them to make sure to submit
for every member of their household + their pledge form) or did not
understand it.  I.e., they somehow interpreted that iconography to
mean that their submission was not recorded...?

## Direct PDS data import

This was the first year that we were able to directly import the
majority of stewardship data into PDS.

The importance of this cannot be overstated.

* The morning after the campaign was over, several CSVs were directly
  imported into PDS and all that data was safely saved in our
  database.
* Over the next week or two, the staff will sanity check all the
  ministry updates in various Google Sheets.  These Sheets will then
  be downloaded as CSVs and uploaded into PDS (per above, some of the
  data will need to be entered by hand, but the majority of it will be
  automatic).

This is phenomenally valuable.  Not only was this done faster than
ever before, but by it being automated, the possibility of error
during human data re-entry was significantly reduced.

## Ideas for 2021 campaign

### Webform limitations

In the campaign, we had to send a different link for each Family
member's ministry update and then another link for the Family pledge
form.

It would be really great if somehow that could be a single link / a
single form (e.g., with a page for each family Member ministry update
and one for the Family pledge form).

I could not figure out a way to have a "variable" length form on
Jotform.  It might be possible -- I just didn't have enough time to
figure it out.  It may also be possible in a different web form
vendor.

E.g., it could be possible to have 5 (or 10?) Member pages in a single
form.  We pre-fill in as many of them as is relevant for a given
household, and have the page advance/"next" button somehow skip the
empty pages.  ...or something like that...?

If it does become possible, it will certainly change how the output
data is processed, because there will be N ministry updates per
submission.

### HTTP POST vs PUT

We use specifically formatted HTTP POST URLs with all the data to
pre-fill in the forms.

In hindsight, it would be at least a little better to see if we could
PUT this data so that it's just slightly harder for a malicious user
to submit arbitrary data.

In a perfect world, it would be much better to have the web form
vendor use a unique cookie to draw the pre-filled-in data from a
database somewhere (vs. passing the data along in a URL).  I did not
find a cheap vendor that allowed us to do this easily, but it's worth
another investigation at some point.

### "Thank you" emails

One piece of feedback that we got was that some people didn't get a
good sense of whether their submission was recorded or not.

In 2021, it would probably be good to send out emails every midnight
to Families who *completed* their submission that day (i.e., submitted
their pledge form as well as ministry submissions for all Members in
their Family).  This is actually a little tricky:

* On the surface, you can just comb through the Jotform results and,
  for each Family, find the first date where that Family submitted
  their pledge form + all Member ministry updates.  If that date is
  before midnight, send a "thank you" email.
* BUT: there's always an element of census updates during these
  stewardship campaigns.  E.g., we marked a few dozen adult children
  as "inactive" due to feedback during the campaign.  E.g., Smith
  family submits pledge + ministry updates for 2 adults on date X.
  They also submit a comment saying "our adult child no longer lives
  with us."  That comment is not handled until 3 days later (i.e.,
  X+3), so the logic in the above bullet will not catch that the Smith
  family needs to have a "Thank you" email sent.
* Might need to keep an sqlite3 database listing of all "thank you"
  emails sent.  :-\
