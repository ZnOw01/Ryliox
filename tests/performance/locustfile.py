"""Locust load testing file for Ryliox API.

Run directly via CLI:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000
"""

from __future__ import annotations

import random

from locust import HttpUser, TaskSet, between, task


class UserBehavior(TaskSet):
    """Locust task set simulating typical user behavior."""

    def on_start(self) -> None:
        """Called when a Locust user starts."""
        self.client.get("/api/status")

    @task(10)
    def check_status(self) -> None:
        """Task: Check authentication status."""
        with self.client.get("/api/status", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(5)
    def search_books(self) -> None:
        """Task: Search for books."""
        queries = ["python", "javascript", "rust", "golang", "machine learning"]
        query = random.choice(queries)

        with self.client.get(f"/api/search?q={query}", catch_response=True) as response:
            if response.status_code in [200, 500]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def check_progress(self) -> None:
        """Task: Check download progress."""
        with self.client.get("/api/progress", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def download_book(self) -> None:
        """Task: Queue a download (rate limited)."""
        book_id = f"load-test-{random.randint(1, 1000)}"

        with self.client.post(
            "/api/download",
            json={"book_id": book_id, "format": ["epub"]},
            headers={"Origin": self.client.base_url},
            catch_response=True,
        ) as response:
            if response.status_code in [200, 429]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def get_book_chapters(self) -> None:
        """Task: Get book chapters."""
        book_ids = ["9780134685991", "9781491946008", "9780135404675"]
        book_id = random.choice(book_ids)

        with self.client.get(f"/api/book/{book_id}/chapters", catch_response=True) as response:
            if response.status_code in [200, 400, 404, 500]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class WebsiteUser(HttpUser):
    """Main Locust user class."""

    tasks = [UserBehavior]
    wait_time = between(1, 5)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.host and self.host.endswith("/"):
            self.host = self.host[:-1]
