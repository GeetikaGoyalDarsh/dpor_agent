from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

wait = WebDriverWait(driver, 20)

iframes = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "iframe")))
print("Found iframes:", len(iframes))
