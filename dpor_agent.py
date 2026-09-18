import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def scrape_dpor(license_query: str = None):
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

        wait = WebDriverWait(driver, 15)

        # 1. Close any overlay / modal dialog if it popped up (the 'x Close' button)
        close_buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(text(), 'Close') or contains(text(), '×') or @aria-label='Close']"
        )
        for btn in close_buttons:
            if btn.is_displayed():
                print("Dismissing overlay modal...")
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1)

        # 2. If a specific license was provided, perform a search
        if license_query:
            print(f"Searching for query: {license_query}...")
            # Locate any visible text input
            inputs = driver.find_elements(By.XPATH, "//input[@type='text' or not(@type)]")
            search_box = None
            for inp in inputs:
                if inp.is_displayed() and inp.is_enabled():
                    search_box = inp
                    break

            if search_box:
                search_box.clear()
                search_box.send_keys(license_query)
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)

        # 3. Collect all clickable license records (the input buttons with license numbers)
        license_buttons = driver.find_elements(
            By.XPATH,
            "//input[@type='submit' or @type='button'][string-length(@value) >= 6 and translate(@value, '0123456789', '')='']"
        )

        all_licenses = [btn.get_attribute("value") for btn in license_buttons if btn.get_attribute("value")]
        print(f"\nFound {len(all_licenses)} license record(s): {all_licenses}")

        records_data = []

        # 4. Extract data from any visible tables
        tables = driver.find_elements(By.TAG_NAME, "table")
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = [c.text.strip() for c in row.find_elements(By.XPATH, "./th|./td")]
                if any(cells):
                    records_data.append(cells)

        print("\n--- Extracted Table Data ---")
        for r in records_data[:20]:
            print(r)

        return records_data

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        return []

    finally:
        driver.quit()


if __name__ == "__main__":
    # If passed via command line, search for it; otherwise extracts current records
    query = sys.argv[1] if len(sys.argv) > 1 else None
    scrape_dpor(query)