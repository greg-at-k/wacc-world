"""Fetch and parse the four public data sources required by the assignment."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup


BETA_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
RATINGS_URL = "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html"
OECD_PAGE_URL = (
    "https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/"
    "full-report/statutory-corporate-income-tax-rates_440f9286.html"
)
OECD_DATA_URL = "https://stat.link/0qkxo1"
TRADING_ECONOMICS_URL = "https://tradingeconomics.com/bonds"


@dataclass(frozen=True)
class Country:
    name: str
    iso3: str
    slug: str
    currency: str


COUNTRIES = [
    Country("Argentina", "ARG", "argentina", "ARS"),
    Country("Australia", "AUS", "australia", "AUD"),
    Country("Austria", "AUT", "austria", "EUR"),
    Country("Belgium", "BEL", "belgium", "EUR"),
    Country("Brazil", "BRA", "brazil", "BRL"),
    Country("Bulgaria", "BGR", "bulgaria", "BGN"),
    Country("Canada", "CAN", "canada", "CAD"),
    Country("Chile", "CHL", "chile", "CLP"),
    Country("China", "CHN", "china", "CNY"),
    Country("Colombia", "COL", "colombia", "COP"),
    Country("Croatia", "HRV", "croatia", "EUR"),
    Country("Czechia", "CZE", "czech-republic", "CZK"),
    Country("Denmark", "DNK", "denmark", "DKK"),
    Country("Egypt", "EGY", "egypt", "EGP"),
    Country("Estonia", "EST", "estonia", "EUR"),
    Country("Finland", "FIN", "finland", "EUR"),
    Country("France", "FRA", "france", "EUR"),
    Country("Germany", "DEU", "germany", "EUR"),
    Country("Greece", "GRC", "greece", "EUR"),
    Country("Hong Kong", "HKG", "hong-kong", "HKD"),
    Country("Hungary", "HUN", "hungary", "HUF"),
    Country("Iceland", "ISL", "iceland", "ISK"),
    Country("India", "IND", "india", "INR"),
    Country("Indonesia", "IDN", "indonesia", "IDR"),
    Country("Ireland", "IRL", "ireland", "EUR"),
    Country("Israel", "ISR", "israel", "ILS"),
    Country("Italy", "ITA", "italy", "EUR"),
    Country("Japan", "JPN", "japan", "JPY"),
    Country("Malaysia", "MYS", "malaysia", "MYR"),
    Country("Mexico", "MEX", "mexico", "MXN"),
    Country("Netherlands", "NLD", "netherlands", "EUR"),
    Country("New Zealand", "NZL", "new-zealand", "NZD"),
    Country("Nigeria", "NGA", "nigeria", "NGN"),
    Country("Norway", "NOR", "norway", "NOK"),
    Country("Pakistan", "PAK", "pakistan", "PKR"),
    Country("Peru", "PER", "peru", "PEN"),
    Country("Philippines", "PHL", "philippines", "PHP"),
    Country("Poland", "POL", "poland", "PLN"),
    Country("Portugal", "PRT", "portugal", "EUR"),
    Country("Romania", "ROU", "romania", "RON"),
    Country("Saudi Arabia", "SAU", "saudi-arabia", "SAR"),
    Country("Singapore", "SGP", "singapore", "SGD"),
    Country("Slovakia", "SVK", "slovakia", "EUR"),
    Country("Slovenia", "SVN", "slovenia", "EUR"),
    Country("South Africa", "ZAF", "south-africa", "ZAR"),
    Country("South Korea", "KOR", "south-korea", "KRW"),
    Country("Spain", "ESP", "spain", "EUR"),
    Country("Sweden", "SWE", "sweden", "SEK"),
    Country("Switzerland", "CHE", "switzerland", "CHF"),
    Country("Thailand", "THA", "thailand", "THB"),
    Country("Turkey", "TUR", "turkey", "TRY"),
    Country("Ukraine", "UKR", "ukraine", "UAH"),
    Country("United Arab Emirates", "ARE", "united-arab-emirates", "AED"),
    Country("United Kingdom", "GBR", "united-kingdom", "GBP"),
    Country("United States", "USA", "united-states", "USD"),
    Country("Vietnam", "VNM", "vietnam", "VND"),
]
COUNTRY_BY_NAME = {country.name: country for country in COUNTRIES}


class DataSourceError(RuntimeError):
    pass


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/131 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


def _get(url: str, timeout: int = 25) -> requests.Response:
    try:
        response = _session().get(url, timeout=timeout)
        response.raise_for_status()
        if not response.content:
            raise DataSourceError(f"Empty response from {url}")
        return response
    except requests.RequestException as exc:
        raise DataSourceError(f"Could not retrieve {url}: {exc}") from exc


def fetch_industry_betas() -> tuple[pd.DataFrame, str]:
    response = _get(BETA_URL)
    try:
        raw = pd.read_excel(
            io.BytesIO(response.content), sheet_name="Industry Averages", header=None
        )
        date_value = pd.to_datetime(raw.iloc[0, 1]).date().isoformat()
        frame = pd.read_excel(
            io.BytesIO(response.content), sheet_name="Industry Averages", header=9
        )
        result = frame[["Industry Name", "Unlevered beta"]].rename(
            columns={"Industry Name": "industry", "Unlevered beta": "unlevered_beta"}
        )
        result = result.dropna().sort_values("industry").reset_index(drop=True)
        if result.empty or "Software (System & Application)" not in set(result["industry"]):
            raise ValueError("Expected industry rows were not present")
        return result, date_value
    except Exception as exc:
        raise DataSourceError(f"Damodaran beta workbook format changed: {exc}") from exc


def fetch_bbb_spread() -> tuple[float, str]:
    response = _get(RATINGS_URL)
    soup = BeautifulSoup(response.content, "lxml")
    for row in soup.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        if "Baa2/BBB" in cells:
            rating_index = cells.index("Baa2/BBB")
            if rating_index + 1 < len(cells):
                match = re.search(r"([0-9.]+)%", cells[rating_index + 1])
                if match:
                    spread = float(match.group(1)) / 100
                    break
    else:
        raise DataSourceError("Baa2/BBB row was not found on the Damodaran page")

    page_text = soup.get_text(" ", strip=True)
    date_match = re.search(r"Data used is as of\s+([A-Za-z]+\s+\d{4})", page_text, re.I)
    source_date = date_match.group(1) if date_match else "Date not stated"
    return spread, source_date


def fetch_oecd_tax_rates() -> tuple[pd.DataFrame, str]:
    response = _get(OECD_DATA_URL)
    try:
        raw = pd.read_excel(io.BytesIO(response.content), sheet_name="g2_1", header=None)
        title = " ".join(str(value) for value in raw.iloc[:5, 0].dropna())
        year_match = re.search(r"(20\d{2})", title)
        year = year_match.group(1) if year_match else "Year not stated"
        result = raw.iloc[:, :2].copy()
        result.columns = ["iso3", "tax_rate"]
        result["iso3"] = result["iso3"].astype(str).str.strip()
        result["tax_rate"] = pd.to_numeric(result["tax_rate"], errors="coerce")
        result = result[
            result["iso3"].str.fullmatch(r"[A-Z]{3}") & result["tax_rate"].notna()
        ].reset_index(drop=True)
        if "USA" not in set(result["iso3"]):
            raise ValueError("Expected USA tax-rate row was not present")
        return result, year
    except Exception as exc:
        raise DataSourceError(f"OECD workbook format changed: {exc}") from exc


def fetch_bond_yield(country: Country) -> tuple[float, str, str]:
    url = f"https://tradingeconomics.com/{country.slug}/government-bond-yield"
    response = _get(url)
    soup = BeautifulSoup(response.content, "lxml")
    value_node = soup.find(id="market_last")
    if not value_node:
        raise DataSourceError(f"Trading Economics did not show a 10-year yield for {country.name}")
    try:
        value = float(value_node.get_text(strip=True).replace(",", "")) / 100
    except ValueError as exc:
        raise DataSourceError(f"Could not parse the {country.name} 10-year yield") from exc

    text = soup.get_text(" ", strip=True)
    date_match = re.search(r"last updated on\s+([A-Za-z]+\s+\d{1,2}\s+of\s+\d{4})", text, re.I)
    if date_match:
        raw_date = re.sub(r"\s+of\s+", " ", date_match.group(1), flags=re.I)
        try:
            source_date = datetime.strptime(raw_date, "%B %d %Y").date().isoformat()
        except ValueError:
            source_date = raw_date
    else:
        script_match = re.search(rb"TELastUpdate\s*=\s*'(\d{8})", response.content)
        source_date = (
            datetime.strptime(script_match.group(1).decode(), "%Y%m%d").date().isoformat()
            if script_match
            else "Date not stated"
        )
    return value, source_date, url

