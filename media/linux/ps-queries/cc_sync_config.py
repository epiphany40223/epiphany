#!/usr/bin/env python3

# Configuration for sync-ps-to-cc.py: defines the ParishSoft Member
# Workgroup to Constant Contact List synchronization mappings.
# Imported by sync-ps-to-cc.py.

SYNCHRONIZATIONS = [
    {
        'source ps member wg': 'Daily Gospel Reflections',
        'target cc list':      'SYNC Daily Gospel Reflections',
        'notifications':       [
            'ps-constantcontact-sync@epiphanycatholicchurch.org,'
            'director-communications@epiphanycatholicchurch.org',
        ],
    },
    {
        'source ps member wg': 'Parish-wide Email',
        'target cc list':      'SYNC Parish-wide Email',
        'notifications':       [
            'ps-constantcontact-sync@epiphanycatholicchurch.org,'
            'director-communications@epiphanycatholicchurch.org',
        ],
    },
]
