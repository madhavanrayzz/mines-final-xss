import os
import time
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException

# === Config ===
chrome_instances = 10
tabs_per_instance = 20
timeout_seconds = 30
max_retries = 5

urls_file = "sorted_urls.txt"
executed_file = "executed_urls.txt"
detected_file = "detected_xss.txt"

executed_lock = threading.Lock()

# === Load Already Executed URLs ===
executed_urls = set()
if os.path.exists(executed_file):
    with open(executed_file, "r") as f:
        executed_urls = set(line.strip() for line in f if line.strip())

# === Load & Filter URLs ===
with open(urls_file, "r") as f:
    all_urls = [line.strip() for line in f if line.strip()]
    urls = [url for url in all_urls if url not in executed_urls]

urls.sort()

# === Chrome Setup ===
def get_chrome():
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")  # Uncomment when needed
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    return webdriver.Chrome(options=chrome_options)

# === Thread-safe Appending ===
def append_executed_url(url):
    with executed_lock:
        with open(executed_file, "a") as f:
            f.write(url + "\n")

# === Test Single URL with Retry ===
def test_url_with_retry(driver, url):
    for attempt in range(1, max_retries + 1):
        try:
            driver.set_page_load_timeout(timeout_seconds)
            driver.get(url)
            time.sleep(2)
            try:
                alert = driver.switch_to.alert
                alert_text = alert.text
                print(f"🛑 XSS Detected! Alert: {alert_text} | URL: {url}")
                with open(detected_file, "a") as out:
                    out.write(f"{url} | Alert: {alert_text}\n")
                alert.accept()
            except:
                pass
            append_executed_url(url)
            return True
        except (TimeoutException, WebDriverException) as e:
            print(f"⚠️ Attempt {attempt} failed for {url}: {str(e).splitlines()[0]}")
            time.sleep(1)
    print(f"❌ Skipping after {max_retries} failures: {url}")
    return False

# === Worker: One Chrome with Multiple Tabs, Self-Healing ===
def worker(instance_id, urls_chunk):
    print(f"🚀 Chrome #{instance_id} starting with {len(urls_chunk)} URLs")
    driver = get_chrome()
    handles = [driver.current_window_handle]

    for _ in range(tabs_per_instance - 1):
        driver.execute_script("window.open('');")
        handles.append(driver.window_handles[-1])

    i = 0
    while i < len(urls_chunk):
        url = urls_chunk[i]
        tab_index = i % tabs_per_instance

        try:
            driver.switch_to.window(handles[tab_index])
        except Exception:
            print(f"💥 Lost tab/window, restarting Chrome for instance #{instance_id}...")
            try:
                driver.quit()
            except:
                pass
            time.sleep(1)
            driver = get_chrome()
            handles = [driver.current_window_handle]
            for _ in range(tabs_per_instance - 1):
                driver.execute_script("window.open('');")
                handles.append(driver.window_handles[-1])
            continue  # Retry same index after restart

        test_url_with_retry(driver, url)
        i += 1

    try:
        driver.quit()
    except:
        pass

    print(f"✅ Chrome #{instance_id} finished.")

# === Main ===
def main():
    urls_per_instance = [[] for _ in range(chrome_instances)]

    # Distribute URLs round-robin
    for idx, url in enumerate(urls):
        target = idx % chrome_instances
        urls_per_instance[target].append(url)

    threads = []
    for instance_id in range(chrome_instances):
        instance_urls = urls_per_instance[instance_id]
        if not instance_urls:
            continue

        thread = threading.Thread(
            target=worker,
            args=(instance_id, instance_urls)
        )
        threads.append(thread)
        thread.start()
        time.sleep(0.3)

    for thread in threads:
        thread.join()

    print("🎯 All Chrome instances completed.")

if __name__ == "__main__":
    main()
