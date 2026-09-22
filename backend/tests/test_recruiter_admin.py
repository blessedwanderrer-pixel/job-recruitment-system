from conftest import auth, create_open_job, make_candidate, make_recruiter, upload_and_apply


def test_admin_can_list_and_create_recruiters(ctx):
    client, service, admin = ctx["client"], ctx["service"], ctx["admin"]
    listed = client.get("/api/admin/recruiters", headers=auth(admin["id"]))
    assert listed.status_code == 200
    assert listed.json() == []

    created = client.post(
        "/api/admin/recruiters",
        headers=auth(admin["id"]),
        json={"full_name": "Recruiter Two", "email": "rec-admin@test.com"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["email"] == "rec-admin@test.com"
    assert body["role"] == "recruiter"
    assert body["is_active"] is True
    assert body["assigned_job_count"] == 0
    profile = service.store.get_profile(body["id"])
    assert profile["role"] == "recruiter"
    invites = [e for e in service.mailer.sent if e["type"] == "recruiter_invite"]
    assert len(invites) == 1
    link = invites[0]["set_password_link"]
    assert link.startswith("https://ats.example.test/set-password?")
    assert "127.0.0.1" not in link
    assert "localhost" not in link
    assert "email=rec-admin%40test.com" in link
    assert "token=" in link

    listed = client.get("/api/admin/recruiters", headers=auth(admin["id"]))
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["full_name"] == "Recruiter Two"
    assert rows[0]["assigned_job_count"] == 0


def test_admin_can_deactivate_recruiter_and_history_stays(ctx):
    client, service, admin = ctx["client"], ctx["service"], ctx["admin"]
    recruiter = make_recruiter(service, "keep-history@test.com")
    candidate = make_candidate(service, "hist-cand@test.com")
    job = create_open_job(client, admin["id"], recruiter["id"], title="Keep History")
    _, applied = upload_and_apply(client, candidate["id"], job["id"])
    app_id = applied.json()["id"]
    rec = auth(recruiter["id"])
    note = client.post(f"/api/applications/{app_id}/notes", headers=rec, json={"body": "Keep this note"})
    assert note.status_code == 200
    advanced = client.post(f"/api/applications/{app_id}/advance", headers=rec)
    assert advanced.status_code == 200

    listed = client.get("/api/admin/recruiters", headers=auth(admin["id"]))
    row = next(r for r in listed.json() if r["id"] == recruiter["id"])
    assert row["assigned_job_count"] == 1
    assert row["is_active"] is True

    deactivated = client.post(
        f"/api/admin/recruiters/{recruiter['id']}/deactivate",
        headers=auth(admin["id"]),
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False
    assert deactivated.json()["assigned_job_count"] == 0

    assert service.store.get_profile(recruiter["id"])["is_active"] is False
    assert service.store.jobs_for_recruiter(recruiter["id"]) == []
    job_now = client.get(f"/api/jobs/{job['id']}", headers=auth(admin["id"]))
    assert job_now.status_code == 200
    assert recruiter["id"] not in job_now.json().get("recruiter_ids", [])

    app_now = client.get(f"/api/applications/{app_id}", headers=auth(admin["id"]))
    assert app_now.status_code == 200
    body = app_now.json()
    assert body["stage"] == "shortlisted"
    assert body["id"] == app_id
    notes = body.get("notes") or []
    assert any(n.get("body") == "Keep this note" for n in notes)
    history = body.get("history") or []
    assert any(h.get("to_stage") == "shortlisted" for h in history)


def test_non_admin_cannot_manage_recruiters(ctx):
    client, service, admin = ctx["client"], ctx["service"], ctx["admin"]
    recruiter = make_recruiter(service)
    candidate = make_candidate(service, "no-admin@test.com")
    payload = {"full_name": "Nope", "email": "nope@test.com"}

    for headers in (auth(recruiter["id"]), auth(candidate["id"])):
        listed = client.get("/api/admin/recruiters", headers=headers)
        assert listed.status_code == 403
        created = client.post("/api/admin/recruiters", headers=headers, json=payload)
        assert created.status_code == 403
        deactivated = client.post(
            f"/api/admin/recruiters/{recruiter['id']}/deactivate",
            headers=headers,
        )
        assert deactivated.status_code == 403
        deleted = client.delete(f"/api/admin/recruiters/{recruiter['id']}", headers=headers)
        assert deleted.status_code == 403

    still = client.get("/api/admin/recruiters", headers=auth(admin["id"]))
    assert still.status_code == 200
    assert any(r["id"] == recruiter["id"] and r["is_active"] for r in still.json())


def test_deactivated_recruiter_cannot_use_recruiter_routes(ctx):
    client, service, admin = ctx["client"], ctx["service"], ctx["admin"]
    recruiter = make_recruiter(service, "gone@test.com")
    candidate = make_candidate(service, "gone-cand@test.com")
    job = create_open_job(client, admin["id"], recruiter["id"])
    _, applied = upload_and_apply(client, candidate["id"], job["id"])
    rec = auth(recruiter["id"])
    assert client.get("/api/jobs", headers=rec).status_code == 200

    assert client.post(f"/api/admin/recruiters/{recruiter['id']}/deactivate", headers=auth(admin["id"])).status_code == 200

    blocked_jobs = client.get("/api/jobs", headers=rec)
    assert blocked_jobs.status_code == 403
    assert "deactivated" in blocked_jobs.json()["detail"].lower()
    blocked_apps = client.get(f"/api/jobs/{job['id']}/applications", headers=rec)
    assert blocked_apps.status_code == 403
    blocked_advance = client.post(f"/api/applications/{applied.json()['id']}/advance", headers=rec)
    assert blocked_advance.status_code == 403
    blocked_login = client.post("/api/auth/login", json={"email": "gone@test.com", "password": "Pass123!"})
    assert blocked_login.status_code == 403


def test_admin_cannot_deactivate_own_account(ctx):
    client, admin = ctx["client"], ctx["admin"]
    res = client.post(f"/api/admin/recruiters/{admin['id']}/deactivate", headers=auth(admin["id"]))
    assert res.status_code in (400, 404)
    me = client.get("/api/me", headers=auth(admin["id"]))
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    login = client.post("/api/auth/login", json={"email": "admin@nowsheradigital.com", "password": "Admin123!"})
    assert login.status_code == 200


def test_admin_can_delete_recruiter_and_reuse_email(ctx):
    client, service, admin = ctx["client"], ctx["service"], ctx["admin"]
    recruiter = make_recruiter(service, "reuse-me@test.com")
    old_id = recruiter["id"]
    candidate = make_candidate(service, "reuse-cand@test.com")
    job = create_open_job(client, admin["id"], recruiter["id"], title="Keep After Delete")
    job_id = job["id"]
    _, applied = upload_and_apply(client, candidate["id"], job_id)
    app_id = applied.json()["id"]
    rec = auth(old_id)
    assert client.post(f"/api/applications/{app_id}/notes", headers=rec, json={"body": "Audit note"}).status_code == 200
    assert client.post(f"/api/applications/{app_id}/advance", headers=rec).status_code == 200
    interview = client.post(
        f"/api/applications/{app_id}/interview",
        headers=rec,
        json={"starts_at": "2030-01-15T10:00:00+00:00", "location": "Nowshera office"},
    )
    assert interview.status_code == 200, interview.text
    cv_id = applied.json()["cv"]["id"]

    deleted = client.delete(f"/api/admin/recruiters/{old_id}", headers=auth(admin["id"]))
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert deleted.json()["email"] == "reuse-me@test.com"

    listed = client.get("/api/admin/recruiters", headers=auth(admin["id"]))
    assert all(row["id"] != old_id for row in listed.json())
    assert service.store.get_profile(old_id) is None
    assert service.store.get_profile_by_email("reuse-me@test.com") is None

    blocked_login = client.post("/api/auth/login", json={"email": "reuse-me@test.com", "password": "Pass123!"})
    assert blocked_login.status_code == 401

    job_now = client.get(f"/api/jobs/{job_id}", headers=auth(admin["id"]))
    assert job_now.status_code == 200
    assert job_now.json()["id"] == job_id
    assert old_id not in job_now.json().get("recruiter_ids", [])

    app_now = client.get(f"/api/applications/{app_id}", headers=auth(admin["id"]))
    assert app_now.status_code == 200
    body = app_now.json()
    assert body["stage"] == "interview"
    assert body["cv"]["id"] == cv_id
    assert any(n.get("body") == "Audit note" for n in (body.get("notes") or []))
    assert body.get("interview")
    assert any(h.get("to_stage") == "shortlisted" for h in (body.get("history") or []))

    created = client.post(
        "/api/admin/recruiters",
        headers=auth(admin["id"]),
        json={"full_name": "Recruiter Reborn", "email": "reuse-me@test.com"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["email"] == "reuse-me@test.com"
    assert created.json()["id"] != old_id
    assert created.json()["role"] == "recruiter"


def test_admin_cannot_delete_own_account(ctx):
    client, admin = ctx["client"], ctx["admin"]
    res = client.delete(f"/api/admin/recruiters/{admin['id']}", headers=auth(admin["id"]))
    assert res.status_code == 400
    assert "cannot delete your own admin account" in res.json()["detail"].lower()
    me = client.get("/api/me", headers=auth(admin["id"]))
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_delete_missing_or_already_deleted_recruiter(ctx):
    client, service, admin = ctx["client"], ctx["service"], ctx["admin"]
    missing = client.delete("/api/admin/recruiters/00000000-0000-0000-0000-000000000000", headers=auth(admin["id"]))
    assert missing.status_code == 404
    recruiter = make_recruiter(service, "once-only@test.com")
    first = client.delete(f"/api/admin/recruiters/{recruiter['id']}", headers=auth(admin["id"]))
    assert first.status_code == 200
    second = client.delete(f"/api/admin/recruiters/{recruiter['id']}", headers=auth(admin["id"]))
    assert second.status_code == 404
