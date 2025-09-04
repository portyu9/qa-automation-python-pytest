import requests
import os


BASE_URL = os.getenv("API_BASE_URL", "https://jsonplaceholder.typicode.com")

def fetch_posts() -> list:
    """
    Fetch posts from the public JSONPlaceholder service and return the JSON data.
    I use this helper in my API tests to validate status codes and response structures.
    """
    response = requests.get(f"{BASE_URL}/posts")
    response.raise_for_status()
    return response.json()
