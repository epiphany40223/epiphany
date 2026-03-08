#!/usr/bin/env python3

# Configuration for sync-ps-to-cc.py: defines the ParishSoft Member
# Workgroup to Constant Contact List synchronization mappings.
# Imported by sync-ps-to-cc.py.

SYNCHRONIZATIONS = [
    {
        'source ps member wg': 'CC SYNC Daily Gospel Reflections',
        'target cc list':      'PS SYNC Daily Gospel Reflections',
        'notifications':       [
            'ps-constantcontact-sync@epiphanycatholicchurch.org,'
            'director-communications@epiphanycatholicchurch.org',
            'business-manager@epiphanycatholicchurch.org',
        ],
    },
    {
        'source ps member wg': 'CC SYNC Epiphany Happenings',
        'target cc list':      'PS SYNC Epiphany Happenings',
        'notifications':       [
            'ps-constantcontact-sync@epiphanycatholicchurch.org,'
            'director-communications@epiphanycatholicchurch.org',
        ],
    },
    {
        'source ps member wg': 'CC SYNC Obituaries',
        'target cc list':      'PS SYNC Obituaries',
        'notifications':       [
            'ps-constantcontact-sync@epiphanycatholicchurch.org,'
            'director-communications@epiphanycatholicchurch.org',
        ],
    },
    {
        'source ps member wg': 'CC SYNC Weekday Mass',
        'target cc list':      'PS SYNC Weekday Mass',
        'notifications':       [
            'ps-constantcontact-sync@epiphanycatholicchurch.org,'
            'director-communications@epiphanycatholicchurch.org',
        ],
    },
]
