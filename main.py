import pandas as pd  # type: ignore
import numpy as np

county_to_party = dict()

pres = pd.read_csv('countypres_2000-2020.csv')
latest = pres.loc[pres.year == 2020]
for fips, bycounty in latest.groupby(by='county_fips'):
  total = bycounty['totalvotes'].iloc[0]  # repeated for all parties and modes
  byparty = bycounty.groupby('party')['candidatevotes'].sum()
  dem = byparty.DEMOCRAT / total
  county_to_party[fips] = dem

# To handle DC data missing for 2020, get party votes from 2016
DISTRICT_OF_COLUMBIA_FIPS = 11001
if DISTRICT_OF_COLUMBIA_FIPS not in county_to_party:
  dc = pres[np.logical_and(pres.year == 2016, pres.county_fips == 11001)]
  dem = dc.loc[dc.party == 'DEMOCRAT']
  county_to_party[DISTRICT_OF_COLUMBIA_FIPS] = float(dem.candidatevotes / dem.totalvotes)
# Also SAN JOAQUIN, CA (fips 06077) is missing total
SAN_JOAQUIN_CA_FIPS = 6077
if pd.isna(county_to_party[SAN_JOAQUIN_CA_FIPS]):
  g = latest[latest.county_fips == SAN_JOAQUIN_CA_FIPS]
  total = g.candidatevotes.sum()
  county_to_party[SAN_JOAQUIN_CA_FIPS] = float(g.loc[g.party == 'DEMOCRAT'].candidatevotes / total)
# All five counties in NYC are grouped together: see https://github.com/nytimes/covid-19-data/issues/105
NYT_FAKE_NYC_FIPS = 36998.0
if NYT_FAKE_NYC_FIPS not in county_to_party:
  dem = 0
  total = 0
  NYC_FIPS = [36005, 36047, 36061, 36081, 36085]
  for fips in NYC_FIPS:
    row = latest[np.logical_and(latest.county_fips == fips, latest.party == 'DEMOCRAT')]
    dem += float(row.candidatevotes.sum())
    total += float(row.totalvotes)
  county_to_party[NYT_FAKE_NYC_FIPS] = dem / total

## covid
covid = pd.concat([
    pd.read_csv('covid-19-data/rolling-averages/us-counties-2020.csv', parse_dates=['date']),
    pd.read_csv('covid-19-data/rolling-averages/us-counties-2021.csv', parse_dates=['date']),
    pd.read_csv('covid-19-data/rolling-averages/us-counties-2022.csv', parse_dates=['date']),
])

geoid_to_deaths = covid.groupby(['geoid'])['deaths'].sum().to_frame()
geoid_to_deaths['county'] = covid.groupby(['geoid'])['county'].max()
geoid_to_deaths['state'] = covid.groupby(['geoid'])['state'].max()
geoid_to_deaths.index = [float(x.split('-')[1]) for x in geoid_to_deaths.index]
geoid_to_deaths['dem'] = [
    county_to_party[fips] if fips in county_to_party else pd.NA for fips in geoid_to_deaths.index
]

MISSING_VOTE_DATA = geoid_to_deaths[np.logical_and(
    pd.isna(geoid_to_deaths.dem), geoid_to_deaths.deaths > 0)].sort_values('deaths')

print(MISSING_VOTE_DATA)


def bin_names(edges=(0.2, 0.4, 0.5, 0.6, 0.8)) -> list[str]:
  ret = []
  padded = (-1,) + edges + (-1,)
  for l, r in zip(padded, padded[1:]):
    if l < 0 or r < 0:
      if l < 0:
        # left edge
        ret.append(f'Rep {round(100*(1-r))}+%')
      else:
        ret.append(f'Dem {round(100*l)}+%')
    else:
      l = round(l * 100)
      r = round(r * 100)
      if l < 50:
        ret.append(f'Rep {100-r}–{100-l-1}%')
      else:
        ret.append(f'Dem {l}–{r-1}%')
    print(l, r, ret[-1])
  return ret


def pct_to_bin(pct: float, edges=(0.2, 0.4, 0.5, 0.6, 0.8)):
  return sum(pct > x for x in edges)


bins = bin_names()
geoid_to_deaths['bin'] = [
    bins[pct_to_bin(x)] if not pd.isna(x) else 'unknown' for x in geoid_to_deaths.dem
]

geoid_to_deaths.sort_values('deaths')

by_bin = geoid_to_deaths.groupby('bin')['deaths'].sum()
print(by_bin.sort_index(ascending=False).to_markdown())

by_party = geoid_to_deaths.dropna().groupby(
    lambda x: geoid_to_deaths.loc[x].dem > 0.5)['deaths'].sum()
print(by_party)
print("true: Dem, false: Rep")


## plot
# preparation
def fix_fips(s: str):
  return float(s.split('-')[1])


covid['fips'] = covid.geoid.map(fix_fips)
covid['dem'] = [county_to_party[fips] if fips in county_to_party else pd.NA for fips in covid.fips]
covid['bin'] = [bins[pct_to_bin(x)] if not pd.isna(x) else 'unknown' for x in covid.dem]

census = pd.read_csv(open('co-est2020.csv', errors='replace'), dtype={'STATE': str, 'COUNTY': str})
census['fips'] = (census.STATE + census.COUNTY).map(float)
fips_to_pop = {k: v for k, v in zip(census.fips, census.POPESTIMATE2019)}
covid['pop'] = [fips_to_pop[fips] if fips in fips_to_pop else pd.NA for fips in covid.fips]
# why does merge not work?

import pylab as plt

plt.style.use('ggplot')
plt.ion()
bin_to_color = {
    k: v
    for k, v in zip(bins, 'maroon,orangered,lightcoral,skyblue,dodgerblue,mediumblue'.split(','))
}
bin_to_linestyle = {k: v for k, v in zip(bins, '- -. : : -. -'.split(' '))}
bin_to_linewidth = {k: v for k, v in zip(bins, [1, 1, 1, 2, 2, 2])}

# total deaths
ts = covid.groupby(['bin', 'date'])['deaths'].sum().to_frame()
fig, ax = plt.subplots()
for b in bins:
  res = ts.loc[b].rolling(14).mean().sort_index()
  ax.plot(
      res.index,
      res.deaths,
      label=b,
      color=bin_to_color[b],
      linestyle=bin_to_linestyle[b],
      linewidth=bin_to_linewidth[b])
ax.set_title(
    'US county-level data: NYT, MIT/MEDSL, US Census\n(https://github.com/fasiha/covid-county)',
    fontsize=12)
ax.set_ylabel('total deaths, 14-day avg')
plt.setp(ax.xaxis.get_majorticklabels(), rotation=90)
ax.legend(loc='best', ncol=2, prop={'size': 8})
plt.tight_layout()

plt.savefig('total_deaths.png', dpi=300)

# per capita
g = covid.dropna().groupby(['bin', 'date'])
ts = (g['deaths'].sum() / g['pop'].sum() * 1e5).to_frame('per_100k')

fig, ax = plt.subplots()
for b in bins:
  res = ts.loc[b].rolling(14).mean().sort_index()
  ax.plot(
      res.index,
      res.per_100k,
      label=b,
      color=bin_to_color[b],
      linestyle=bin_to_linestyle[b],
      linewidth=bin_to_linewidth[b])
ax.set_title(
    'US county-level data: NYT, MIT/MEDSL, US Census\n(https://github.com/fasiha/covid-county)',
    fontsize=12)
ax.set_ylabel('deaths per 100k, 14-day avg')
plt.setp(ax.xaxis.get_majorticklabels(), rotation=90)
ax.legend(loc='best', ncol=2, prop={'size': 8})
plt.tight_layout()

plt.savefig('per_capita_deaths.png', dpi=300)

MISSING_POP_DATA = covid[pd.isna(covid['pop'])].sort_values('deaths')
print(MISSING_POP_DATA)