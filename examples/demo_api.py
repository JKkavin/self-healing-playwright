import requests
from healer import self_healing_get

# 1. Fetch a real post from JSONPlaceholder
endpoint = "https://jsonplaceholder.typicode.com/posts/1"
response = requests.get(endpoint)
data = response.json()

print("--- ACTUAL API RESPONSE ---")
print(data)
print("---------------------------\n")

# 2. Simulate the API "changing" its key names
# The real API returns "userId", "id", "title", "body"
# We pretend our old test still uses these names:
simulated_new_response = {
    "user_id": data["userId"],   # API changed userId -> user_id
    "post_id": data["id"],       # API changed id -> post_id
    "post_title": data["title"], # API changed title -> post_title
    "content": data["body"]      # API changed body -> content
}

print("--- SIMULATED NEW RESPONSE SHAPE ---")
print(simulated_new_response)
print("------------------------------------\n")

# 3. Our old test code uses OLD keys - the healer should fix them
print("=== Reading old keys from new response ===\n")

user_id = self_healing_get(simulated_new_response, "userId", endpoint)
print(f"→ userId = {user_id}\n")

post_id = self_healing_get(simulated_new_response, "id", endpoint)
print(f"→ id = {post_id}\n")

title = self_healing_get(simulated_new_response, "title", endpoint)
print(f"→ title = {title}\n")

body = self_healing_get(simulated_new_response, "body", endpoint)
print(f"→ body = {body[:50]}...\n")

print("✅ All keys healed successfully!")