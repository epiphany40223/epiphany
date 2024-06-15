#!/usr/bin/env python3

"""Script to iterate through ministries and Member WorkGroups from
ParishSoft Family Suite and sync the membership of a Google Group to
match.

- Use a hard-coded list of ministries+Member WorkGroups and associated
  Google Groups.  NOTE: the ministries, workgroups, and Google Group
  names must match EXACTLY.
- For each:

  - Determine if the Google Group is a Broadcast (only manager/owers
    can post) or Discussion group (anyone can post).
  - Find all PS Members in a given ministry and/or have a given
    Member WorkGroup
  - Find all members of the Google Group
  - Compare the two:
    - Find which PS members should be added to the Google Group
    - Find which email addresses should be removed from the Google Group
    - Find which email addresses in the Google Group need to change
      role (from member -> owner or owner -> member)
  - If not a dry run, do the actions found above

No locking / lockfile is used in this script because it is assumed
that simultaneous access is prevented by locking at a higher level
(i.e., ../run-all.py).

-----

This script uses Google OAuth authentication; it requires a
"client_id.json" file with the app credentials from the Google App
dashboard.  This file is not committed here in git for obvious reasons
(!).

The client_id.json file is obtained from
console.developers.google.com, project name "PDS to Google Groups".
The project is owned by itadmin@epiphanycatholicchurch.org.

This script will create/fill a "user-credentials.json" file in the
same directory with the result of getting user consent for the Google
Account being used to authenticate.

Make sure you install the PIP modules in requirements.txt:

    pip install -r requirements.txt

"""

import os
import re
import sys
import csv
import json
import time
import logging
import httplib2
import logging.handlers

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import Google
import GoogleAuth
import ParishSoftv2 as ParishSoft

import googleapiclient
from google.api_core import retry

from oauth2client import tools

from pprint import pprint
from pprint import pformat

# Globals

args = None
log = None

# Default for CLI arguments
gapp_id='client_id.json'
guser_cred_file = 'user-credentials.json'
verbose = True
debug = False
logfile = "log.txt"

# Google Group permissions
BROADCAST  = 1
DISCUSSION = 2

####################################################################

def get_synchronizations():
    ecc = '@epiphanycatholicchurch.org'

    synchronizations = [
        {
            'ministries' : [ '100-Parish Pastoral Council' ],
            'ggroup'     : f'ppc{ecc}',
            'notify'     : f'bookkeeper{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '102-Finance Advisory Council' ],
            'ggroup'     : f'administration-committee{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '103-Worship Committee' ],
            'ggroup'     : f'worship-committee{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '104-Stewardship & E Committee' ],
            'ggroup'     : f'stewardship{ecc}',
            'notify'     : f'director-parish-engagement{ecc},ps-google-sync{ecc}',
        },
        {
            "ministries" : [ '107-Social Resp Steering Comm' ],
            'ggroup'     : f'social-responsibility-steering-commitee{ecc}',
            'notify'     : f'pastoral-associate-social-resp{ecc},ps-google-sync{ecc}',
        },
        {
            "ministries" : [ '110-Ten Percent Committee' ],
            'ggroup'     : f'ten-percent-committee{ecc}',
            'notify'     : f'pastoral-associate-social-resp{ecc},ps-google-sync{ecc}',
        },
        {
            "workgroups" : [ 'Ten Percent Treasurer' ],
            'ggroup'     : f'ten-percent-treasurer{ecc}',
            'notify'     : f'pastoral-associate-social-resp{ecc},ps-google-sync{ecc}',
        },
        {
            "ministries" : [ '111-Hispanic Ministry Team' ],
            'ggroup'     : f'hispanic-ministry-team{ecc}',
            'notify'     : f'pastoral-associate-social-resp{ecc},ps-google-sync{ecc}',
        },
        {
            "ministries" : [ '113-Media Comms Planning Comm.' ],
            'ggroup'     : f'communications-planning-team{ecc}',
            'notify'     : f'director-communications{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'ministries' : [ '203-Garden & Grounds' ],
            'ggroup'     : f'garden-and-grounds{ecc}',
            'notify'     : f'business-manager{ecc},emswine2@gmail.com,ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '207-Technology Committee' ],
            'ggroup'     : f'tech-committee{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'ministries' : [ '300-Art & Environment' ],
            'ggroup'     : f'art-and-environment-ministry{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '301-Audio/Visual/Light Minstry' ],
            'ggroup'     : f'audio-visual-lighting-ministry{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '304-LiturgicalPlanningDscrnmnt' ],
            'ggroup'     : f'worship-liturgical-planning-discernment{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '305-Movers Ministry' ],
            'ggroup'     : f'movers{ecc}',
            'notify'     : f'director-worship{ecc},awsimpson57@gmail.com,ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '309-Acolytes', ],
            'ggroup'     : f'acolytes{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '310-Adult Choir' ],
            'ggroup'     : f'choir{ecc}',
            'notify'     : f'director-worship{ecc},director-choir{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '311-Bell Choir' ],
            'workgroups' : [ 'Bell choir email list' ],
            'ggroup'     : f'bell-ringers{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '313-Eucharistic Ministers', ],
            'ggroup'     : f'eucharistic-ministers{ecc}',
            'notify'     : f'director-worship{ecc},tonya@cabral.org,ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '315-Funeral Mass Ministry' ],
            'ggroup'     : f'funeral-mass-ministry{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '316-Greeters', ],
            'ggroup'     : f'greeters{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '317-Instrumentalists & Cantors' ],
            'workgroups' : [ 'Musicians email list' ],
            'ggroup'     : f'musicians{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '318-Lectors', ],
            'ggroup'     : f'lectors{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '321-Prayer Chain Ministry' ],
            'ggroup'     : f'prayer-chain-ministry{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'ministries' : [ '404-Welcome Desk' ],
            'ggroup'     : f'welcome-desk{ecc}',
            'notify'     : f'director-parish-engagement{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '407-Stewardship Team' ],
            'ggroup'     : f'stewardship-team{ecc}',
            'notify'     : f'director-parish-engagement{ecc},ps-google-sync{ecc}',
        },

        {
            "workgroups"   : [ 'Name Badges Google Drive acces' ],
            'ggroup'     : f'stewardship-name-badges-google-drive-access{ecc}',
            'notify'     : f'director-parish-engagement{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'ministries' : [ '501-Eucharist to Sick&Homebnd' ],
            'ggroup'     : f'care-for-the-sick{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '505-Healing Blanket Ministry' ],
            'ggroup'     : f'healing-blankets-ministry{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '508-Messages of Hope Ministry' ],
            'ggroup'     : f'messages-of-hope{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'ministries' : [ '600-Men of Epiphany' ],
            'ggroup'     : f'moe{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},moe-chair{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '601-Sages (for 50 yrs. +)' ],
            'ggroup'     : f'sages{ecc}',
            'notify'     : f'joanhagedorn46@gmail.com,pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '602-Singles Explore Life (SEL)' ],
            'ggroup'     : f'sel{ecc}',
            # Lynne Webb
            'notify'     : f'justlmw@att.net,ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '612-Community Life Committee' ],
            'ggroup'     : f'community-life{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            "ministries" : [ '700-Advocates for Common Good' ],
            'ggroup'     : f'advocates-for-the-common-good{ecc}',
            'notify'     : f'pastoral-associate-social-resp{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '707-St. Vincent DePaul' ],
            'ggroup'     : f'SVDPConference{ecc}',
            'notify'     : f'pastoral-associate-social-resp{ecc},ps-google-sync{ecc}',
        },
        {
            "ministries" : [ '709-Twinning Committee:Chiapas' ],
            'ggroup'     : f'twinning-committee{ecc}',
            'notify'     : f'pastoral-associate-social-resp{ecc},ps-google-sync{ecc}',
        },
        {
            "ministries" : [ '710-Environmental Concerns' ],
            'ggroup'     : f'environmental-concerns{ecc}',
            'notify'     : f'pastoral-associate-social-resp{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'ministries' : [ '800-Catechists for Children' ],
            'ggroup'     : f'childrens-formation-catechists{ecc}',
            'notify'     : f'formation{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ '807-Catechumenate/InitiationTm' ],
            'ggroup'     : f'rcia-team{ecc}',
            'notify'     : f'formation{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'ministries' : [ '903-Confirmation Core Team' ],
            'ggroup'     : f'confirmation-core{ecc}',
            'notify'     : f'youth-minister{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'workgroups' : [ 'Livestream Team' ],
            'ggroup'     : f'livestream-team{ecc}',
            'notify'     : f'director-communications{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'ministries' : [ 'E-Taize Prayer' ],
            'ggroup'     : f'taizeprayer{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'ministries' : [ 'E-Soul Life' ],
            'ggroup'     : f'soullife{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'workgroups' : [ 'Apply@ECC email list' ],
            'ggroup'     : f'apply{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Registration@ECC email list' ],
            'ggroup'     : f'registration{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Renovations@ECC email list' ],
            'ggroup'     : f'renovations{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'ECC Liturgy Plans editor' ],
            'ggroup'     : f'worship-liturgy-plans-editor{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Liturgy Planning Ldr' ],
            'ggroup'     : f'worship-liturgy-planning-leadership{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'ECC Liturgy Plans reader' ],
            'ggroup'     : f'worship-liturgy-planning-reader{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'ECC Liturgy Particption Editor' ],
            'ggroup'     : f'worship-liturgy-participation-materials{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'ECC Musicians Info editor' ],
            'ggroup'     : f'music-ministry-musicians-information-editor{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            # JMS To be deleted after 30 May 2020
            'workgroups' : [ 'ECC Sheet Music access' ],
            'ggroup'     : f'music-ministry-sheet-music-access{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Homebound MP3 Recordings' ],
            'ggroup'     : f'mp3-uploads-group{ecc}',
            'notify'     : f'director-worship{ecc},business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Homebound recipients email lst', 'Homebound MP3 Recordings' ],
            'ggroup'     : f'ministry-homebound-liturgy-recipients{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Liturgy Transcriptions' ],
            'ggroup'     : f'liturgy-transcriptions{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Staff: Maintenance' ],
            'ggroup'     : f'maintenance-staff{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Office@ECC email list' ],
            'ggroup'     : f'office-group{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Staff: Pastoral' ],
            'ggroup'     : f'pastoral-staff{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'PPC Executive Committee' ],
            'ggroup'     : f'ppc-exec{ecc}',
            'notify'     : f'bookkeeper{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Recordings access' ],
            'ggroup'     : f'recordings-viewer{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Staff: Support' ],
            'ggroup'     : f'support-staff{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Staff: Auxiliary' ],
            'ggroup'     : f'auxiliary-staff{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Wedding Ministries email list' ],
            'ggroup'     : f'wedding-ministries{ecc}',
            'notify'     : f'director-worship{ecc},wedding-assistant-chair{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Weekday Mass Email' ],
            'ggroup'     : f'WeekdayMass{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'Worship Administration' ],
            'ggroup'     : f'worship-administration{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'YouthMin parent: Jr high' ],
            'ggroup'     : f'youth-ministry-parents-jr-high{ecc}',
            'notify'     : f'pastoral-associate-youth{ecc},ps-google-sync{ecc}',
        },
        {
            'workgroups' : [ 'YouthMin parent: Sr high' ],
            'ggroup'     : f'youth-ministry-parents-sr-high{ecc}',
            'notify'     : f'pastoral-associate-youth{ecc},ps-google-sync{ecc}',
        },

        #############################

        {
            'functions'  : [ { 'func' : find_ministry_chairs,
                               'purpose' : "Find ministry chairs" }, ],
            'ggroup'     : f'ministry-chairs{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },

        #----------------------------

        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "103"},
                               'purpose' : "Worship ministry chair" }, ],
            'ggroup'     : f'worship-chair{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "110"},
                               'purpose' : "Ten percent ministry chair" }, ],
            'ggroup'     : f'ten-percent-chair{ecc}',
            'notify'     : f'pastoral-associate-social-resp{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "612"},
                               'purpose' : "Community Life chair" }, ],
            'ggroup'     : f'community-life-chair{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "104-Stewardship"},
                               'purpose' : "Stewardship ministry chair" }, ],
            'ggroup'     : f'stewardship-chair{ecc}',
            'notify'     : f'director-parish-engagement{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "201"},
                               'purpose' : "Collection counter ministry chair" }, ],
            'ggroup'     : f'collection-counters-chair{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "207"},
                               'purpose' : "Technology ministry chair" }, ],
            'ggroup'     : f'technology-chair{ecc}',
            'notify'     : f'business-manager{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "300"},
                               'purpose' : "Worship/art&environment ministry chair" }, ],
            'ggroup'     : f'worship-art-and-environment-chair{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "307"},
                               'purpose' : "Wedding assistant ministry chair" }, ],
            'ggroup'     : f'wedding-assistant-chair{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "309"},
                               'purpose' : "Worship/acolytes ministry chair" }, ],
            'ggroup'     : f'worship-acolytes-chair{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "313"},
                               'purpose' : "Worship/communion ministers ministry chair" }, ],
            'ggroup'     : f'worship-communion-ministers-chair{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "316"},
                               'purpose' : "Worship/greeters ministry chair" }, ],
            'ggroup'     : f'worship-greeters-chair{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "318"},
                               'purpose' : "Worship/lectors ministry chair" }, ],
            'ggroup'     : f'worship-lectors-chair{ecc}',
            'notify'     : f'director-worship{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "401-Epiphany Companions"},
                               'purpose' : "Epiphany Companions ministry chair" }, ],
            'ggroup'     : f'companions-chair{ecc}',
            'notify'     : f'director-parish-engagement{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "402"},
                               'purpose' : "New members coffee chair" }, ],
            'ggroup'     : f'new-members-coffee-chair{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "409"},
                               'purpose' : "Sunday morning coffee chair" }, ],
            'ggroup'     : f'sunday-morning-coffee-chair{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "501"},
                               'purpose' : "Care for the Sick: Eucharist ministry chair" }, ],
            'ggroup'     : f'care-for-the-sick-chair{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : "505"},
                               'purpose' : "Chair: Healing Blankets" }, ],
            'ggroup'     : f'healing-blankets-chair{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : '600' },
                               'purpose' : "MOE ministry chair" }, ],
            'ggroup'     : f'moe-chair{ecc}',
            'notify'     : f'pastoral-associate-parish-life{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : '602-Singles Explore Life (SEL)' },
                               'purpose' : "SEL ministry chair" }, ],
            'ggroup'     : f'sel-chair{ecc}',
            'notify'     : f'ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : '901' },
                               'purpose' : "Youth Ministry Adult Volunteers" }, ],
            'ggroup'     : f'youth-ministry-adult-volunteers-chair{ecc}',
            'notify'     : f'youth-minister{ecc},ps-google-sync{ecc}',
        },
        {
            'functions'  : [ { 'func' : find_ministry_chair,
                               'kwargs' : { "ministry_prefix" : '903' },
                               'purpose' : "Confirmation Core Team Chair" }, ],
            'ggroup'     : f'confirmation-core-chair{ecc}',
            'notify'     : f'youth-minister{ecc},ps-google-sync{ecc}',
        },
    ]

    return synchronizations

####################################################################
#
# Sync functions
#
####################################################################

def compute_sync(sync, ps_members, group_members, log=None):
    def _normalized(email):
        # We could do a DNS MX lookup to see if a given domain is a Google
        # mail domain.  However, that does not seem worth it (and would
        # likely generate a bazillion spurious DNS MX lookups, because we
        # invoke this comparison a *LOT*).  So just use a hard-coded list of
        # common-enough Google mail domains.
        google_mail_domains = ['gmail.com', 'epiphanycatholicchurch.org', 'stalbert.org']

        parts = email.split('@')
        if parts[1] not in google_mail_domains:
            return email

        if '+' in parts[0]:
            plus_parts = parts[0].split('+')
            parts[0] = plus_parts[0]

        if '.' in parts[0]:
            parts[0] = parts[0].replace('.', '')

        return f"{parts[0]}@{parts[1]}"

    #--------------------------------------------------------------------

    # Google is a bit whacky with email addresses.  It does the following
    # two things when processing email addresses:
    #
    # - If there's a "." on the left hand side of the email address, ignore it
    # - If there's a "+BLAH" suffix on the left hand side, ignore it
    #
    # Meaning that all of the following email addresses resolve to the
    # same Google account:
    #
    # - foobar@gmail.com
    # - foo.bar@gmail.com
    # - f.o.o.b.a.r@gmail.com
    # - foobar+hello@gmail.com
    # - foo.bar+whazzup@gmail.com
    #
    # Meaning we can send any of the above email addresses to Google
    # and Google will resolve it all down to the same Google account.
    #
    # HOWEVER: When we ask for the membership of a Google Group, Google
    # may return any form of the email address (e.g., it may contain a "."
    # or a "+BLAH" suffix on the LHS).  It's not clear to me what the
    # rules are here -- perhaps the Google user sets a preference
    # somewhere for how they want Google to display their email address...?
    #
    # Meaning: we can't just normailze the above email addresses (in PS) to
    # foobar@gmail.com and assume that Gmail will always return
    # foobar@gmail.com to us as a member of a Google Group.  Instead, if
    # we see a Google mail domain, we might need to normalize the email
    # addresses and *then* compares to see if any given PS email address
    # is a member of a Google Group.
    def _compare_email(a, b):
        if a == b:
            return True

        # If one or the other email address is invalid, they're not equal
        if '@' not in a or '@' not in b:
            return False

        # Check to see if the normalized forms are equal
        return _normalized(a) == _normalized(b)

    #--------------------------------------------------------------------

    actions = list()

    for pm in ps_members:
        found_in_google_group = False
        for gm in group_members:
            if _compare_email(pm['email'], gm['email']):
                found_in_google_group = True
                gm['sync_found'] = True

                if pm['leader'] and gm['role'] != 'owner':
                    # In this case, the PS Member is in the group,
                    # but they need to be changed to a Google Group
                    # OWNER.
                    actions.append({
                        'action'              : 'change role',
                        'email'               : pm['email'],
                        'role'                : 'OWNER',
                        'ps_ministry_member' : pm,
                    })

                elif not pm['leader'] and gm['role'] == 'owner':
                    # In this case, the PS Member is in the group,
                    # but they need to be changed to a Google Group
                    # MEMBER.
                    actions.append({
                        'action'              : 'change role',
                        'email'               : pm['email'],
                        'role'                : 'MEMBER',
                        'ps_ministry_member' : pm,
                    })

        if not found_in_google_group:
            # In this case, we have an email address that needs to be
            # added to the Google Group.
            role = 'MEMBER'
            if pm['leader']:
                role = 'OWNER'

            actions.append({
                'action'              : 'add',
                'email'               : pm['email'],
                'role'                : role,
                'ps_ministry_member' : pm,
            })

    # Now go through all the group members and see who wasn't
    # 'sync_found' (above).  These are the emails we need to delete
    # from the Google Group.
    for gm in group_members:
        if 'sync_found' in gm and gm['sync_found']:
            continue

        actions.append({
            'action'              : 'delete',
            'email'               : gm['email'],
            'id'                  : gm['id'],
            'role'                : None,
            'ps_ministry_member' : None,
        })

    if len(actions) > 0:
        log.info(f'Actions for {sync["ggroup"]}')
        log.info(pformat(actions, depth=3))

    return actions

#-------------------------------------------------------------------

def do_sync(args, sync, group_permissions, service, actions, log=None):
    ministries = sync['ministries'] if 'ministries' in sync else 'None'
    workgroups = sync['workgroups'] if 'workgroups' in sync else 'None'

    type_str   = 'Broadcast' if group_permissions == BROADCAST else 'Discussion'

    log.info(f"Synchronizing ministries: {ministries}, workgroups: {workgroups}, group: {sync['ggroup']}, type {type_str}")

    # Process each of the actions
    changes     = list()
    for action in actions:
        a = action['action']
        r = action['role']

        # Remember: the ps_ministry_member contains an array of PS
        # members (because there may be more than one PS Member that
        # shares the same email address).
        mem_names = None
        key = 'ps_ministry_member'
        if key in action and action[key]:
            for mem in action[key]['ps_members']:
                if mem_names is None:
                    mem_names = mem['py friendly name FL']
                else:
                    mem_names += f', {mem["py friendly name FL"]}'

        log.debug("Processing action: {action} / {email} / {role}".
                  format(action=action['action'],
                         email=action['email'],
                         role=action['role']))
        # JMS This outputs PS Members (and their families!) -- very
        # lengthy output.
        #log.debug("Processing full action: {action}".
        #          format(action=pformat(action)))

        msg = None
        if a == 'change role':
            if r == 'OWNER':
                msg = _sync_member_to_owner(args, sync, group_permissions,
                                            service, action, mem_names, log)
            elif r == 'MEMBER':
                msg = _sync_owner_to_member(args, sync, group_permissions,
                                            service, action, mem_names, log)
            else:
                log.error(f"Action: change role, unknown role: {r} -- PS Member {mem_names} (skipped)")
                continue

        elif a == 'add':
            msg = _sync_add(args, sync, group_permissions,
                            service=service, action=action,
                            name=mem_names, log=log)

        elif a == 'delete':
            msg = _sync_delete(args, sync, service, action, mem_names, log)

        else:
            log.error(f"Unknown action: {a} -- PS Member {mem_names} (skipped)")

        # Don't send email if --dry-run
        if msg and not args.dry_run:
            email = action['email']
            i     = len(changes) + 1
            changes.append(f"<tr>\n<td>{i}.</td>\n<td>{mem_names}</td>\n<td>{action['email']}</td>\n<td>{msg}</td>\n</tr>")

    # If we have changes to report, email them
    # NOTE: len(changes) will == 0 if args.dry_run, but we check for
    # it any way (defensive programming!).
    if len(changes) > 0 and not args.dry_run:
        subject = 'Update to Google Group for '

        subject_add = list()
        rationale   = list()
        if 'ministries' in sync:
            for m in sync['ministries']:
                rationale.append(f'<li> Members in the "{m}" ministry</li>')
                subject_add.append(m)

        if 'workgroups' in sync:
            for k in sync['workgroups']:
                rationale.append(f'<li> Members with the "{k}" keyword</li>')
                subject_add.append(k)

        if 'functions' in sync:
            for f in sync['functions']:
                rationale.append(f'<li> Members that satisfied the "{f["purpose"]}" function</li>')
                subject_add.append(f['purpose'])

        # Assemble the final subject line
        subject = subject + ', '.join(subject_add)

        # Assemble the final email body
        style = r'''table { border-collapse: collapse; }
th, td {
    text-align: left;
    padding: 8px;
    border-bottom: 1px solid #ddd;
}
tr:nth-child(even) { background-color: #f2f2f2; }'''

        changes = '\n'.join(changes)
        rationale = '\n'.join(rationale)
        body = f"""<html>
<head>
<style>
{style}
</style>
</head>
<body>
<p>The following changes were made to the {type_str} Google Group {sync['ggroup']}:</p>

<p><table border=0>
<tr>
<th>&nbsp;</th>
<th>Name</th>
<th>Email address</th>
<th>Action</th>
</tr>
{changes}
</table></p>

<p>These email addresses were obtained from PS:</p>

<p><ol>
{rationale}
</ol></p>
</body>
</html>
"""

        # Send the email
        ECC.send_email(to_addr=sync['notify'], subject=subject, body=body,
                  content_type='text/html', log=log)

#-------------------------------------------------------------------

@retry.Retry(predicate=Google.retry_errors)
def _sync_member_to_owner(args, sync, group_permissions, service, action, name, log=None):
    email = action['email']
    if log:
        log.info(f"Changing PS Member {name} ({email}) from Google Group Member to Owner")

    # Per
    # https://stackoverflow.com/questions/31552146/group-as-owner-or-manager-fails-with-400-error,
    # we can't set a Group as an OWNER or MANAGER of another Group
    # (e.g., director-worship@ecc.org can't be the owner of one of the
    # ministry groups).  As of Aug 2018, you can still do it in the
    # Google Web dashboard (i.e., remove the Group, then re-add the
    # Group as an OWNER), but you can't do it via the API.  Apparently
    # this is Google's intended behavior -- the fact that it works on
    # the Google Web dashboard is a fluke.  :-( So we just have to
    # plan on not being able to set Groups to be OWNER or MANAGER of
    # another Group.  Sigh.

    group_entry = {
        'email' : email,
        'role'  : 'OWNER',
    }
    if not args.dry_run:
        service.members().update(groupKey=sync['ggroup'],
                                 memberKey=email,
                                 body=group_entry).execute()

    if group_permissions == BROADCAST:
        msg = "Change to: owner (can post to this group)"
    else:
        msg = "Change to: owner"

    return msg

@retry.Retry(predicate=Google.retry_errors)
def _sync_owner_to_member(args, sync, group_permissions, service, action, name, log=None):
    email = action['email']
    if log:
        log.info(f"Changing PS Member {name} ({email}) from Google Group Owner to Member")

    group_entry = {
        'email' : email,
        'role'  : 'MEMBER',
    }
    if not args.dry_run:
        service.members().update(groupKey=sync['ggroup'],
                                 memberKey=email,
                                 body=group_entry).execute()

    if group_permissions == BROADCAST:
        msg = "Change to: member (can <strong><em>not</em></strong> post to this group)"
    else:
        msg = "Change to: member"

    return msg

@retry.Retry(predicate=Google.retry_errors)
def _sync_add(args, sync, group_permissions, service, action, name, log=None):
    email = action['email']
    role  = action['role']
    if log:
        log.info(f"Adding PS Member {name} ({email}) as Google Group {role.lower()}")

    group_entry = {
        'email' : email,
        'role'  : role,
    }
    try:
        if not args.dry_run:
            service.members().insert(groupKey=sync['ggroup'],
                                     body=group_entry).execute()

        if group_permissions == BROADCAST:
            if role == 'OWNER':
                msg = "Added to group (can post to this group)"
            else:
                msg = "Added to group (can <strong><em>not</em></strong> post to this group)"
        else:
            msg = "Added to group"

    except googleapiclient.errors.HttpError as e:
        # NOTE: If we failed because this is a duplicate, then don't
        # worry about it.
        log.warning(f"FAILED to add this member -- Google error: {e}")

        j = json.loads(e.content)
        for err in j['error']['errors']:
            if err['reason'] == 'duplicate':
                # This is not worth trying again.
                if log:
                    log.warning(f"Google says a duplicate of {email} "
                              "already in the group -- ignoring")
                return None

            elif 'Resource Not Found' in err['reason']:
                # If this is an invalid Gmail address (i.e., Google
                # says this email address does not exist), then just
                # log the error and keep going.
                log.warning(f"Google says {email} "
                            "is not a valid Gmail address -- ignoring")
                msg = f'NOT added: {email} is not a valid Gmail address'
                break

            # Re-raise the error and let retry.Retry() determine if we should
            # try again.
            raise e

    except Exception as e:
        # When errors occur, we do want to log them.  But we'll re-raise them to
        # let an upper-level error handler handle them (e.g., retry.Retry() may
        # actually re-invoke this function if it was a retry-able Google API
        # error).
        all = sys.exc_info()
        msg = ("FAILED to add this member -- unknown Google error! "
               f"({all[0]} / {all[1]} / {all[2]})")
        log.error(msg)
        raise e

    return msg

@retry.Retry(predicate=Google.retry_errors)
def _sync_delete(args, sync, service, action, name, log=None):
    email = action['email']

    # We delete by ID (instead of by email address) because of a weird
    # corner case:
    #
    # - foo@example.com (a non-gmail address) is in a google group,
    #   but has no Google account
    # - later, foo@example.com visits
    #   https://accounts.google.com/SignupWithoutGmail and gets a
    #   Google account associated with that email address
    #
    # In this case, Google seems to be somewhat confused:
    # foo@example.com is still associated with the Group, but it's the
    # non-Google-account foo@example.com.  But if we attempt to move
    # that email address, it'll try to remove the Google-account
    # foo@example.com (and therefore fail).
    #
    # So we remove by ID, and that unambiguously removes the correct
    # member from the Group.
    id    = action['id']
    if log:
        log.info(f"Deleting PS Member {name} ({email}) from group {sync['ggroup']}")

    if not args.dry_run:
        service.members().delete(groupKey=sync['ggroup'],
                                 memberKey=id).execute()

    msg = "Removed from the group"
    return msg

####################################################################
#
# Google queries
#
####################################################################

@retry.Retry(predicate=Google.retry_errors)
def google_group_get_permissions(service, group_email, log=None):
    response = (service
                .groups()
                .get(groupUniqueId=group_email,
                     fields='whoCanPostMessage')
                .execute())

    who = response.get('whoCanPostMessage')
    if log:
        log.debug(f"Group permissions for {group_email}: {who}")

    if (who == 'ANYONE_CAN_POST' or who == 'ALL_MEMBERS_CAN_POST' or
        who == 'ALL_IN_DOMAIN_CAN_POST'):
        return DISCUSSION
    else:
        return BROADCAST

#-------------------------------------------------------------------

@retry.Retry(predicate=Google.retry_errors)
def google_group_find_members(service, sync, log=None):
    group_members = list()

    log.debug(f"Looking up Google Group members of {sync}")

    # Iterate over all (pages of) group members
    page_token = None
    while True:
        response = (service
                    .members()
                    .list(pageToken=page_token,
                          groupKey=sync['ggroup'],
                          fields='nextPageToken,members(email,role,id)').execute())
        for group in response.get('members', []):
            group_members.append({
                'email' : group['email'].lower(),
                'role'  : group['role'].lower(),
                'id'    : group['id'].lower(),
            })

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    if log:
        log.debug(f"Google Group membership for {sync['ggroup']}")
        log.debug(pformat(group_members))

    return group_members

####################################################################
#
# PS queries
#
####################################################################

def _is_ministry_leader(ministry):
    if ministry['role'] == 'Chairperson' or \
       ministry['role'] == 'Staff':
        return True

    return False

# Returns two values:
# Boolean: if the Member is in any of the ministry names provided
#          --> I.e., if the Member is in the ministry
# Boolean: if the Member is Chairperson in any of the ministry names provided
#          --> I.e., if the Member should be able to post to the Google Group
def _member_in_any_ministry(member, ministries):
    if 'py ministries' not in member:
        return False, False

    found = False
    leader_of_any = False
    for member_ministry in member['py ministries'].values():
        member_ministry_name = member_ministry['name']
        if member_ministry_name in ministries:
            found = True
            if _is_ministry_leader(member_ministry):
                leader_of_any = True
    if found:
        return found, leader_of_any

    # Didn't find the Member in any of the ministries
    return False, False

# Returns two values:
# Boolean: if the member is in a Member WorkGroup named "NAME" or
# "NAME Ldr" from those provided
#          --> I.e., if the Member has the base keyword
# Boolean: if the member has Member WorkGroup "NAME Ldr" or "NAME
# Leader" from those provided
#          --> I.e., if the Member should be able to post to the Google Group
def _member_in_any_workgroup(member, workgroups):
    if 'py workgroups' not in member:
        return False, False

    found_any = False
    poster_of_any = False
    for name in workgroups:
        # member['py workgroups'] is a dictionary of
        # WORKGROUP_NAME:{more data} items.
        if name in member['py workgroups']:
            found_any = True
        if f'{name} Ldr' in member['py workgroups'] or \
           f'{name} Leader' in member['py workgroups']:
            found_any = True
            poster_of_any = True

    return found_any, poster_of_any

# Returns two values:
# Boolean (member): if the Member is a chair of any ministry
# Boolean (leader): False
def find_ministry_chairs(member, **kwargs):
    if 'py ministries' not in member:
        return False, False

    for ministry in member['py ministries'].values():
        if _is_ministry_leader( ministry):
            return True, False

    return False, False

# Returns two values:
# Boolean (member): if the Member is the chair of the target committee
# Boolean (leader): same as the first value
def find_ministry_chair(member, **kwargs):
    if 'py ministries' not in member:
        return False, False

    key = 'ministry_prefix'
    if key not in kwargs:
        return False, False
    ministry_prefix = kwargs[key]

    for ministry in member['py ministries'].values():
        if _is_ministry_leader(ministry) and \
           ministry['name'].startswith(ministry_prefix):
            return True, True

    return False, False

# Find a list of Members that match the criteria of the sync group
# we're looking for.
def find_matching_members(members, sync, log=None):
    ministry_members = list()
    ministries       = list()
    workgroups         = list()
    found_emails     = dict()
    functions        = list()

    # Make the sync ministries be an array
    if 'ministries' in sync:
        if type(sync['ministries']) is list:
            ministries = sync['ministries']
        else:
            ministries = [ sync['ministries'] ]

    # Make the sync workgroups be a group
    if 'workgroups' in sync:
        if type(sync['workgroups']) is list:
            workgroups = sync['workgroups']
        else:
            workgroups = [ sync['workgroups'] ]

    if 'functions' in sync:
        functions = sync['functions']

    # Walk all members looking for those in any of the ministries or
    # those that have any of the workgroups.
    for ps_member in members.values():
        # Check if the member is in any of the ministries
        member, leader = _member_in_any_ministry(ps_member, ministries)

        # Check if the member has any of the workgroups
        member_temp, leader_temp = _member_in_any_workgroup(ps_member, workgroups)
        if member_temp:
            member = True
        if leader_temp:
            leader = True

        # Check if the member satisfies any of the other functions
        key = 'kwargs'
        for func in functions:
            kwargs = {}
            if key in func:
                kwargs = func[key]
            member_temp, leader_temp = func['func'](ps_member, **kwargs)
            if member_temp:
                member = True
            if leader_temp:
                leader = True

        if leader:
            member = True

        if not member:
            continue

        # This Member should be in this Google Group.  Yay!
        # But if they don't have an email address, skip them.
        e = ps_member['emailAddress']
        if e is None:
            continue

        e = e.lower()
        new_entry = {
            'ps_members' : [ ps_member ],
            'email'      : e,
            'leader'     : leader,
        }

        # Here's a kicker: some PS Members share an email address.
        # This means we might find multiple Members with the same
        # email address who are in the same ministry.  ...and they
        # might have different permissions (one may be a poster
        # and one may not)!  Since Google Groups will treat these
        # multiple Members as a single email address, we just have
        # to take the most permissive Member's permission for the
        # shared email address.

        if e in found_emails:
            index = found_emails[e]
            leader = leader or ministry_members[index]['leader']
            ministry_members[index]['leader'] = leader
            ministry_members[index]['ps_members'].append(ps_member)
        else:
            ministry_members.append(new_entry)
            found_emails[e] = len(ministry_members) - 1

    if log:
        log.debug(f"PS members for ministries {ministries} and workgroups {workgroups} and functions {functions}:")
        for m in ministry_members:
            name_str = ''
            for pm in m['ps_members']:
                if len(name_str) > 0:
                    name_str = name_str + ' or '
                name_str = name_str + pm['py friendly name FL']

            log.debug(f'  {name_str} <{m["email"]}> leader: {m["leader"]}')

    return ministry_members

####################################################################
#
# Setup functions
#
####################################################################

def setup_cli_args():
    tools.argparser.add_argument('--smtp-auth-file',
                                 required=True,
                                 help='File containing SMTP AUTH username:password')
    tools.argparser.add_argument('--slack-token-filename',
                                 help='File containing the Slack bot authorization token')

    tools.argparser.add_argument('--ps-api-keyfile',
                                 required=True,
                                 help='File containing the ParishSoft API key')
    tools.argparser.add_argument('--ps-cache-dir',
                                 default='.',
                                 help='Directory to cache the ParishSoft data')

    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

    tools.argparser.add_argument('--dry-run',
                                 action='store_true',
                                 help='Do not actually update the Google Group; just show what would have been done')

    global verbose
    tools.argparser.add_argument('--verbose',
                                 action='store_true',
                                 default=verbose,
                                 help='If enabled, emit extra status messages during run')
    global debug
    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 default=debug,
                                 help='If enabled, emit even more extra status messages during run')
    global logfile
    tools.argparser.add_argument('--logfile',
                                 default=logfile,
                                 help='Store verbose/debug logging to the specified file')

    global args
    args = tools.argparser.parse_args()

    # --dry-run implies --verbose
    if args.dry_run:
        args.verbose = True

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True

    # Read the PS API key
    if not os.path.exists(args.ps_api_keyfile):
        print(f"ERROR: ParishSoft API keyfile does not exist: {args.ps_api_keyfile}")
        exit(1)
    with open(args.ps_api_keyfile) as fp:
        args.api_key = fp.read().strip()

    return args

####################################################################
#
# Main
#
####################################################################

def main():
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate=True,
                            slack_token_filename=args.slack_token_filename)
    ECC.setup_email(args.smtp_auth_file, smtp_debug=args.debug, log=log)

    log.info("Loading ParishSoft info...")
    families, members, family_workgroups, member_worksgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             active_only=True,
                                             parishioners_only=False,
                                             cache_dir=args.ps_cache_dir,
                                             log=log)

    apis = {
        'admin' : { 'scope'       : Google.scopes['admin'],
                    'api_name'    : 'admin',
                    'api_version' : 'directory_v1', },
        'group' : { 'scope'       : Google.scopes['group'],
                    'api_name'    : 'groupssettings',
                    'api_version' : 'v1', },
    }
    services = GoogleAuth.service_oauth_login(apis,
                                              app_json=args.app_id,
                                              user_json=args.user_credentials,
                                              log=log)
    service_admin = services['admin']
    service_group = services['group']

    synchronizations = get_synchronizations()
    for sync in synchronizations:
        group_permissions = google_group_get_permissions(service_group,
                                                         sync['ggroup'],
                                                         log)
        matching_members = find_matching_members(members,
                                                 sync, log=log)
        group_members = google_group_find_members(service_admin, sync, log=log)

        actions = compute_sync(sync,
                               matching_members,
                               group_members, log=log)

        do_sync(args, sync, group_permissions, service_admin, actions, log=log)

    # All done
    log.info("Synchronization complete")

if __name__ == '__main__':
    main()
