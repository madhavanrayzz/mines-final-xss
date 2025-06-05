import re
import requests
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from concurrent.futures import ThreadPoolExecutor, as_completed

KXSS_OUTPUT_FILE = "kxss_output.txt"
REFLECTION_MARKER = "text123"
OUTPUT_FILE = "validated_urls.txt"
MAX_THREADS = 10  # Set the number of threads you want to use

def extract_param_url(line):
    """
    Extracts parameter and URL from a line of KXSS output.
    Supports:
    - Format 1: param XYZ is reflected ... on http://...
    - Format 2: URL: ... Param: XYZ Unfiltered: ...
    """
    # Format 1
    match1 = re.search(r"param (\w+) is reflected.* on (http[s]?://\S+)", line)
    if match1:
        return match1.groups()

    # Format 2
    match2 = re.search(r"URL:\s*(http[s]?://\S+)\s+Param:\s*(\w+)", line)
    if match2:
        url, param = match2.groups()
        return param, url

    return None, None

def encode_marker_for_url(marker):
    """Encodes the marker to be URL-safe."""
    return quote(marker)

def replace_param_value(url, param, new_value):
    """Replaces the given parameter value in the URL with the new_value."""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    if param in query_params:
        param_value = query_params[param][0]
        if not param_value:
            # If param value is empty, insert marker as full URL-encoded link
            encoded_value = encode_marker_for_url(f"https://example.com/{new_value}")
            query_params[param] = [encoded_value]
        else:
            # Otherwise, replace value with plain marker
            query_params[param] = [new_value]

        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse(parsed._replace(query=new_query))
        return new_url

    return None

def is_reflected(response_text, marker):
    """Checks if the marker is reflected in the response body."""
    return marker in response_text

def validate_url(param, url):
    """Checks if the URL reflects the marker when the param is replaced."""
    test_url = replace_param_value(url, param, REFLECTION_MARKER)
    if not test_url:
        return None

    try:
        r = requests.get(test_url, timeout=30)
        if is_reflected(r.text, REFLECTION_MARKER):
            print(f"[✅] Reflected: {param} on {test_url}")
            return f"{test_url} | {param}"
        else:
            print(f"[❌] Not reflected: {param} on {test_url}")
    except Exception as e:
        print(f"[⚠️] Request failed: {test_url} | {e}")
    return None

def main():
    # Read input file lines
    with open(KXSS_OUTPUT_FILE, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    # Extract param-url pairs
    param_url_pairs = [extract_param_url(line) for line in lines]
    param_url_pairs = [pair for pair in param_url_pairs if pair[0] and pair[1]]

    with open(OUTPUT_FILE, "w") as out:
        # ThreadPoolExecutor for concurrent requests
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            future_to_url = {executor.submit(validate_url, param, url): (param, url) for param, url in param_url_pairs}

            for future in as_completed(future_to_url):
                result = future.result()
                if result:
                    out.write(result + "\n")

if __name__ == "__main__":
    main()
