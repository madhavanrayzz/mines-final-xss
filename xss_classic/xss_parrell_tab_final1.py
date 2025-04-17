import os
import time
import json
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException

# === Config ===
chrome_instances = 10
tabs_per_instance = 20
timeout_seconds = 30
fallback_offset = 30
max_retries = 5

urls_file = "sorted_urls.txt"
resume_folder = "resume"
detected_file = "detected_xss.txt"

resume_locks = {}

# === Setup Resume Folder ===
if not os.path.exists(resume_folder):
    os.makedirs(resume_folder)

# === Load & Sort URLs ===
with open(urls_file, "r") as f:
    urls = [line.strip() for line in f if line.strip()]
urls.sort()

# === Resume Functions ===
def get_resume_index(instance_id):
    path = os.path.join(resume_folder, f"instance_{instance_id}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            try:
                return max(0, json.load(f).get("index", 0) - fallback_offset)
            except:
                return 0
    return 0

def save_resume_index(instance_id, index):
    path = os.path.join(resume_folder, f"instance_{instance_id}.json")
    with resume_locks[instance_id]:
        current = get_resume_index(instance_id)
        if index > current:
            with open(path, "w") as f:
                json.dump({"index": index}, f)

# === Chrome Setup ===
def get_chrome():
    chrome_options = Options()
    # Uncomment this after testing if you want headless
    # chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    return webdriver.Chrome(options=chrome_options)

# === Test Single URL with Retry ===
def test_url_with_retry(driver, url, instance_id, global_index):
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
            return True
        except (TimeoutException, WebDriverException) as e:
            print(f"⚠️ Attempt {attempt} failed for {url}: {str(e).splitlines()[0]}")
            time.sleep(1)
    print(f"❌ Skipping after {max_retries} failures: {url}")
    return False

# === Worker: One Chrome with Multiple Tabs, Self-Healing ===
def worker(instance_id, urls_chunk, index_chunk):
    print(f"🚀 Chrome #{instance_id} starting with {len(urls_chunk)} URLs")
    driver = get_chrome()
    handles = [driver.current_window_handle]

    for _ in range(tabs_per_instance - 1):
        driver.execute_script("window.open('');")
        handles.append(driver.window_handles[-1])

    i = 0
    while i < len(urls_chunk):
        url = urls_chunk[i]
        global_index = index_chunk[i]
        tab_index = i % tabs_per_instance

        try:
            driver.switch_to.window(handles[tab_index])
        except Exception as e:
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

        success = test_url_with_retry(driver, url, instance_id, global_index)
        save_resume_index(instance_id, global_index + 1)
        i += 1

    try:
        driver.quit()
    except:
        pass

    print(f"✅ Chrome #{instance_id} finished.")

# === Main ===
def main():
    total_urls = len(urls)
    urls_per_instance = [[] for _ in range(chrome_instances)]
    indexes_per_instance = [[] for _ in range(chrome_instances)]

    # Distribute URLs round-robin
    for idx, url in enumerate(urls):
        target = idx % chrome_instances
        urls_per_instance[target].append(url)
        indexes_per_instance[target].append(idx)

    threads = []
    for instance_id in range(chrome_instances):
        resume_index = get_resume_index(instance_id)

        urls_chunk = urls_per_instance[instance_id]
        index_chunk = indexes_per_instance[instance_id]

        if resume_index >= len(index_chunk):
            continue

        urls_to_process = urls_chunk[resume_index:]
        indexes_to_process = index_chunk[resume_index:]

        resume_locks[instance_id] = threading.Lock()
        thread = threading.Thread(
            target=worker,
            args=(instance_id, urls_to_process, indexes_to_process)
        )
        threads.append(thread)
        thread.start()
        time.sleep(0.3)

    for thread in threads:
        thread.join()

    print("🎯 All Chrome instances completed.")

if __name__ == "__main__":
    main()
