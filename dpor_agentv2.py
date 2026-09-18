import requests
from bs4 import BeautifulSoup
import pandas as pd

BASE_URL = "https://www.dpor.virginia.gov/LicenseLookup"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def search_dpor(query):
    """
    Perform a search on DPOR using a keyword.
    """
    params = {"search": query}
    response = requests.get(BASE_URL, params=params, headers=HEADERS)
    response.raise_for_status()
    return response.text


def parse_licenses(html):
    """
    Extract real license records from DPOR search results.
    """
    soup = BeautifulSoup(html, "html.parser")
    records = []

    # Each license result is inside <div class="views-row">
    rows = soup.select("div.views-row")

    for row in rows:
        def safe_select(selector):
            el = row.select_one(selector)
            return el.get_text(strip=True) if el else ""

        record = {
            "license_holder_name": safe_select(".field--name-title"),
            "license_number": safe_select(".field--name-field-license-number"),
            "license_type": safe_select(".field--name-field-license-type"),
            "license_status": safe_select(".field--name-field-license-status"),
            "expiration_date": safe_select(".field--name-field-expiration-date"),
        }

        # Only add records that have at least a license number
        if record["license_number"]:
            records.append(record)

    return records

def parse_license_detail(html):
    soup = BeautifulSoup(html, "html.parser")

    def get(selector):
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else ""

    return {
        "name": get(".field--name-title"),
        "dba": get(".field--name-field-dba-names"),
        "license_number": get(".field--name-field-license-number"),
        "license_description": get(".field--name-field-license-description"),
        "firm_type": get(".field--name-field-firm-type"),
        "rank": get(".field--name-field-rank"),
        "address": get(".field--name-field-address"),
        "specialties": get(".field--name-field-specialties"),
        "initial_certification_date": get(".field--name-field-initial-certification-date"),
        "expiration_date": get(".field--name-field-expiration-date"),
    }



def collect_real_dpor_data():
    """
    Collect real license records from multiple home service trades.
    """
    search_terms = [
        "HVAC",
        "plumbing",
        "electrical",
        "contractor",
        "home inspection"
    ]

    all_records = []

    for term in search_terms:
        print(f"Searching DPOR for: {term}")
        html = search_dpor(term)
        records = parse_licenses(html)
        print(f"Found {len(records)} records for {term}")
        all_records.extend(records)

    return all_records


def save_to_csv(records):
    df = pd.DataFrame(records)
    df.to_csv("DPOR_License_Data.csv", index=False)
    print(f"Saved {len(records)} records to DPOR_License_Data.csv")


if __name__ == "__main__":
    records = collect_real_dpor_data()
    save_to_csv(records)
