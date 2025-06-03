from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Load payloads
with open("payloads.txt") as f:
    payloads = [line.strip() for line in f if line.strip()]

# Load validated URLs (from the tool's output)
with open("validated_urls.txt") as f:
    validated_lines = [line.strip() for line in f if line.strip()]

constructed_urls = []

for line in validated_lines:
    # Extract URL and parameter from validated URLs
    url, param = line.split(" | ")

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    if param not in query:
        continue  # skip if param not found in query

    for payload in payloads:
        new_query = query.copy()
        new_query[param] = [payload]  # Replace the specific param with payload
        encoded_query = urlencode(new_query, doseq=True)
        new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, encoded_query, parsed.fragment))
        constructed_urls.append(new_url)

# Save to file or print
with open("constructed_urls.txt", "w") as f:
    for u in constructed_urls:
        f.write(u + "\n")

print(f"[+] Generated {len(constructed_urls)} URLs in constructed_urls.txt")
