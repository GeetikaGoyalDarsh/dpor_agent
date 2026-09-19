import csv
from datetime import datetime
import re
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def determine_status(raw_status: str, expiration_str: str) -> str:
    """If a license expiration date is in the past, it is Expired unless explicitly Revoked/Suspended."""
    # Preserve critical punitive statuses
    if raw_status and any(k in raw_status.lower() for k in ["revoked", "suspended", "surrendered"]):
        return raw_status.capitalize()

    # Try parsing expiration date against today's date
    if expiration_str and expiration_str != "N/A":
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                exp_date = datetime.strptime(expiration_str.strip(), fmt).date()
                today = datetime.now().date()
                if exp_date < today:
                    return "Expired"
                else:
                    return "Active"
            except ValueError:
                continue

    # Default fallback to whatever was scraped or Active
    return raw_status.capitalize() if raw_status and raw_status != "Unknown" else "Active"


def extract_field_from_detail(driver, label_name: str) -> str:
    """Extracts a cell value based on label from DPOR's detail table."""
    xpath_queries = [
        f"//tr[td[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label_name.lower()}')]]/td[last()]",
        f"//tr[th[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label_name.lower()}')]]/td[1]",
        f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label_name.lower()}')]/following-sibling::td[1]",
        f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label_name.lower()}')]/following::td[1]"
    ]
    for xpath in xpath_queries:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for el in elements:
                val = el.text.strip()
                if val and label_name.lower() not in val.lower():
                    return val
        except Exception:
            continue
    return ""


def parse_details_from_page(driver):
    """Pulls raw status and expiration date, then evaluates expiration logic."""
    raw_status = extract_field_from_detail(driver, "Status")
    expiration = extract_field_from_detail(driver, "Expiration Date")
    if not expiration:
        expiration = extract_field_from_detail(driver, "Expiration")

    # Body text regex fallback
    body_text = driver.find_element(By.TAG_NAME, "body").text

    if not raw_status:
        m_status = re.search(r'(?:License\s+Status|Status)\s*[:\-]?\s*([A-Za-z]+)', body_text, re.IGNORECASE)
        if m_status:
            raw_status = m_status.group(1).strip()
        elif "revoked" in body_text.lower():
            raw_status = "Revoked"
        elif "suspended" in body_text.lower():
            raw_status = "Suspended"

    if not expiration:
        # Match YYYY-MM-DD or MM/DD/YYYY
        m_date = re.search(r'(?:Expiration(?:\s*Date)?|Expires)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})', body_text, re.IGNORECASE)
        if m_date:
            expiration = m_date.group(1).strip()

    final_expiration = expiration or "N/A"
    # Auto-evaluate: past expiration date = Expired
    final_status = determine_status(raw_status, final_expiration)

    return final_status, final_expiration


def scrape_dpor(search_query: str = "Smith", max_records: int = 10, output_csv: str = "dpor_licenses.csv"):
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        url = "https://dporweb.dpor.virginia.gov/LicenseLookup/"
        print(f"Loading {url}...")
        driver.get(url)
        time.sleep(3)

        # 1. Close modal popup if present
        for btn in driver.find_elements(By.XPATH, "//button[contains(text(), 'Close') or contains(text(), '×')]"):
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1)

        # 2. Enter search query
        if search_query:
            print(f"Searching for '{search_query}'...")
            inputs = driver.find_elements(By.XPATH, "//input[@type='text' or not(@type)]")
            for inp in inputs:
                if inp.is_displayed() and inp.is_enabled():
                    inp.clear()
                    inp.send_keys(search_query)
                    inp.send_keys(Keys.RETURN)
                    time.sleep(4)
                    break

        # 3. Read initial results
        rows = driver.find_elements(By.XPATH, "//table//tr[count(./td) >= 4]")
        items = []

        for row in rows:
            cells = row.find_elements(By.XPATH, "./td")
            lic_input = cells[0].find_elements(By.XPATH, ".//input[@value]")
            lic_num = lic_input[0].get_attribute("value").strip() if lic_input else cells[0].text.strip()

            if not lic_num or not lic_num.isdigit():
                continue

            name = cells[1].text.strip() if len(cells) > 1 else ""
            lic_type = cells[3].text.strip() if len(cells) > 3 else ""

            items.append({
                "license_num": lic_num,
                "name": name,
                "license_type": lic_type
            })

        print(f"Found {len(items)} licenses. Fetching details for up to {max_records} items...")

        records = []

        # 4. Lookup each record in a new tab
        for i, item in enumerate(items[:max_records]):
            lic_num = item["license_num"]
            print(f"[{i+1}/{min(len(items), max_records)}] Fetching #{lic_num} ({item['name']})...")

            driver.switch_to.new_window('tab')
            try:
                driver.get("https://dporweb.dpor.virginia.gov/LicenseLookup/")
                time.sleep(2)

                # Close modal if present
                for btn in driver.find_elements(By.XPATH, "//button[contains(text(), 'Close') or contains(text(), '×')]"):
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)

                # Search specifically for this license
                inputs = driver.find_elements(By.XPATH, "//input[@type='text' or not(@type)]")
                for inp in inputs:
                    if inp.is_displayed() and inp.is_enabled():
                        inp.clear()
                        inp.send_keys(lic_num)
                        inp.send_keys(Keys.RETURN)
                        time.sleep(3)
                        break

                # Extract status & expiration date
                status, expiration = parse_details_from_page(driver)

                record = {
                    "License Holder Name": item["name"],
                    "License Number": lic_num,
                    "License Type / Trade": item["license_type"],
                    "License Status": status,
                    "Expiration Date": expiration
                }
                print(f"   -> Status: {status} | Expiration: {expiration}")
                records.append(record)

            except Exception as err:
                print(f"  Error on #{lic_num}: {err}")
            finally:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(1)

        # 5. Export to CSV
        if records:
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
                writer.writerows(records)
            print(f"\nSaved all {len(records)} records to '{output_csv}'!")

        return records

    finally:
        driver.quit()


if __name__ == "__main__":
    # If passed as a command-line argument, use it; otherwise, ask the user interactively
    if len(sys.argv) > 1:
        query = sys.argv[1].strip()
    else:
        query = input("Enter a License Number, Business Name, or Individual Name to search: ").strip()

    # Ensure the user didn't just press Enter on an empty input
    while not query:
        print("Search query cannot be empty.")
        query = input("Please enter a License Number, Business Name, or Individual Name: ").strip()

    scrape_dpor(query)
