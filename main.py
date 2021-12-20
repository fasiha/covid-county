import pandas as pd

county_to_party = dict()

pres = pd.read_csv('countypres_2000-2020.csv')
latest = pres.loc[pres.year == 2020]
for fips, bycounty in latest.groupby(by='county_fips'):
  total = bycounty['totalvotes'].iloc[0]  # repeated for all parties and modes
  byparty = bycounty.groupby('party')['candidatevotes'].sum()
  dem = byparty.DEMOCRAT / total
  county_to_party[fips] = dem

covid = pd.concat([
    pd.read_csv('covid-19-data/rolling-averages/us-counties-2020.csv'),
    pd.read_csv('covid-19-data/rolling-averages/us-counties-2021.csv')
])

geoid_to_deaths = covid.groupby(['geoid'])['deaths'].sum()
geoid_to_deaths.index = [float(x.split('-')[1]) for x in geoid_to_deaths.index]


def bin_names(edges=(0.2, 0.4, 0.5, 0.6, 0.8)) -> list[str]:
  return [f'Dem <{"+" if x > 0.5 else "-"}{round(100*x)}%' for x in edges
         ] + [f'Dem >{"+" if x > 0.5 else "-"}{round(100*x)}%' for x in edges[-1:]]


def pct_to_bin(pct: float, edges=(0.2, 0.4, 0.5, 0.6, 0.8)):
  return sum(pct > x for x in edges)


bins = bin_names()
partydf = pd.DataFrame.from_dict(county_to_party, orient='index', columns=['dem'])
partydf['bin'] = [bins[pct_to_bin(x)] for x in partydf.dem]
partydf['deaths'] = [
    geoid_to_deaths.loc[fips] if fips in geoid_to_deaths else -1 for fips in county_to_party
]

print('area under curve\n', partydf.groupby('bin')['deaths'].sum())
"""
Dem <-20%     40141
Dem <-40%    211405
Dem <-50%    123572
Dem <+60%    194219
Dem <+80%    174997
Dem >+80%     17121
"""

MISSING_FIPS = list(filter(lambda fips: fips not in geoid_to_deaths, county_to_party))
print('MISSING', MISSING_FIPS)
"""
[2001.0,
 2002.0,
 2003.0,
 2004.0,
 2005.0,
 2006.0,
 2007.0,
 2008.0,
 2009.0,
 2010.0,
 2011.0,
 2012.0,
 2014.0,
 2015.0,
 2017.0,
 2018.0,
 2019.0,
 2021.0,
 2022.0,
 2023.0,
 2024.0,
 2025.0,
 2026.0,
 2027.0,
 2028.0,
 2029.0,
 2030.0,
 2031.0,
 2032.0,
 2033.0,
 2034.0,
 2035.0,
 2036.0,
 2037.0,
 2038.0,
 2039.0,
 2040.0,
 2099.0,
 36000.0,
 36005.0,
 36047.0,
 36061.0,
 36081.0,
 36085.0,
 46113.0]"""
