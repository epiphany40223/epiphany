# Notes after Stewardship 2024

* Per Captain Capstone project, can we do this whole scheme in free
  AWS tiers with lambda functions?  Specifically: do we really need to
  spin up a Digital Ocean droplet with Apache+PHP every year?

* We can definitely replace parts of make-and-send-email.py by having
  Constant Contact send out the emails instead of us.  This would get
  us out of the sending email business:

  * Have the Constant Contact python sync the list of unsubmitted
    families.
  * In the Contacts created at CC, include the 6-digit Family Code.
    Those can be substituted into the emails that are sent out.

    * The only question is: where to store those Family codes (since
      we can't bulk upload those codes to some field in our ParishSoft
      source of truth).  Maybe instead of random Family codes, have a
      deterministic / repeatable hash of the PS Family Name and the
      stewardship year?  (this would mean we have a different family
      code each year, but the code is constant throughout a single
      drive)
