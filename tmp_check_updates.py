import urllib.request
import json
TOKEN = '8449623611:AAFC4_OvrVeWVrsJcHOXD-N4gD_XpzvXaBc'
url = f'https://api.telegram.org/bot{TOKEN}/getUpdates?limit=20'
with urllib.request.urlopen(url) as resp:
    data = json.load(resp)
print(json.dumps(data, indent=2))
