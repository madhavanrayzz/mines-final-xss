#!/bin/bash
echo -e "\n\033[1;32m"
echo "  __  __           __   ____  _____ _____  "
echo " |  \/  |  /\     / /  |  _ \| ____|_   _|"
echo " | \  / | /  \   / /   | |_) |  _|   | |  "
echo " | |\/| |/ /\ \ / /    |  __/| |___  | |  "
echo " |_|  |_/_/  \_\_/     |_|   |_____| |_|  "
echo ""
echo -e "         \033[0;31m🔥 Powered by: \033[1;35mMaddy   \033[0m"
echo ""
echo -e "\033[0mStarting XSS Enumeration Chain...\n"

# === XSS POWERCHAIN SCRIPT ===
set -e

# Prompt user to input the target URL
echo -e "\n🚀 Please provide the target URL (e.g., https://example.com):"
read -p "Target URL: " TARGET_URL

# Check if the user provided a URL
if [ -z "$TARGET_URL" ]; then
    echo "❌ Error: No target URL provided. Exiting..."
    exit 1
fi

echo -e "\n🚀 Starting XSS Enumeration Chain for $TARGET_URL...\n"

# Step 1: Katana crawling
echo "[1/7] 🕷 Running katana scan on $TARGET_URL..."
katana -u "$TARGET_URL" -d 5 waybackarchive,commoncrawl,alienvault -kf -jc -fx -ef woff,css,png,svg,jpg,woff2,jpeg,gif,svg -o allurls.txt

# Step 2: Filter possible XSS params with kxss
echo "[2/7] 💉 Filtering with kxss..."
cat allurls.txt | kxss > kxss_output.txt

# Step 3: Validate with custom Python request sender
echo "[3/7] 📬 Sending requests via Request_sender_response.py..."
python3 Request_sender_response.py

# Step 4: Copy validated URLs to each working directory
echo "[4/7] 📂 Copying validated_urls.txt to payload directories..."
cp validated_urls.txt xss_classic/
cp validated_urls.txt xss_poly/

# Step 5: Run classic payload constructor
echo "[5/7] 🏗 Running classic payload constructor..."
cd xss_classic
python3 new_constructed_tool.py

# Step 6: Deduplicate constructed URLs
echo "[6/7] 🧹 Sorting & deduping constructed URLs..."
sort -u constructed_urls.txt -o constructed_urls.txt
rm -f resume.log

# Step 7: Launch final parallel-tab XSS detector
echo "[7/9] ⚔️ Launching tabbed-parallel XSS runner..."
python3 xss_parrell_tab_final.py
echo -e "\n✅ XSS Chain Completed!"
echo "[8/9] ⚔️ Entering pologot tabbed-parallel XSS runner..."
cd ../
cd xss_poly
python3 new_constructed_tooll.py

# Step 6: Deduplicate constructed URLs
echo "[8/9] 🧹 Sorting & deduping constructed URLs..."
sort -u constructed_polygots_urls.txt -o constructed_polygots_urls.txt
rm -f resume.log

# Step 7: Launch final parallel-tab XSS detector
echo "[9/9] ⚔️ Launching tabbed-parallel XSS runner..."
python3 poly_xss_detector_final.py


echo -e "\n✅ XSS Chain Completed!"
