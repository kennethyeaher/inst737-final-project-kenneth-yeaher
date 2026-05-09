"""
Single source of truth for FIPS to state mappings.

Several pipeline stages need to translate between two digit FIPS codes
(used by Census products) and two letter state abbreviations
(used in NPPES and downstream model outputs). Keeping the mapping in
one file means a state code change only has to be fixed once.
"""

from __future__ import annotations

# two digit FIPS code to USPS state abbreviation
# covers the 50 states plus DC (matches the universe of states the project analyzes)
FIPS_TO_STATE: dict[str, str] = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}

# reverse lookup for the same set, useful when joining model output back to FIPS
STATE_TO_FIPS: dict[str, str] = {abbr: fips for fips, abbr in FIPS_TO_STATE.items()}
