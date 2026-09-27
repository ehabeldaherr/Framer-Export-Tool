import requests
import json
import time

BASE = "http://127.0.0.1:5000"

print("1. Testing GET / (Main App Page)")
r = requests.get(BASE + "/")
assert r.status_code == 200
print("   Status 200 OK")

print("\n2. Testing POST /api/export")
payload = {
    "url": "https://framer.com",
    "rewrite_links": True,
    "strip_telemetry": True,
    "hide_badge": True,
    "max_pages": 2
}
r = requests.post(BASE + "/api/export", json=payload)
assert r.status_code == 200
data = r.json()
export_id = data.get("export_id")
print(f"   Export started! ID: {export_id}")

print("\n3. Polling /api/status until complete...")
for _ in range(30):
    r = requests.get(f"{BASE}/api/status/{export_id}")
    st = r.json()
    print(f"   Status: {st.get('status')}, Pages: {st.get('total_pages')}")
    if st.get("status") == "completed":
        break
    time.sleep(1)

print("\n4. Testing /api/tree/<export_id>")
r = requests.get(f"{BASE}/api/tree/{export_id}")
assert r.status_code == 200
tree = r.json().get("tree", [])
print(f"   Generated tree items ({len(tree)}):")
for item in tree:
    print(f"   - {item['path']} ({item['size']} bytes)")

print("\n5. Testing /api/file/<export_id>")
if tree:
    first_path = tree[0]["path"]
    r = requests.get(f"{BASE}/api/file/{export_id}", params={"path": first_path})
    assert r.status_code == 200
    file_data = r.json()
    print(f"   Fetched file '{first_path}' content length: {len(file_data.get('content', ''))} chars")

print("\n6. Testing /api/download/<export_id>")
r = requests.get(f"{BASE}/api/download/{export_id}")
assert r.status_code == 200
print(f"   Downloaded ZIP file successfully! Size: {len(r.content)} bytes")

print("\n✨ ALL API & ENGINE TESTS PASSED PERFECTLY!")
