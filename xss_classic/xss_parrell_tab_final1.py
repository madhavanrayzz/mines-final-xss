import os
import time
import json
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException

# === Settings ===
chrome_instances = 3
tabs_per_instance = 3
total_tabs = chrome_instances * tabs_per_instance
timeout_seconds = 30

urls_file = "constructed_urls.txt"
resume_file = "resume.json"
detected_file = "detected_xss.txt"

# === Resume Handling ===
def get_resume_index():
    if os.path.exists(resume_file):
        with open(resume_file, "r") as f:
            return json.load(f).get("index", 0)
    return 0

def save_resume_index(index):
    with open(resume_file, "w") as f:
        json.dump({"index": index}, f)

# === Load URLs ===
with open(urls_file, "r") as f:
    urls = [line.strip() for line in f if line.strip()]

# === Chrome Setup ===
def get_chrome():
    chrome_options = Options()
#    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    return webdriver.Chrome(options=chrome_options)

# === Test Function ===
def test_url(driver, url, index):
    try:
        driver.set_page_load_timeout(timeout_seconds)
        driver.get(url)

        # Wait for alert or full load
        time.sleep(3)
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"🛑 XSS Detected! Alert Text: {alert_text} | URL: {url}")
            with open(detected_file, "a") as out:
                out.write(f"{url} | Alert: {alert_text}\n")
            alert.accept()
        except:
            pass
    except TimeoutException:
        print(f"⏳ Timeout loading URL: {url}")
    except WebDriverException as e:
        print(f"❌ WebDriver error on {url}: {str(e).splitlines()[0]}")
    finally:
        save_resume_index(index + 1)

# === Worker Thread ===
def worker(url_list, start_index):
    driver = get_chrome()
    for i, url in enumerate(url_list):
        index = start_index + i
        test_url(driver, url, index)
    driver.quit()

# === Main Logic ===
def main():
    resume_index = get_resume_index()
    print(f"🔁 Resuming from index: {resume_index} / Total: {len(urls)}")

    remaining_urls = urls[resume_index:]
    chunk_size = len(remaining_urls) // chrome_instances + 1

    threads = []
    for i in range(chrome_instances):
        start = i * chunk_size
        end = min(start + chunk_size, len(remaining_urls))
        if start >= end:
            break
        print(f"🚀 Launching Chrome instance #{i + 1}")
        thread = threading.Thread(target=worker, args=(remaining_urls[start:end], resume_index + start))
        threads.append(thread)
        thread.start()
        time.sleep(1)

    for thread in threads:
        thread.join()

    print("✅ All tasks completed.")

if __name__ == "__main__":
    main()

