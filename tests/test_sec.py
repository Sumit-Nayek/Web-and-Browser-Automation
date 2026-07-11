import requests

headers = {
    "User-Agent": "Sumit Nayek Portfolio Project ghostnayek@gmail.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}

print("Pinging SEC EDGAR...")
response = requests.get("https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.20260710.idx", headers=headers)

if response.status_code == 200:
    print("✅ SUCCESS! The SEC has lifted the ban and accepted your headers.")
else:
    print(f"❌ FAILED. Status Code: {response.status_code}. The IP is still banned. Wait 5 more minutes.")