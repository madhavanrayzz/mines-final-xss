import os
import time
import threading
import random
import psutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException

# === USER AGENTS ===
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:112.0) Gecko/20100101 Firefox/112.0",
    # Add more here...
]

# === Generate Fake IPs ===
def generate_fake_ip(base="127.0.0.", start=1, end=255):
    return f"{base}{random.randint(start, end)}"

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
def get_chrome(user_agent=None):
    chrome_options = Options()
    if user_agent:
        chrome_options.add_argument(f"user-agent={user_agent}")
    # chrome_options.add_argument("--headless=new")  # Uncomment when needed
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    driver = webdriver.Chrome(options=chrome_options)
    driver.service.process  # Ensure the process is tracked
    return driver

# === Check Chrome is Alive ===
def is_chrome_alive(driver):
    try:
        return psutil.pid_exists(driver.service.process.pid)
    except:
        return False

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

            # === Visit domain root first (required before setting cookies)
            domain = "/".join(url.split("/")[:3])  # https://example.com
            driver.get(domain)
            time.sleep(1)

            # === Add spoofed IP as cookie
            fake_ip = generate_fake_ip()
            try:
                driver.add_cookie({"name": "X-Forwarded-For", "value": fake_ip})
                print(f"🕵️ Spoofed IP: {fake_ip} added to {domain}")
            except Exception as e:
                print(f"❗ Cookie injection failed: {e}")

            # === Load the actual test URL
            driver.get(url)
            time.sleep(2)

            # === Check for alert
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
    user_agent = random.choice(user_agents)
    driver = get_chrome(user_agent=user_agent)

    def setup_browser():
        driver = get_chrome()
        handles = [driver.current_window_handle]
        for _ in range(tabs_per_instance - 1):
            try:
                driver.execute_script("window.open('');")
                time.sleep(0.1)  # Delay to avoid overwhelming Chrome
                handles.append(driver.window_handles[-1])
            except Exception as e:
                print(f"❗ Tab creation failed: {e}")
        return driver, handles

    driver, handles = setup_browser()

    i = 0
    while i < len(urls_chunk):
        url = urls_chunk[i]
        tab_index = i % tabs_per_instance

        # Tab/window validation
        if tab_index >= len(driver.window_handles):
            print(f"⚠️ Tab #{tab_index} is missing, restarting browser #{instance_id}")
            try:
                driver.quit()
            except:
                pass
            time.sleep(1)
            driver, handles = setup_browser()
            continue

        if not is_chrome_alive(driver):
            print(f"💀 Chrome process died for instance #{instance_id}, restarting...")
            try:
                driver.quit()
            except:
                pass
            time.sleep(1)
            driver, handles = setup_browser()
            continue

        try:
            driver.switch_to.window(handles[tab_index])
        except Exception as e:
            print(f"💥 Tab switch failed: {e}, restarting Chrome for instance #{instance_id}")
            try:
                driver.quit()
            except:
                pass
            time.sleep(1)
            driver, handles = setup_browser()
            continue

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
