import os
import time
import threading
import traceback
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
executed_file = "executed_urls.txt"
detected_file = "detected_xss.txt"
error_log_file = "errors.log"

executed_lock = threading.Lock()
detected_lock = threading.Lock()
log_lock = threading.Lock()

# === User-Agent Rotation ===
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.70 Safari/537.36",
]

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
def get_chrome(user_agent):
    chrome_options = Options()
    #chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument(f"user-agent={user_agent}")
    return webdriver.Chrome(options=chrome_options)

# === Logging Helpers ===
def append_executed_url(url):
    with executed_lock:
        with open(executed_file, "a") as f:
            f.write(url + "\n")

def log_detected_alert(url, alert_text):
    with detected_lock:
        with open(detected_file, "a") as f:
            f.write(f"{url} | Alert: {alert_text}\n")

def log_error(context, ex):
    with log_lock:
        with open(error_log_file, "a") as f:
            f.write(f"=== ERROR in {context} ===\n")
            f.write(traceback.format_exc())
            f.write("\n")

# === Test URL with Alert Detection ===
def test_url_with_retry(driver, url, tab_index, handles):
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
                log_detected_alert(url, alert_text)

                # Close current tab and reopen
                driver.close()
                if driver.window_handles:
                    driver.switch_to.window(driver.window_handles[0])
                driver.execute_script("window.open('');")
                new_handle = driver.window_handles[-1]
                handles[tab_index] = new_handle
                driver.switch_to.window(new_handle)

                append_executed_url(url)
                return True
            except:
                pass

            append_executed_url(url)
            return True
        except (TimeoutException, WebDriverException):
            print(f"⚠️ Attempt {attempt} failed for {url}")
            time.sleep(1)
        except Exception as e:
            log_error(f"test_url_with_retry for {url}", e)

    print(f"❌ Skipping after {max_retries} failures: {url}")
    return False

# === Worker Thread ===
def worker(instance_id, urls_chunk):
    print(f"🚀 Chrome #{instance_id} starting with {len(urls_chunk)} URLs")
    user_agent = user_agents[instance_id % len(user_agents)]
    driver = get_chrome(user_agent)
    handles = [driver.current_window_handle]

    # Open other tabs
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

        test_url_with_retry(driver, url, tab_index, handles)
        i += 1

    try:
        driver.quit()
    except Exception as e:
        log_error(f"Chrome quit failure for instance #{instance_id}", e)

    print(f"✅ Chrome #{instance_id} finished.")

# === Main ===
def main():
    urls_per_instance = [[] for _ in range(chrome_instances)]

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
