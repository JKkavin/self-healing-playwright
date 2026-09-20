from api_healer import self_healing_get

endpoint = "https://api.example.com/v1/user/123"

# Simulated NEW live API response (keys changed from the old version)
live_response = {
    "id": 123,
    "name": "alice",
    "auth_token": "eyJhbGciOi...",
    "created_at": "2026-09-20T10:00:00Z"
}

print("\n=== Reading old keys from new API response ===\n")

user_id = self_healing_get(live_response, "user_id", endpoint)
print(f"→ user_id = {user_id}\n")

user_name = self_healing_get(live_response, "user_name", endpoint)
print(f"→ user_name = {user_name}\n")

token = self_healing_get(live_response, "token", endpoint)
print(f"→ token = {token}\n")

print("✅ All keys healed successfully!")