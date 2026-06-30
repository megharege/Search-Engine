import requests

r = requests.post('http://localhost:8000/api/search', json={
    'query': 'vata dosha',
    'books': [],
    'mode': 'Hybrid',
    'limit': 2
})
d = r.json()
print(f"Status: {r.status_code}")
print(f"Hits: {len(d['hits'])}")
for h in d['hits']:
    print(f"  - [{h.get('source_file')}] {h.get('topic_heading')}")
