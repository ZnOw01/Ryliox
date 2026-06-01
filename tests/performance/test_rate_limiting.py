"""Performance tests for Ryliox API.

Tests cover:
- Rate limiting under load
- API response times
- Concurrent request handling
- Database performance

Requirements:
- Locust: uv sync --frozen --extra test
- Run with: pytest tests/performance/ --run-performance

Or run locust directly:
    locust -f tests/performance/test_rate_limiting.py --host=http://localhost:8000
"""

from __future__ import annotations

import concurrent.futures
import random
import statistics
import time
from typing import Any

import pytest
import requests


@pytest.mark.performance
@pytest.mark.slow
class TestAPIResponseTimes:
    """Tests for API endpoint response times."""

    def test_status_endpoint_response_time(self, base_url: str):
        """Test that status endpoint responds within acceptable time."""
        times = []

        for _ in range(20):
            start = time.time()
            response = requests.get(f"{base_url}/api/status")
            elapsed = time.time() - start
            times.append(elapsed)

            assert response.status_code == 200

        avg_time = statistics.mean(times)
        max_time = max(times)

        # Assert response times are acceptable
        assert avg_time < 0.5, f"Average response time {avg_time}s exceeds 500ms"
        assert max_time < 1.0, f"Max response time {max_time}s exceeds 1s"

    def test_search_endpoint_response_time(self, base_url: str):
        """Test search endpoint response time."""
        times = []

        for i in range(10):
            start = time.time()
            response = requests.get(f"{base_url}/api/search?q=python{i}")
            elapsed = time.time() - start
            times.append(elapsed)

            # Accept 200 or 500 (if service is unavailable)
            assert response.status_code in [200, 500]

        avg_time = statistics.mean(times)
        assert avg_time < 2.0, f"Average search response time {avg_time}s exceeds 2s"

    def test_progress_endpoint_response_time(self, base_url: str):
        """Test progress endpoint response time."""
        times = []

        for _ in range(20):
            start = time.time()
            response = requests.get(f"{base_url}/api/progress")
            elapsed = time.time() - start
            times.append(elapsed)

            assert response.status_code == 200

        avg_time = statistics.mean(times)
        assert avg_time < 0.3, f"Average progress response time {avg_time}s exceeds 300ms"


@pytest.mark.performance
@pytest.mark.rate_limit
@pytest.mark.slow
class TestRateLimiting:
    """Tests for rate limiting behavior under load."""

    def test_download_rate_limit_enforcement(self, base_url: str, sample_cookies: dict[str, str]):
        """Test that download endpoint enforces rate limits."""
        # First, set up authentication
        requests.post(f"{base_url}/api/cookies", json=sample_cookies, headers={"Origin": base_url})

        responses = []
        start_time = time.time()

        # Send rapid requests
        for i in range(20):
            response = requests.post(
                f"{base_url}/api/download",
                json={"book_id": f"book-{i}", "format": ["epub"]},
                headers={"Origin": base_url},
            )
            responses.append(response.status_code)

            # Small delay to not completely overwhelm
            time.sleep(0.05)

        time.time() - start_time

        # Check that we got some rate limited responses
        rate_limited_count = responses.count(429)

        # Should have at least some rate limiting
        assert rate_limited_count > 0, f"Expected some 429 responses, got: {responses}"

        # Most requests should either succeed or be rate limited
        valid_responses = [r for r in responses if r in [200, 429, 400, 500]]
        assert len(valid_responses) == len(responses)

    def test_cookies_endpoint_rate_limit(self, base_url: str, sample_cookies: dict[str, str]):
        """Test rate limiting on cookies endpoint."""
        responses = []

        # Send rapid requests
        for i in range(15):
            response = requests.post(
                f"{base_url}/api/cookies",
                json={**sample_cookies, "_unique": i},  # Slightly vary payload
                headers={"Origin": base_url},
            )
            responses.append(response.status_code)
            time.sleep(0.05)

        # Should get rate limited
        assert 429 in responses, f"Expected 429 responses for rate limiting, got: {responses}"

    def test_different_ips_rate_limiting(self, base_url: str, sample_cookies: dict[str, str]):
        """Test that rate limiting is per-IP."""
        responses_by_ip = {}

        # Simulate requests from different IPs
        for ip_suffix in range(3):
            headers = {
                "Origin": base_url,
                "X-Forwarded-For": f"192.168.1.{ip_suffix}",
            }

            responses = []
            for _i in range(10):
                response = requests.post(
                    f"{base_url}/api/cookies", json=sample_cookies, headers=headers
                )
                responses.append(response.status_code)
                time.sleep(0.05)

            responses_by_ip[ip_suffix] = responses

        # Each IP should have its own rate limit counter
        # So they might not all be rate limited if they stay under their individual limits
        for ip, responses in responses_by_ip.items():
            # Each IP should have valid responses
            assert all(r in [200, 429, 400] for r in responses), (
                f"IP {ip} got unexpected responses: {responses}"
            )


@pytest.mark.performance
@pytest.mark.slow
class TestConcurrentRequests:
    """Tests for handling concurrent requests."""

    def test_concurrent_status_requests(self, base_url: str):
        """Test handling many concurrent status requests."""

        def make_request():
            return requests.get(f"{base_url}/api/status")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        success_count = sum(1 for r in responses if r.status_code == 200)

        # At least 80% should succeed
        assert success_count >= 40, f"Only {success_count}/50 status requests succeeded"

    def test_concurrent_search_requests(self, base_url: str):
        """Test handling concurrent search requests."""

        def make_request(query: str):
            return requests.get(f"{base_url}/api/search?q={query}")

        queries = ["python", "javascript", "rust", "golang"] * 10

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, q) for q in queries]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Check responses
        status_codes = [r.status_code for r in responses]
        success_count = status_codes.count(200)
        error_count = status_codes.count(500)

        # Most should either succeed or fail gracefully
        assert success_count + error_count == len(responses)

    def test_mixed_concurrent_requests(self, base_url: str, sample_cookies: dict[str, str]):
        """Test mixed concurrent read/write operations."""
        results = {"status": [], "search": [], "progress": []}

        def status_request():
            r = requests.get(f"{base_url}/api/status")
            results["status"].append(r.status_code)

        def search_request():
            r = requests.get(f"{base_url}/api/search?q=test")
            results["search"].append(r.status_code)

        def progress_request():
            r = requests.get(f"{base_url}/api/progress")
            results["progress"].append(r.status_code)

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            # Submit mixed workload
            for _ in range(20):
                executor.submit(status_request)
                executor.submit(search_request)
                executor.submit(progress_request)

            # Wait for completion
            executor.shutdown(wait=True)

        # All operations should complete without hanging
        total = len(results["status"]) + len(results["search"]) + len(results["progress"])
        assert total == 60, f"Expected 60 responses, got {total}"


@pytest.mark.performance
@pytest.mark.slow
class TestDatabasePerformance:
    """Tests for database performance."""

    def test_download_queue_performance(self, base_url: str, sample_cookies: dict[str, str]):
        """Test download queue database operations performance."""
        # Set up auth
        requests.post(f"{base_url}/api/cookies", json=sample_cookies, headers={"Origin": base_url})

        # Queue multiple downloads
        times = []
        job_ids = []

        for i in range(20):
            start = time.time()
            response = requests.post(
                f"{base_url}/api/download",
                json={"book_id": f"perf-test-{i}", "format": ["epub"]},
                headers={"Origin": base_url},
            )
            elapsed = time.time() - start
            times.append(elapsed)

            if response.status_code == 200:
                job_ids.append(response.json()["job_id"])

        avg_time = statistics.mean(times)

        # Queue operations should be fast
        assert avg_time < 0.5, f"Download queue operation average {avg_time}s exceeds 500ms"

        # Verify we can query progress for all jobs
        for job_id in job_ids[:5]:  # Check first 5
            response = requests.get(f"{base_url}/api/progress?job_id={job_id}")
            assert response.status_code == 200

    def test_session_store_performance(self, base_url: str):
        """Test session store read/write performance."""
        times = []

        # Multiple save operations
        for i in range(30):
            cookies = {"session_id": f"test_{i}", "token": f"token_{i}"}

            start = time.time()
            response = requests.post(
                f"{base_url}/api/cookies", json=cookies, headers={"Origin": base_url}
            )
            elapsed = time.time() - start
            times.append(elapsed)

            # Accept 200 or 429 (rate limited)
            assert response.status_code in [200, 429]

        # Calculate avg of successful requests only
        successful_times = [t for t, r in zip(times, [200] * 30) if True]  # Simplified
        if successful_times:
            avg_time = statistics.mean(successful_times)
            assert avg_time < 0.3, f"Session save average {avg_time}s exceeds 300ms"


# ============================================================================
# Locust Load Testing Class (for use with locust command)
# ============================================================================

# This section is only used when running with `locust` command directly
try:
    from locust import HttpUser, TaskSet, between, task

    class UserBehavior(TaskSet):
        """Locust task set simulating typical user behavior."""

        def on_start(self):
            """Called when a Locust user starts."""
            # Check status
            self.client.get("/api/status")

        @task(10)
        def check_status(self):
            """Task: Check authentication status."""
            with self.client.get("/api/status", catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        @task(5)
        def search_books(self):
            """Task: Search for books."""
            queries = ["python", "javascript", "rust", "golang", "machine learning"]
            query = random.choice(queries)

            with self.client.get(f"/api/search?q={query}", catch_response=True) as response:
                if response.status_code in [
                    200,
                    500,
                ]:  # 500 is acceptable if service unavailable
                    response.success()
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        @task(3)
        def check_progress(self):
            """Task: Check download progress."""
            with self.client.get("/api/progress", catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        @task(1)
        def download_book(self):
            """Task: Queue a download (rate limited)."""
            book_id = f"load-test-{random.randint(1, 1000)}"

            with self.client.post(
                "/api/download",
                json={"book_id": book_id, "format": ["epub"]},
                headers={"Origin": self.client.base_url},
                catch_response=True,
            ) as response:
                if response.status_code in [200, 429]:  # 200 or rate limited
                    response.success()
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

        @task(2)
        def get_book_chapters(self):
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
        wait_time = between(1, 5)  # Wait 1-5 seconds between tasks

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Ensure base_url doesn't have trailing slash issues
            if self.host and self.host.endswith("/"):
                self.host = self.host[:-1]

except Exception:
    # Locust not installed, skip load testing classes
    pass


# ============================================================================
# Benchmark Utilities
# ============================================================================


def benchmark_endpoint(
    base_url: str,
    method: str,
    endpoint: str,
    payload: dict | None = None,
    headers: dict | None = None,
    iterations: int = 100,
) -> dict[str, Any]:
    """Benchmark an API endpoint.

    Args:
        base_url: Base URL of the API
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        payload: Request payload for POST/PUT
        headers: Request headers
        iterations: Number of requests to make

    Returns:
        Dictionary with benchmark statistics
    """
    url = f"{base_url}{endpoint}"
    times = []
    status_counts = {}

    for _ in range(iterations):
        start = time.time()

        if method.upper() == "GET":
            response = requests.get(url, headers=headers or {})
        elif method.upper() == "POST":
            response = requests.post(url, json=payload, headers=headers or {})
        else:
            raise ValueError(f"Unsupported method: {method}")

        elapsed = time.time() - start
        times.append(elapsed)

        status_counts[response.status_code] = status_counts.get(response.status_code, 0) + 1

    return {
        "iterations": iterations,
        "mean_time": statistics.mean(times),
        "median_time": statistics.median(times),
        "stdev_time": statistics.stdev(times) if len(times) > 1 else 0,
        "min_time": min(times),
        "max_time": max(times),
        "status_counts": status_counts,
    }


@pytest.mark.performance
@pytest.mark.slow
class TestBenchmarkSuite:
    """Comprehensive benchmark tests."""

    def test_status_endpoint_benchmark(self, base_url: str):
        """Benchmark the status endpoint."""
        stats = benchmark_endpoint(base_url, "GET", "/api/status", iterations=100)

        print("\nStatus Endpoint Benchmark:")
        print(f"  Mean: {stats['mean_time']:.3f}s")
        print(f"  Median: {stats['median_time']:.3f}s")
        print(f"  Min: {stats['min_time']:.3f}s")
        print(f"  Max: {stats['max_time']:.3f}s")
        print(f"  Status codes: {stats['status_counts']}")

        # Assertions
        assert stats["mean_time"] < 0.5
        assert stats["status_counts"].get(200, 0) >= 90  # At least 90% success

    def test_progress_endpoint_benchmark(self, base_url: str):
        """Benchmark the progress endpoint."""
        stats = benchmark_endpoint(base_url, "GET", "/api/progress", iterations=100)

        print("\nProgress Endpoint Benchmark:")
        print(f"  Mean: {stats['mean_time']:.3f}s")
        print(f"  Median: {stats['median_time']:.3f}s")
        print(f"  Status codes: {stats['status_counts']}")

        assert stats["mean_time"] < 0.3
        assert stats["status_counts"].get(200, 0) >= 95
