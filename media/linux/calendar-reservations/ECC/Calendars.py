#!/usr/bin/env python

import ECC.Thermostats

# List of Epiphany calendars
calendars = [
    {
        "name" : "Musicians calendar",
        "id" : "churchofepiphany.com_ga4018ieg7n3q71ihs1ovjo9c0@group.calendar.google.com",
        "check_conflicts" : False,
    },
    {
        "name" : "Epiphany Events",
        "id" : "churchofepiphany.com_9gueg54raienol399o0jtdgmpg@group.calendar.google.com",
        "check_conflicts" : False,
    },
    {
        "name" : "Area E (CC)",
        "id" : "churchofepiphany.com_2d3336353235303639373131@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Common", ],
    },
    {
        "name" : "Area F (CC)",
        "id" : "churchofepiphany.com_2d3336333531363533393538@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Common", ],
    },
    {
        "name" : "Area G (CC)",
        "id" : "churchofepiphany.com_2d33363137333031353534@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Common", ],
    },
    {
        "name" : "Area H (CC)",
        "id" : "churchofepiphany.com_2d33353938373132352d343735@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Common", ],
    },
    {
        "name" : "Area I (CC)",
        "id" : "churchofepiphany.com_2d33353739373832333731@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Common", ],
    },
    {
        "name" : "Area J (CC)",
        "id" : "churchofepiphany.com_2d333535383831322d32@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Common", ],
    },
    {
        "name" : "Area K (CC)",
        "id" : "churchofepiphany.com_2d3335333231363832383335@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Common", ],
    },
    {
        "name" : "Area L (CC)",
        "id" : "churchofepiphany.com_2d3335313431363234383230@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Common", ],
    },
    {
        "name" : "Chapel (WC)",
        "id" : "churchofepiphany.com_2d3431353233343734323336@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Coffee Bar Room (CC)",
        "id" : "churchofepiphany.com_2d38343237303931342d373732@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Connector table 1",
        "id" : "churchofepiphany.com_2d3538323334323031353338@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Connector table 2",
        "id" : "churchofepiphany.com_2d3538313436353238373034@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Connector table 3",
        "id" : "churchofepiphany.com_2d3538303631303232333033@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Dining Room (EH)",
        "id" : "churchofepiphany.com_34373539303436353836@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Epiphany House-1-Polycom",
        "id" : "c_188am3mlh8ghkjovnmm43cqqhdgla@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Kitchen (CC)",
        "id" : "churchofepiphany.com_34383131343230342d333531@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Kitchen", ],
    },
    {
        "name" : "Kitchen (EH)",
        "id" : "churchofepiphany.com_2d36363539313732302d343738@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Library (CC)",
        "id" : "churchofepiphany.com_2d3131393638363634343630@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Library", ],
    },
    {
        "name" : "Lighthouse",
        "id" : "churchofepiphany.com_2d38303937383836353134@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Living Room (EH)",
        "id" : "churchofepiphany.com_37313933333139382d323530@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Media cart and projector",
        "id" : "churchofepiphany.com_2d37353236313138352d373236@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Narthex Gathering Area (WC)",
        "id" : "churchofepiphany.com_3334313632303539343135@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "WC / Connector", ],
    },
    {
        "name" : "Nursery (CC)",
        "id" : "churchofepiphany.com_2d353231343439392d34@resource.calendar.google.com",
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Nursery", ],
    },
    {
        "name" : "Projector screen (large)",
        "id" : "churchofepiphany.com_2d39343734383435352d323039@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Projector screen (small)",
        "id" : "churchofepiphany.com_2d37313836393635372d313838@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Quiet Room (WC)",
        "id" : "churchofepiphany.com_2d36343734343332342d353333@resource.calendar.google.com",
        "check_conflicts" : True,
    },
    {
        "name" : "Worship Space",
        "id" : "churchofepiphany.com_33363131333030322d363435@resource.calendar.google.com",
        "check_conflicts" : True,
    }
]

# Test calendars to use when we're debugging
calendars_debug = [
    {
        "name" : "Test calendar #1",
        "id": 'c_bj96menjelb4pecracnninf45k@group.calendar.google.com',
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Common", ],
    },
    {
        "name" : "Test calendar #2",
        "id" : 'c_ncm1ib261lp6c02i46mors4isc@group.calendar.google.com',
        "check_conflicts" : True,
        "thermostat_groups" : [ "CC Library", ],
    }
]

_key = 'thermostat_groups'
for clist in [calendars, calendars_debug]:
    for calendar in clist:
        if _key not in calendar:
            continue

        for group_name in calendar[_key]:
            if group_name not in ECC.Thermostats.thermostat_groups:
                print(f"ERROR: Calendar {calendar['name']} thermostat group name {group_name} not found!")
                print(f"ERROR: This is a programmer error in 'calendars.py' -- exiting to allow a human to fix this")
                exit(1)

            calendar['thermostats'] = ECC.Thermostats.thermostat_groups[group_name]
