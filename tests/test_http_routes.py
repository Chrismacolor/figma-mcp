class TestAuth:
    def test_valid_token(self, client, auth_headers):
        resp = client.get("/api/jobs/next", headers=auth_headers)
        assert resp.status_code == 204

    def test_invalid_token(self, client):
        resp = client.get("/api/jobs/next", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401

    def test_missing_header(self, client):
        resp = client.get("/api/jobs/next")
        assert resp.status_code == 422


class TestJobsNext:
    def test_empty_returns_204(self, client, auth_headers):
        resp = client.get("/api/jobs/next", headers=auth_headers)
        assert resp.status_code == 204

    def test_returns_pending_job(self, client, auth_headers, queue):
        job = queue.create_job([{"op": "CREATE_FRAME", "tempId": "f1"}])
        resp = client.get("/api/jobs/next", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == job.id
        assert data["ops"] == [{"op": "CREATE_FRAME", "tempId": "f1"}]

    def test_records_poll(self, client, auth_headers, queue):
        assert queue.plugin_connected() is False
        client.get("/api/jobs/next", headers=auth_headers)
        assert queue.plugin_connected() is True

    def test_job_transitions_to_in_progress(self, client, auth_headers, queue):
        from server.job_queue import JobStatus

        job = queue.create_job([])
        client.get("/api/jobs/next", headers=auth_headers)
        assert job.status == JobStatus.IN_PROGRESS


class TestCompleteJob:
    def test_success(self, client, auth_headers, queue):
        job = queue.create_job([])
        queue.next_pending()
        resp = client.post(f"/api/jobs/{job.id}/complete", json={"result": {"ok": True}}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_not_found(self, client, auth_headers):
        resp = client.post("/api/jobs/nonexistent/complete", json={"result": {}}, headers=auth_headers)
        assert resp.status_code == 404

    def test_wrong_status(self, client, auth_headers, queue):
        job = queue.create_job([])
        # Job is PENDING, not IN_PROGRESS
        resp = client.post(f"/api/jobs/{job.id}/complete", json={"result": {}}, headers=auth_headers)
        assert resp.status_code == 404


class TestErrorJob:
    def test_success(self, client, auth_headers, queue):
        job = queue.create_job([])
        queue.next_pending()
        resp = client.post(f"/api/jobs/{job.id}/error", json={"error": "failed"}, headers=auth_headers)
        assert resp.status_code == 200

    def test_not_found(self, client, auth_headers):
        resp = client.post("/api/jobs/nonexistent/error", json={"error": "x"}, headers=auth_headers)
        assert resp.status_code == 404


class TestReadRequest:
    def test_empty_returns_204(self, client, auth_headers, queue):
        resp = client.get("/api/read-request", headers=auth_headers)
        assert resp.status_code == 204

    def test_returns_pending(self, client, auth_headers, queue):
        req = queue.create_read_request(depth=3)
        resp = client.get("/api/read-request", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == req.id
        assert data["depth"] == 3

    def test_submit_response(self, client, auth_headers, queue):
        req = queue.create_read_request()
        resp = client.post(f"/api/read-request/{req.id}/response", json={"data": {"tree": []}}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_submit_response_wrong_id(self, client, auth_headers, queue):
        queue.create_read_request()
        resp = client.post("/api/read-request/wrong/response", json={"data": {}}, headers=auth_headers)
        assert resp.status_code == 404


class TestScreenshotRequest:
    def test_empty_returns_204(self, client, auth_headers, queue):
        resp = client.get("/api/screenshot-request", headers=auth_headers)
        assert resp.status_code == 204

    def test_returns_pending(self, client, auth_headers, queue):
        req = queue.create_screenshot_request(node_id="1:2", scale=2.0)
        resp = client.get("/api/screenshot-request", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == req.id
        assert data["nodeId"] == "1:2"
        assert data["scale"] == 2.0

    def test_submit_response(self, client, auth_headers, queue):
        req = queue.create_screenshot_request()
        resp = client.post(f"/api/screenshot-request/{req.id}/response", json={"base64": "abc="}, headers=auth_headers)
        assert resp.status_code == 200

    def test_submit_error(self, client, auth_headers, queue):
        req = queue.create_screenshot_request()
        resp = client.post(f"/api/screenshot-request/{req.id}/error", json={"error": "render failed"}, headers=auth_headers)
        assert resp.status_code == 200

    def test_submit_error_wrong_id(self, client, auth_headers, queue):
        queue.create_screenshot_request()
        resp = client.post("/api/screenshot-request/wrong/error", json={"error": "x"}, headers=auth_headers)
        assert resp.status_code == 404
