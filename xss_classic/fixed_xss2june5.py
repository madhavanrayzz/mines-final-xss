import os
import time
import threading
import traceback
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException

# === Config ===
chrome_instances = 3
tabs_per_instance = 2
timeout_seconds = 30
delay_seconds = 2
max_retries = 5

urls_file = "sorted_urls.txt"

# === Extract target folder from first URL ===
with open(urls_file, "r") as f:
    first_url = f.readline().strip()

def extract_folder_name(url):
    parsed = urlparse(url)
    host = parsed.hostname or "unknown"
    parts = host.split(".")
    if len(parts) > 2:
        return parts[-3]          # sub.example.com → sub
    elif len(parts) == 2:
        return parts[0]           # example.com → example
    else:
        return host

def get_unique_folder_name(base_name):
    """
    If 'base_name' exists, append 1, 2, 3… until a free name is found.
    """
    folder_name = base_name
    counter = 1
    while os.path.exists(folder_name):
        folder_name = f"{base_name}{counter}"
        counter += 1
    return folder_name

base_folder_name = extract_folder_name(first_url)
target_folder = get_unique_folder_name(base_folder_name)
os.makedirs(target_folder)        # ← now guaranteed unique

# === Paths ===
divided_folder  = os.path.join(target_folder, "divided_urls")
executed_folder = os.path.join(target_folder, "executed_urls")
detected_folder = os.path.join(target_folder, "detected_xss")
error_log_file  = os.path.join(target_folder, "errors.log")

os.makedirs(divided_folder,  exist_ok=True)
os.makedirs(executed_folder, exist_ok=True)
os.makedirs(detected_folder, exist_ok=True)

executed_lock = threading.Lock()
detected_lock = threading.Lock()
log_lock      = threading.Lock()

# === User-Agent Rotation ===
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.70 Safari/537.36",
]

# === Load URLs ===
with open(urls_file, "r") as f:
    all_urls = [line.strip() for line in f if line.strip()]

all_urls.sort()

# === Divide URLs into files ===
urls_per_instance = [[] for _ in range(chrome_instances)]
for idx, url in enumerate(all_urls):
    urls_per_instance[idx % chrome_instances].append(url)

for instance_id in range(chrome_instances):
    divided_file = os.path.join(divided_folder, f"urls_instance_{instance_id}.txt")
    with open(divided_file, "w") as f:
        for url in urls_per_instance[instance_id]:
            f.write(url + "\n")

# === Chrome Setup ===
def get_chrome(user_agent):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument(f"user-agent={user_agent}")
    return webdriver.Chrome(options=chrome_options)

# === Logging Helpers ===
def append_executed_url(url, instance_id):
    with executed_lock:
        executed_path = os.path.join(executed_folder, f"executed_{instance_id}.txt")
        with open(executed_path, "a") as f:
            f.write(url + "\n")

def log_detected_alert(url, alert_text, instance_id):
    with detected_lock:
        detected_path = os.path.join(detected_folder, f"detected_{instance_id}.txt")
        with open(detected_path, "a") as f:
            f.write(f"{url} | Alert: {alert_text}\n")

def log_error(context, ex):
    with log_lock:
        with open(error_log_file, "a") as f:
            f.write(f"=== ERROR in {context} ===\n")
            f.write(traceback.format_exc())
            f.write("\n")

# === Test URL with Alert Detection ===
def test_url_with_retry(driver, url, tab_index, handles, instance_id):
    for attempt in range(1, max_retries + 1):
        try:
            driver.set_page_load_timeout(timeout_seconds)
            driver.get(url)
            time.sleep(delay_seconds)

            try:
                alert = driver.switch_to.alert
                alert_text = alert.text
                print(f"🛑 XSS Detected! Alert: {alert_text} | URL: {url}")
                alert.accept()
                log_detected_alert(url, alert_text, instance_id)

                driver.close()
                if driver.window_handles:
                    driver.switch_to.window(driver.window_handles[0])
                driver.execute_script("window.open('');")
                new_handle = driver.window_handles[-1]
                handles[tab_index] = new_handle
                driver.switch_to.window(new_handle)

                append_executed_url(url, instance_id)
                return True
            except:
                pass

            append_executed_url(url, instance_id)
            return True

        except (TimeoutException, WebDriverException):
            print(f"⚠️ Attempt {attempt} failed for {url}")
            time.sleep(1)
        except Exception as e:
            log_error(f"test_url_with_retry for {url}", e)

    print(f"❌ Skipping after {max_retries} failures: {url}")
    return False

# === Worker Thread ===
def worker(instance_id):
    divided_file = os.path.join(divided_folder, f"urls_instance_{instance_id}.txt")
    if not os.path.exists(divided_file):
        print(f"No URLs for instance #{instance_id}. Skipping.")
        return

    with open(divided_file, "r") as f:
        urls_chunk = [line.strip() for line in f if line.strip()]

    print(f"🚀 Chrome #{instance_id} starting with {len(urls_chunk)} URLs")
    user_agent = user_agents[instance_id % len(user_agents)]
    driver = get_chrome(user_agent)
    handles = [driver.current_window_handle]

    for _ in range(tabs_per_instance - 1):
        driver.execute_script("window.open('');")
        handles.append(driver.window_handles[-1])

    i = 0
    while i < len(urls_chunk):
        url = urls_chunk[i]
        tab_index = i % tabs_per_instance

        try:
            if tab_index >= len(driver.window_handles):
                driver.execute_script("window.open('');")
                handles.append(driver.window_handles[-1])

            driver.switch_to.window(handles[tab_index])
        except Exception as e:
            print(f"💥 Lost tab/window, restarting Chrome for instance #{instance_id}...")
            log_error(f"Tab switch or Chrome failure (instance {instance_id})", e)
            try:
                driver.quit()
            except:
                pass
            time.sleep(1)
            driver = get_chrome(user_agent)
            handles = [driver.current_window_handle]
            for _ in range(tabs_per_instance - 1):
                driver.execute_script("window.open('');")
                handles.append(driver.window_handles[-1])
            continue

        test_url_with_retry(driver, url, tab_index, handles, instance_id)
        i += 1

    try:
        driver.quit()
    except Exception as e:
        log_error(f"Chrome quit failure for instance #{instance_id}", e)

    print(f"✅ Chrome #{instance_id} finished.")

# === Main Execution ===
def main():
    threads = []
    for instance_id in range(chrome_instances):
        thread = threading.Thread(target=worker, args=(instance_id,))
        threads.append(thread)
        thread.start()
        time.sleep(0.3)  # stagger startups just a bit

    for thread in threads:
        thread.join()

    print("🎯 All Chrome instances completed.")

if __name__ == "__main__":
    main()
