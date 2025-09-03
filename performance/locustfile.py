"""
Locust load test for the mock posts API.

Run this script with ``locust -f performance/locustfile.py`` and open
http://localhost:8089 in your browser.  Enter the target host (e.g.
http://localhost:5000) and start the test to generate load against the mock API.
"""

from locust import HttpUser, task, between


class PostsUser(HttpUser):
    # Wait time between tasks to simulate user think time
    wait_time = between(1, 2)

    @task
    def list_posts(self) -> None:
        """Task that fetches all posts from the API."""
        self.client.get("/posts")

    @task
    def get_first_post(self) -> None:
        """Task that fetches the first post."""
        self.client.get("/posts/1")
