import csv
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def scrape_dpor(search_query: str = None, output_csv: str = "dpor_licenses.csv"):
    options = webdriver.ChromeOptions()
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

        # 1. Dismiss popup/overlay modal if present
        close_buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(text(), 'Close') or contains(text(), '×') or @aria-label='Close']"
        )
        for btn in close_buttons:
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1)

        # 2. Enter search query if provided
        if search_query:
            print(f"Searching for: {search_query}...")
            inputs = driver.find_elements(By.XPATH, "//input[@type='text' or not(@type)]")
            for inp in inputs:
                if inp.is_displayed() and inp.is_enabled():
                    inp.clear()
                    inp.send_keys(search_query)
                    inp.send_keys(Keys.RETURN)
                    time.sleep(4)
                    break

        # 3. Extract table records and extract the button value for the license number
        records = []
        tables = driver.find_elements(By.TAG_NAME, "table")

        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.XPATH, "./td")
                if len(cells) < 4:
                    continue  # Skip header or empty rows

                # License number is stored inside an <input type="submit"> value attribute
                license_input = cells[0].find_elements(By.XPATH, ".//input[@value]")
                if license_input:
                    license_num = license_input[0].get_attribute("value").strip()
                else:
                    license_num = cells[0].text.strip()

                name = cells[1].text.strip() if len(cells) > 1 else ""
                address = cells[2].text.strip() if len(cells) > 2 else ""
                license_type = cells[3].text.strip() if len(cells) > 3 else ""
                board = cells[4].text.strip() if len(cells) > 4 else ""

                if license_num or name:
                    records.append({
                        "License Number": license_num,
                        "Name": name,
                        "Address": address,
                        "License Type": license_type,
                        "Board": board
                    })

        # 4. Print preview and save to CSV
        print(f"\nSuccessfully scraped {len(records)} records:")
        for r in records[:5]:
            print(r)

        if records:
            with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)
            print(f"\nSaved all records to '{output_csv}'!")

        return records

    finally:
        driver.quit()


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else None
    scrape_dpor(query)