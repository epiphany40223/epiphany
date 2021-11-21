#!/usr/bin/env python

THERMO_ECOBEE = "Ecobee"

# Three different data structures to find the underlying thermostats:
#
# 1. Dictionary of thermostats by human-friendly name
# 1. Dictionary of thermostats by Ecobee device name
# 1. Dictionary of lists of thermostats by group name
thermostats_by_name = dict()
thermostats_by_ecobee_name = dict()
thermostat_groups = dict()

def _add_ecobee(name, **kwargs):
    ecobee_name = name
    groups      = list()

    key = 'group'
    if key in kwargs:
        groups.append(kwargs[key])
    key = 'groups'
    if key in kwargs:
        groups = kwargs[key]
    key = 'ecobee_name'
    if key in kwargs:
        ecobee_name = kwargs[key]

    # Sanity check to make sure we don't have any duplicates
    error = False
    if name in thermostats_by_name:
        print(f"ERROR: Two thermostats have the same name ({name})")
        error = True
    if ecobee_name in thermostats_by_ecobee_name:
        print(f"ERROR: Two thermostats have the same Ecobee name ({ecobee_name})")
        error = True

    if error:
        print("ERROR: This is a programming error in ECC/Thermostats.py")
        print("ERROR: Cannot continue")
        exit(1)

    item = {
        'type'        : THERMO_ECOBEE,
        'name'        : name,
        'ecobee name' : ecobee_name,
        'groups'      : groups,
    }
    thermostats_by_name[name] = item
    thermostats_by_ecobee_name[ecobee_name] = item

    for group_name in groups:
        if group_name not in thermostat_groups:
            thermostat_groups[group_name] = list()
        thermostat_groups[group_name].append(item)

# Call _add_ecobee() once for each Ecobee thermostat we have registered to
# the ECC Ecobee account.
_add_ecobee("Narthex", group="WC / Connector",
            ecobee_name="NARTHEX")
_add_ecobee("Connector 1", group="WC / Connector",
            ecobee_name="CON 1")
_add_ecobee("Connector 2", group="WC / Connector",
            ecobee_name="CON 2")

_add_ecobee("Hall",
            groups=[ "CC Kitchen", "CC Library", "CC Nursery", "CC Common" ])
_add_ecobee("Library", group="CC Library")
_add_ecobee("Nursery", group="CC Nursery")
_add_ecobee("Kitchen", group="CC Kitchen",
            ecobee_name='SERVICE KITCHEN')

_add_ecobee("CC F", group="CC Common")
_add_ecobee("CC H", group="CC Common")
_add_ecobee("CC L", group="CC Common")
_add_ecobee("CC J", group="CC Common")
