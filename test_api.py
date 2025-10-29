import requests

url = "http://localhost:5000/api/v1/path"
data = {
    "start_user_id": "user_1",
    "target_user_id": "user_5"
}

response = requests.post(url, json=data)
print("Status Code:", response.status_code)
print("Response:", response.json())
