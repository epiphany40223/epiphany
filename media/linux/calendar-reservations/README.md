# ECC Google calendar reservations bot

This bot was created to solve a fairly simple problem: prevent non-ECC staff from reserving ECC Google Calendar rooms.

Specifically, Google only offers two settings for calendar rooms:

1. Automatically accept all non-conflicting events
1. Automatically add all events

Epiphany used to use the first one: automatically _accept_ all events.  In this setting, _anyone in the world_ can book at room at Epiphany; all they need to know is the email address of the room.  If they invite the room, the room will automatically accept.

A few parishioners have accidentally booked rooms this way.  For example:

1. ECC staff member makes a Google calendar event and both reserves a room and invites a non-ECC staff member.
1. The non-staff member gets the calendar event and sees the email address of the room.
1. The non-staff member can then make a new event and invite that room.

There are multiple ways that last step can happen; one way that happened a few times was that the non-ECC staff member simply copy-n-pasted the entire attendee list of a prior event to a new event.  If the prior event included a room, then the room was also invited to the new event (and therefore auto-accepted).

This bot prevents many cases similar to this from happening.  It does not cover _all_ possibilities (e.g., an ECC staff member could accidentally reserve a room), but it does cover the most common errors that we have seen.

# Pre-requisites

This bot has a hard-coded list of email addresses for all the calendars that it monitors.

Note that these calendars should all be set by the respective ECC calendar owners for the "Automatically add all events" (vs. automatically _accept_ non-conflicting events).  This option will allow invitations to be placed on the calendar, but it will not accept or reject the event.  I.e., the room is not "reserved" because the room calendar did not accept (or reject) the event -- it's waiting for some other entity to accept or reject.

This bot fulfills the role of the "other entity".

This bot will periodically sweep all of its monitored calendars and look for events that still need to be accepted or rejected.  If it finds any such events, it applies the following policy:

1. If the event was created by an email address that does not end in `@epiphanycatholicchurch.org` or `@churchofepiphany.com`, reject the event.
1. If the event overlaps another already-accepted event, reject the event.
1. Otherwise, accept the event.

Upon rejection or acceptance, Google will automatically send an email back to the event creator.

# Miscellaneous

A few more points:

1. The bot actually only checks events starting from 31 days ago to 18 months in the future.
    * We did some testing: checking _all_ events on a calendar takes too long.  Effectively checking 19 months only takes a few seconds.
    * Realistically, we only need to worry about events in the (relatively) immediate past and up to a year or so in the future.
1. The bot processes events in the order in which they were created.  E.g., if 2 events attempt to book the same room in the same timeslot, the event that was created first will "win" (i.e., be accepted).  The 2nd event will then conflict with now-accepted event and will be rejected.
1. The bot also monitors some Google calendars that are not actually rooms (e.g., the main Epiphany Events calendar).  Since these calendars do not represent physical resources, conflicts do not matter and are therefore ignored.  Specifically: the policy logic ignores conflicts when deciding whether to accept or reject an event invitation.
