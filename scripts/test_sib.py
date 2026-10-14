import urllib.request
import ssl
import sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.southindianbank.com/",
}

url = "https://www.southindianbank.com/userfiles/forms/ld%202172.pdf"
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        content = resp.read()
        print("Success! Downloaded", len(content), "bytes")
        with open("data/real_docs/south_indian_bank_ld2172.pdf", "wb") as f:
            f.write(content)
except Exception as e:
    print("Error:", e)
