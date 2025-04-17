import os
import time
import socket
from multiprocessing import Process
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === CONFIG ===
chrome_path = "/home/maddy/Documents/project/chromedriver-linux64/chromedriver"
input_file = "constructed_urls.txt"
alert_file = "alert_xss_found.txt"
screenshot_log_file = "alert_screenshots_log.txt"
resume_file = "resume.log"
failed_tabs_file = "failed_tabs.txt"
tabs_count = 12
parallel_browsers = 2
resume_fallback = 30

# === Functions ===

def check_internet():
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2)
        return True
    except:
        return False

def read_resume_url_index(urls):
    if os.path.exists(resume_file):
        with open(resume_file, "r") as f:
            last_url = f.read().strip()
            if last_url in urls:
                idx = urls.index(last_url)
                return max(0, idx - resume_fallback)
    return 0

def write_resume_url(current_url):
    with open(resume_file, "w") as f:
        f.write(current_url.strip())

def chunkify(lst, n):
    return [lst[i::n] for i in range(n)]

def xss_worker(name, url_chunks, base_index):
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Keep visible
    service = Service(chrome_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    for chunk_index, chunk in enumerate(url_chunks):
        index_offset = base_index + chunk_index * tabs_count

        # Open tabs
        for i, url in enumerate(chunk):
            write_resume_url(url)
            if not check_internet():
                print(f"[{name}] ❌ No internet. Exiting to resume later.")
                driver.quit()
                return
            try:
                if i == 0:
                    driver.get(url)
                else:
                    try:
                        driver.execute_script(f"window.open('{url}', '_blank');")
                    except WebDriverException:
                        print(f"[{name}] ❌ Failed to open: {url}")
                        with open(failed_tabs_file, "a") as ff:
                            ff.write(url + "\n")
                        continue
            except WebDriverException as e:
                print(f"[{name}] ⚠️ WebDriver error: {url} | {e.msg}")
                with open(failed_tabs_file, "a") as ff:
                    ff.write(url + "\n")
                continue

        # Wait for full page load
        tabs = driver.window_handles
        for i in range(len(chunk)):
            driver.switch_to.window(tabs[i])
            try:
                WebDriverWait(driver, 30).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except:
                print(f"[{name}] ⏳ Timeout while loading: {driver.current_url}")
                with open(failed_tabs_file, "a") as ff:
                    ff.write(driver.current_url + "\n")

        # Check each tab for alert
        for i in range(len(chunk)):
            driver.switch_to.window(tabs[i])
            print(f"[{name}] 🔍 Checking tab {i+1}/{len(chunk)}: {driver.current_url}")
            time.sleep(3)

            try:
                WebDriverWait(driver, 5).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                alert_text = alert.text
                print(f"[{name}] 🛑 XSS detected: {driver.current_url} | Alert: {alert_text}")

                with open(alert_file, "a") as af:
                    af.write(driver.current_url + "\n")

                screenshot_name = f"{int(time.time())}_{name}_xss.png"
                with open(screenshot_log_file, "a") as sf:
                    sf.write(f"{driver.current_url} -> {screenshot_name}\n")

                driver.save_screenshot(screenshot_name)
                alert.accept()

            except:
                print(f"[{name}] ✅ No XSS popup on: {driver.current_url}")

        # Close all tabs except first
        for i in range(len(tabs) - 1, 0, -1):
            driver.switch_to.window(tabs[i])
            driver.close()
        driver.switch_to.window(tabs[0])

    driver.quit()

# === Main ===

def main():
    with open(input_file, "r") as f:
        urls = [url.strip() for url in f if url.strip()]

    start_index = read_resume_url_index(urls)
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

    # === Retry failed tabs ===
    if os.path.exists(failed_tabs_file):
        with open(failed_tabs_file, "r") as f:
            failed_urls = list(set([line.strip() for line in f if line.strip()]))

        if failed_urls:
            print(f"\n🔁 Retrying {len(failed_urls)} failed tabs...\n")
            open(failed_tabs_file, "w").close()  # Clear file for new round

            retry_chunks = [failed_urls[i:i + tabs_count] for i in range(0, len(failed_urls), tabs_count)]
            retry_grouped = chunkify(retry_chunks, 1)  # 1 retry thread

            retry_processes = []
            for i, chunk_group in enumerate(retry_grouped):
                p = Process(target=xss_worker, args=(f"Retry-{i+1}", chunk_group, 0))
                p.start()
                retry_processes.append(p)

            for p in retry_processes:
                p.join()

            print("\n✅ Retry round finished.")


if __name__ == "__main__":
    main()
