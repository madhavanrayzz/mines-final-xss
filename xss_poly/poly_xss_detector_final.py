import os
import time
import socket
import random
from multiprocessing import Process
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

# === CONFIG ===
chrome_path = "/home/maddy/Documents/project/chromedriver-linux64/chromedriver"
input_file = "constructed_polygots_urls.txt"
alert_file = "alert_xss_found.txt"
resume_file = "resume.log"
tabs_count = 2
parallel_browsers = 2
resume_fallback = 30

# === User Agents ===
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.90 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 11; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.85 Mobile Safari/537.36"
]

# === Functions ===

def check_internet():
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2)
        return True
    except:
        return False

def read_resume_index():
    if os.path.exists(resume_file):
        with open(resume_file, "r") as f:
            idx = int(f.read().strip())
            return max(0, idx - resume_fallback)
    return 0

def write_resume_index(index):
    with open(resume_file, "w") as f:
        f.write(str(index))

def chunkify(lst, n):
    """Split list into n chunks as evenly as possible"""
    return [lst[i::n] for i in range(n)]

def xss_worker(name, url_chunks, base_index):
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Uncomment to run headless

    # Randomize user-agent
    user_agent = random.choice(USER_AGENTS)
    chrome_options.add_argument(f"user-agent={user_agent}")

    # Additional browser stability options
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(chrome_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    for chunk_index, chunk in enumerate(url_chunks):
        index_offset = base_index + chunk_index * tabs_count

        for i, url in enumerate(chunk):
            write_resume_index(index_offset + i)
            if not check_internet():
                print(f"[{name}] ❌ No internet. Exiting to resume later.")
                driver.quit()
                return

            try:
                if i == 0:
                    driver.get(url)
                else:
                    driver.execute_script(f"window.open('{url}', '_blank');")
                time.sleep(3)  # Give payloads time to execute
            except WebDriverException as e:
                print(f"[{name}] ⚠️ Failed to open {url} | {e.msg}")
                continue

        tabs = driver.window_handles

        for i in range(len(chunk)):
            driver.switch_to.window(tabs[i])
            time.sleep(2)
            try:
                alert = Alert(driver)
                alert_text = alert.text
                print(f"[{name}] 🛑 XSS detected: {driver.current_url} | Alert Text: {alert_text}")
                with open(alert_file, "a") as af:
                    af.write(driver.current_url + "\n")
                alert.accept()
            except:
                print(f"[{name}] ✅ No XSS popup on: {driver.current_url}")

        # Close extra tabs
        for i in range(len(tabs) - 1, 0, -1):
            driver.switch_to.window(tabs[i])
            driver.close()
        driver.switch_to.window(tabs[0])

    driver.quit()

# === Main ===

def main():
    with open(input_file, "r") as f:
        urls = [url.strip() for url in f if url.strip()]

    start_index = read_resume_index()
    urls = urls[start_index:]

    all_chunks = [urls[i:i + tabs_count] for i in range(0, len(urls), tabs_count)]

    grouped_chunks = chunkify(all_chunks, parallel_browsers)

    processes = []
    for i, chunk_group in enumerate(grouped_chunks):
        base_index = start_index + i * len(chunk_group) * tabs_count
        p = Process(target=xss_worker, args=(f"Worker-{i+1}", chunk_group, base_index))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

if __name__ == "__main__":
    main()
