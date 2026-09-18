import csv
import re
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def parse_details_from_page(driver):
    body_text = driver.find_element(By.TAG_NAME, "body").text
    
    # Quick regex match for Status
    status_match = re.search(r'(?:License\s+Status|Status)\s*[:\-]?\s*([A-Za-z]+)', body_text, re.IGNORECASE)
    status = status_match.group(1).strip() if status_match else ("Active" if "active" in body_text.lower() else "Expired")

    # Quick regex match for Expiration Date
    date_match = re.search(r'(?:Expiration|Expires|Exp\s*Date)\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4})', body_text, re.IGNORECASE)
    expiration = date_match.group(1).strip() if date_match else "N/A"

    return status, expiration


def scrape_dpor(search_query: str = "Smith", max_records: int = 10, output_csv: str = "dpor_licenses.csv"):
    options = webdriver.ChromeOptions()
    # RUN HEADLESS: Everything happens in memory without opening/re-rendering screens
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        url = "https://dporweb.dpor.virginia.gov/LicenseLookup/"
        print(f"Connecting to {url} (running silently in background)...")
        driver.get(url)

        # Dismiss modal if present
        for btn in driver.find_elements(By.XPATH, "//button[contains(text(), 'Close') or contains(text(), '×')]"):
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)

        # Perform Search
        print(f"Searching for '{search_query}'...")
        inputs = driver.find_elements(By.XPATH, "//input[@type='text' or not(@type)]")
        for inp in inputs:
            if inp.is_displayed() and inp.is_enabled():
                inp.clear()
                inp.send_keys(search_query)
                inp.send_keys(Keys.RETURN)
                time.sleep(3)
                break

        # Grab all rows from the initial search table
        rows = driver.find_elements(By.XPATH, "//table//tr[count(./td) >= 4]")
        summary_records = []

        for row in rows:
            cells = row.find_elements(By.XPATH, "./td")
            lic_input = cells[0].find_elements(By.XPATH, ".//input[@value]")
            lic_num = lic_input[0].get_attribute("value").strip() if lic_input else cells[0].text.strip()

            if not lic_num or not lic_num.isdigit():
                continue

            summary_records.append({
                "license_num": lic_num,
                "name": cells[1].text.strip() if len(cells) > 1 else "",
                "license_type": cells[3].text.strip() if len(cells) > 3 else ""
            })

        print(f"Found {len(summary_records)} results. Extracting complete records...")

        full_records = []
        for i, item in enumerate(summary_records[:max_records]):
            lic_num = item["license_num"]
            # Look up the license directly
            driver.get(f"https://dporweb.dpor.virginia.gov/LicenseLookup/")
            
            # Direct quick search
            for inp in driver.find_elements(By.XPATH, "//input[@type='text' or not(@type)]"):
                if inp.is_displayed():
                    inp.send_keys(lic_num)
                    inp.send_keys(Keys.RETURN)
                    break
            time.sleep(1)

            status, exp_date = parse_details_from_page(driver)
            record = {
                "License Holder Name": item["name"],
                "License Number": lic_num,
                "License Type / Trade": item["license_type"],
                "License Status": status,
                "Expiration Date": exp_date
            }
            print(f"[{i+1}/{min(len(summary_records), max_records)}] {record['License Number']} | {record['License Holder Name']} | {status} | {exp_date}")
            full_records.append(record)

        if full_records:
            fieldnames = [
                "License Holder Name",
                "License Number",
                "License Type / Trade",
                "License Status",
                "Expiration Date"
            ]
            with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(full_records)
            print(f"\nDone! Saved {len(full_records)} records directly into '{output_csv}'.")

        return full_records

    finally:
        driver.quit()


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "Smith"
    scrape_dpor(query)
