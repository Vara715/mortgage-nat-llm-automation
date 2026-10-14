import urllib.request
import ssl
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
os.makedirs("data/real_docs", exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 1. Download RBI Notification 7256 on Prepayment penalty
url_prepayment = "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=7256&Mode=0"
try:
    req = urllib.request.Request(url_prepayment, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        # Extract main content
        content_table = soup.find('table', {'class': 'tablebg'}) or soup.find('div', {'id': 'content'}) or soup
        text = content_table.get_text(separator="\n", strip=True)
        with open("data/real_docs/rbi_prepayment_circular_text.txt", "w", encoding="utf-8") as f:
            f.write(text)
        print("Successfully extracted RBI Prepayment circular text (bytes:", len(text), ")")
except Exception as e:
    print("Error fetching RBI Prepayment circular:", e)
