#!/usr/bin/env python3

import os
import sys
import csv
import copy
import datetime

# Load the ECC python modules.  There will be a sym link off this directory.
moddir = os.path.join(os.path.dirname(sys.argv[0]), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import PDSChurch

pledge_minimum = 0

##############################################################################

def find_family_funding(year, family):
    data = {
        'year'    : year,
        'fid'     : family['FamRecNum'],
        'found'   : False,
        'pledged' : 0,
        'q1'      : 0,
        'q2'      : 0,
        'q3'      : 0,
        'q4'      : 0,
        'total'   : 0,
    }

    key      = 'funds'
    pds_year = f"{year-2000:02d}"
    if key not in family or pds_year not in family[key]:
        return data

    funds = family[key][pds_year]
    for fund in funds.keys():
        # Only look at fund 1, which is general stewardship
        if fund != "1":
            continue

        fund_rate = funds[fund]['fund_rate']
        if fund_rate and fund_rate['FDTotal']:
            data['pledged'] += int(fund_rate['FDTotal'])
            data['found'] = True

        for item in funds[fund]['history']:
            amount = item['item']['FEAmt']
            if amount is None:
                # Yes, this happens.  Sigh.
                continue

            quarter = int((item['item']['FEDate'].month-1) / 3) + 1
            data[f'q{quarter}'] += amount
            data['total'] += amount
            data['found'] = True

    return data

##############################################################################

today = datetime.date.today()

def is_active(family, funding, year):
    if today.year == year:
        if not family['Inactive']:
            return True

    if funding['found'] and funding['total'] > 0:
        return True

    # I guess this Family isn't active!
    return False

def submitted_stewardship(family, funding, year):
    key = 'keywords'
    if key in family:
        keyword = f'Active: Stewardship {year}'
        if keyword in family[key]:
            return True

    # We do not have keywords before 2020, so look at pledge data.
    # Also, it's possible a Family missed the keyword but has a pledge.
    if funding['pledged'] > 0:
        return True

    return False

def submitted_census(family, year):
    key = 'keywords'
    if key in family:
        keyword = f'Active: Census {year}'
        if keyword in family[key]:
            return True

    return False

def has_year_keyword(family, year):
    key = 'keywords'
    if key in family:
        str_year = str(year)
        for keyword in family[key]:
            if str_year in keyword:
                return True

    return False

##############################################################################

def is_parishioner(family):
    key = 'Visitor'
    if key in family:
        return not bool(family[key])

    return False

##############################################################################

def analyze(start, end, families, members, log):
    fids      = families.keys()
    fid_dicts = { fid  : dict() for fid in fids }
    results   = { year : copy.deepcopy(fid_dicts) for year in range(start, end+1) }

    for year in range(start, end+1):
        print(f"Computing for year: {year}")
        for family in families.values():
            fid         = family['FamRecNum']
            parishioner = is_parishioner(family)
            funding     = find_family_funding(year, family)
            census      = submitted_census(family, year)
            stewardship = submitted_stewardship(family, funding, year)
            active      = (funding['total'] > 0 or funding['pledged'] > pledge_minimum or
                            census or stewardship or has_year_keyword(family, year))

            results[year][fid] = {
                'year'          : year,
                'fid'           : fid,
                'family'        : family,
                'census'        : census,
                'stewardship'   : stewardship,

                'parishioner'   : parishioner,
                'active'        : active,
                'funding'       : funding,

                'active_added'  : False,
                'active_lost'   : False,

                'giver_added'   : False,
                'giver_lost'    : False,
            }

            if year - 1 in results:
                active_last = results[year-1][fid]['active']
                if active_last and not active:
                    results[year][fid]['active_lost'] = True
                elif not active_last and active:
                    results[year][fid]['active_added'] = True

                giver_last = results[year-1][fid]['funding']['total'] > 0
                giver_this = results[year  ][fid]['funding']['total'] > 0
                if giver_last and not giver_this:
                    results[year][fid]['giver_lost'] = True
                elif not giver_last and giver_this:
                    results[year][fid]['giver_added'] = True

    return results

##############################################################################

def show_family_stats(results):
    for year in sorted(results):
        year_data = results[year]

        # Do some counting
        active                  = 0
        parishioners            = 0
        census                  = 0
        stewardship             = 0
        pledgers                = 0
        givers                  = 0
        givers_q1               = 0
        givers_q2               = 0
        givers_q3               = 0
        givers_q4               = 0

        givers_parishioners     = 0
        givers_non_parishioners = 0

        census_only             = 0
        stewardship_only        = 0
        census_and_stewardship  = 0

        active_added            = 0
        active_lost             = 0
        giver_added             = 0
        giver_lost              = 0

        yes_stew_yes_pledge_yes_give = 0
        yes_stew_yes_pledge_no_give  = 0
        yes_stew_no_pledge_yes_give  = 0
        yes_stew_no_pledge_no_give   = 0
        no_stew_no_pledge_yes_give   = 0
        no_stew_no_pledge_no_give    = 0

        for fid, family_data in year_data.items():
            funding = family_data['funding']

            f_census = family_data['census']
            f_stew   = family_data['stewardship']
            f_pledge = funding['pledged'] > pledge_minimum
            f_gave   = funding['total'] > 0

            active       += int(family_data['active'])
            parishioners += int(family_data['parishioner'])
            census       += int(f_census)
            stewardship  += int(f_stew)
            pledgers     += int(f_pledge)
            givers       += int(f_gave)
            givers_q1    += int(funding['q1'] > 0)
            givers_q2    += int(funding['q2'] > 0)
            givers_q3    += int(funding['q3'] > 0)
            givers_q4    += int(funding['q4'] > 0)

            active_added += int(family_data['active_added'])
            active_lost  += int(family_data['active_lost'])

            giver_added  += int(family_data['giver_added'])
            giver_lost   += int(family_data['giver_lost'])

            yes_stew_yes_pledge_yes_give += int(f_stew and f_pledge and f_gave)
            yes_stew_yes_pledge_no_give  += int(f_stew and f_pledge and not f_gave)
            yes_stew_no_pledge_yes_give  += int(f_stew and not f_pledge and f_gave)
            yes_stew_no_pledge_no_give   += int(f_stew and not f_pledge and not f_gave)
            no_stew_no_pledge_yes_give   += int(not f_stew and not f_pledge and f_gave)
            no_stew_no_pledge_no_give    += int(not f_stew and not f_pledge and not f_gave)

            census_only                  += int(f_census and (not f_stew or not f_pledge))
            stewardship_only             += int(not f_census and (f_stew or f_pledge))
            census_and_stewardship       += int(f_census and (f_stew or f_pledge))

            givers_non_parishioners      += int(not family_data['parishioner'] and f_gave)

        print(f"For year {year}: ")
        print(f"  - Total Families: {len(year_data)}, Parishioners: {parishioners}")
        print(f"  - Active Families: {active} (added {active_added}, lost {active_lost})")
        print(f"  - Pledgers: {pledgers}")
        print(f"  - Givers: {givers_q1} q1, {givers_q2} q2, {givers_q3} q3, {givers_q4} q4, {givers} total ({givers_non_parishioners} were not parishioners) ({giver_added} added, {giver_lost} lost)")
        print(f"  - stew+pledge+give {yes_stew_yes_pledge_yes_give}, stew+pledge+no give {yes_stew_yes_pledge_no_give}, stew+no pledge+give {yes_stew_no_pledge_yes_give}, stew+no pledge+no give {yes_stew_no_pledge_no_give}, no stew+give {no_stew_no_pledge_yes_give}, no stew+no give {no_stew_no_pledge_no_give}")
        print(f"  - returned just census {census_only}, returned stewardship only {stewardship_only}, returned census+stewardship {census_and_stewardship}")

        check_stew   = yes_stew_yes_pledge_no_give + yes_stew_yes_pledge_yes_give + yes_stew_no_pledge_no_give + yes_stew_no_pledge_yes_give
        check_census = stewardship_only + census_and_stewardship
        print(f"  - Check: {'GOOD' if check_stew == check_census else 'BAD'} (stew {check_stew}, census {check_census})")

##############################################################################

def show_money_stats(families, results):
    import numpy as np
    import matplotlib.pyplot as plt

    max_pledge_bins = None
    max_give_bins = None

    all_pledges = dict()
    all_gives = dict()

    # Do two things in this loop:
    # 1. Make lists of all pledges / give totals for the year
    # 2. Calculate the historgram of each, and find the set of bins with the largest max (we'll use that one set of bins with the largest max to histogram graph all the years)
    for year in sorted(results):
        year_data = results[year]

        pledge_total = 0
        give_total = 0

        below_pledge = 0
        met_pledge = 0
        above_pledge = 0

        pledges = list()
        gives = list()

        for fid, family_data in year_data.items():
            funding = family_data['funding']
            pledge  = funding['pledged']
            gave    = funding['total']

            pledge_total += pledge if pledge > pledge_minimum else 0
            give_total   += gave

            if pledge > pledge_minimum:
                pledges.append(pledge)

                tenp = pledge * 0.1
                if gave > pledge + tenp:
                    above_pledge += 1
                elif gave < pledge - tenp:
                    below_pledge += 1
                else:
                    met_pledge += 1

            if gave > 0:
                gives.append(gave)

        print(f"Year {year}: above pledge {above_pledge}, met pledge {met_pledge}, below pledge {below_pledge}")

        all_pledges[year] = pledges
        all_gives[year] = gives

        def _doit_numpy_hist(data, max_bins, show=False):
            data, bins = np.histogram(data)
            if max_bins is None:
                max_bins = bins
            elif max_bins[-1] < bins[-1]:
                max_bins = bins

            return max_bins

        max_pledge_bins = _doit_numpy_hist(pledges, max_pledge_bins)
        max_give_bins   = _doit_numpy_hist(gives, max_give_bins, True)

    def _doit_print(label, bins):
        ints = [ str(int(x)) for x in bins ]
        print(f"{label}: {', '.join(ints)}")

    _doit_print("Pledge bins", max_pledge_bins)
    _doit_print("Give bins  ", max_give_bins)

    # Find the max bin overall and use that
    if max_pledge_bins[-1] > max_give_bins[-1]:
        max_bins = max_pledge_bins
    else:
        max_bins = max_give_bins

    _doit_print("Using bins ", max_bins)

    # Once we have the final final finial bins, add up how much money we received for each bin in the historgram
    all_totals_per_bucket = dict()
    for year in sorted(results):
        year_data = results[year]

        # Initially zeros for all buckets
        total_per_bucket = [ 0 for val in max_bins ]
        count_per_bucket = [ 0 for val in max_bins ]

        for fid, family_data in year_data.items():
            total = family_data['funding']['total']

            # The lowest bucket may be 2, but the total may be 0
            if total <= max_bins[0]:
                total_per_bucket[0] += total
                count_per_bucket[0] += 1
                continue

            found = False
            for i in range(len(max_bins) - 1):
                if total > max_bins[i] and total <= max_bins[i+1]:
                    total_per_bucket[i] += total
                    count_per_bucket[i] += 1
                    found = True
                    break

            assert(found == True)

        # Can't do the single-line way because some count_per_bucket[i] values will be 0.
        average_per_bucket = list()
        for i in range(len(total_per_bucket)):
            value = 0
            if count_per_bucket[i] > 0:
                # Round to an int, because we're talking dollars here --
                # it's good enough to round.
                value = int(total_per_bucket[i] / count_per_bucket[i])
            average_per_bucket.append(value)

        all_totals_per_bucket[year] = total_per_bucket
        print(f"Year: {year}: totals per bucket:   {total_per_bucket}")
        print(f"Year: {year}: averages per bucket: {average_per_bucket}")

    # Now that we have the set of bins with the largest max, histogram graph each year
    for year in sorted(all_pledges):
        def _doit_save_pdf(label, year, data, bins):
            plt.clf()
            fig, ax = plt.subplots(1, 1)
            _ = ax.hist(data, bins=bins)
            rects = ax.patches
            data = list()
            for rect in rects:
                height = rect.get_height()
                data.append(int(height))
                ax.text(rect.get_x() + rect.get_width() / 2, height+0.01, f"{int(height)}",
                        ha='center', va='bottom')

            print(f"{label} Histogram heights: {data}")
            plt.title(f"{label} for {year}")

            filename = f"{label}-for-{year}.png"
            plt.savefig(filename)
            print(f"Wrote {filename}")

        _doit_save_pdf("Pledges", year, all_pledges[year], max_bins)
        _doit_save_pdf("Gives", year, all_gives[year], max_bins)

##############################################################################

def main():
    log = ECC.setup_logging(debug=False)

    (pds, families,
     members) = PDSChurch.load_families_and_members(filename='pdschurch.sqlite3',
                                                    active_only=False,
                                                    parishioners_only=False,
                                                    log=log)

    print(f"Loaded {len(members)} total Members")
    print(f"Loaded {len(families)} total Families")

    squyres = 119353
    for year in range(2015, 2020+1):
        data = find_family_funding(year, families[squyres])
        print(f"Squyres {year}: {data}")

    results = analyze(start=2015, end=2021,
        families=families, members=members, log=log)

    show_family_stats(results)
    show_money_stats(families, results)

main()
