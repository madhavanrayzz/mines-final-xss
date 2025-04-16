from urllib.parse import urlparse, parse_qs, urlunparse
import copy

# Load and group payloads (3 lines per payload, joined into one line)
with open("polygots.txt") as f:
    lines = [line.strip() for line in f if line.strip()]
payloads = ["".join(lines[i:i+3]) for i in range(0, len(lines), 3)]

# Load new input format (URL | param)
with open("validated_urls.txt") as f:
    input_lines = [line.strip() for line in f if " | " in line]

constructed_urls = set()

for line in input_lines:
    url_part, param = [x.strip() for x in line.split(" | ", 1)]

    parsed = urlparse(url_part)
    query = parse_qs(parsed.query)

    if param not in query:
        continue

    for payload in payloads:
        new_query = copy.deepcopy(query)
        new_query[param] = [payload]

        query_str = "&".join(f"{k}={v[0]}" for k, v in new_query.items())
        new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query_str, parsed.fragment))

        constructed_urls.add(new_url)

# Save final URLs
with open("constructed_polygots_urls.txt", "w") as f:
    for url in sorted(constructed_urls):
        f.write(url + "\n")

print(f"[+] Injected payloads into provided URLs.")
print(f"[+] Total unique constructed URLs: {len(constructed_urls)}")
print("[+] Output written to constructed_polygots_urls.txt")
