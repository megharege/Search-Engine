# Note: This script requires the 'requests' library, which is included in the project's requirements.txt
import requests
headers = {"Authorization": "Bearer ayurveda-dev-key"}
r = requests.patch("http://localhost:7700/experimental-features", json={"vectorStore": True}, headers=headers)
print(r.json())
