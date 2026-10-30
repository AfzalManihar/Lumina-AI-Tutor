import pytest

from tests.conftest import register
from tests.fakes import FakeLLM, smart_responder
from tests.pdfs import PHOTO_PAGES, make_pdf


@pytest.fixture
def llm():
    return FakeLLM(smart_responder)


async def test_lesson_generation_and_retrieval(client):
    await register(client)
    r = await client.post("/api/v1/lessons", json={"topic": "Binary search", "difficulty": "intermediate"})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["difficulty"] == "intermediate" and b["lesson"]["topic"] == "Binary search" and not b["grounded"]
    got = await client.get(f"/api/v1/lessons/{b['id']}")
    assert got.status_code == 200 and got.json()["lesson"]["title"].startswith("Intro")
    assert (await client.get("/api/v1/lessons")).json()["total"] == 1


async def test_lesson_difficulty_mismatch_is_repaired(client, llm):
    await register(client)
    good = {"title": "Lesson X", "topic": "Graphs", "difficulty": "advanced", "objectives": ["o"],
            "sections": [{"heading": "h", "content": "some long enough content here"}],
            "key_takeaways": ["k"], "practice_questions": [], "citations": []}
    llm.push({**good, "difficulty": "beginner"}, good)  # first attempt violates the requested difficulty
    r = await client.post("/api/v1/lessons", json={"topic": "Graphs", "difficulty": "advanced"})
    assert r.status_code == 201 and r.json()["lesson"]["difficulty"] == "advanced" and len(llm.calls) == 2


async def test_invalid_model_json_exhausts_bounded_repairs(client, llm):
    await register(client)
    llm.push("not json", "still not json", "nope")
    r = await client.post("/api/v1/lessons", json={"topic": "Graphs", "difficulty": "advanced"})
    assert r.status_code == 502 and len(llm.calls) == 3  # initial + max_retries(2) repairs, then stop
    assert (await client.get("/api/v1/lessons")).json()["total"] == 0


async def test_quiz_flow_hides_key_until_attempt_and_grades_server_side(client):
    await register(client)
    q = (await client.post("/api/v1/quizzes", json={"topic": "Python lists", "num_questions": 4})).json()
    assert len(q["questions"]) == 4 and all("correct_index" not in x for x in q["questions"])
    bad = await client.post(f"/api/v1/quizzes/{q['id']}/submit", json={"answers": [0, 1]})
    assert bad.status_code == 422
    res = (await client.post(f"/api/v1/quizzes/{q['id']}/submit", json={"answers": [0, 1, 2, 3]})).json()
    assert res["score"] == 4 and res["percent"] == 100.0  # fake key is i % 4
    res2 = (await client.post(f"/api/v1/quizzes/{q['id']}/submit", json={"answers": [3, 3, 3, 3]})).json()
    assert res2["score"] == 1
    again = (await client.get(f"/api/v1/quizzes/{q['id']}")).json()
    assert "correct_index" in again["questions"][0] and again["attempts"] == 2
    p = (await client.get("/api/v1/progress")).json()
    assert p["quizzes_taken"] == 2 and p["average_quiz_percent"] == 62.5


async def test_quiz_question_count_enforced(client, llm):
    await register(client)
    one = {"topic": "T", "difficulty": "beginner", "questions": [
        {"prompt": "What is one?", "options": ["a", "b", "c", "d"], "correct_index": 0, "explanation": "because", "cite_ids": []}]}
    llm.push(one, one, one)
    r = await client.post("/api/v1/quizzes", json={"topic": "Arithmetic", "num_questions": 3})
    assert r.status_code == 502


async def test_grounded_quiz_cites_real_sources_and_requires_evidence(client):
    await register(client)
    doc = (await client.post("/api/v1/documents", files={"file": ("b.pdf", make_pdf(PHOTO_PAGES), "application/pdf")})).json()
    q = await client.post("/api/v1/quizzes", json={"topic": "chloroplast light", "num_questions": 2, "document_ids": [doc["id"]]})
    assert q.status_code == 201 and q.json()["grounded"] and q.json()["questions"][0]["cite_ids"]
    none = await client.post("/api/v1/quizzes", json={"topic": "medieval sword forging", "document_ids": [doc["id"]]})
    assert none.status_code == 422 and none.json()["error"]["code"] == "insufficient_evidence"


async def test_free_text_evaluation(client):
    await register(client)
    r = await client.post("/api/v1/assessments/evaluate", json={"question": "What is gravity?", "answer": "A force that attracts masses"})
    assert r.status_code == 200 and r.json()["verdict"] == "correct"
    empty = await client.post("/api/v1/assessments/evaluate", json={"question": "What is gravity?", "answer": ""})
    assert empty.json()["verdict"] == "incorrect" and empty.json()["score"] == 0


async def test_learning_data_isolated_between_users(make_client):
    a, b = await make_client(), await make_client()
    await register(a)
    await register(b)
    q = (await a.post("/api/v1/quizzes", json={"topic": "Secrets of A", "num_questions": 2})).json()
    les = (await a.post("/api/v1/lessons", json={"topic": "Secrets of A"})).json()
    for path in (f"/api/v1/quizzes/{q['id']}", f"/api/v1/lessons/{les['id']}"):
        assert (await b.get(path)).status_code == 404
    assert (await b.post(f"/api/v1/quizzes/{q['id']}/submit", json={"answers": [0, 0]})).status_code == 404
    assert (await b.get("/api/v1/progress")).json()["quizzes_taken"] == 0
    assert (await b.get("/api/v1/quizzes")).json()["total"] == 0


async def test_dashboard_reflects_real_data_and_starts_empty(client):
    await register(client)
    d = (await client.get("/api/v1/dashboard")).json()
    assert d["documents"]["total"] == 0 and d["progress"]["quizzes_taken"] == 0
    assert d["subscription"]["plan_id"] == "free" and d["usage"]["tokens_used"] == 0 and d["recent_conversations"] == []
    q = (await client.post("/api/v1/quizzes", json={"topic": "Sets", "num_questions": 2})).json()
    await client.post(f"/api/v1/quizzes/{q['id']}/submit", json={"answers": [0, 1]})
    await client.post("/api/v1/tutor/chat", json={"message": "Explain what a set is in maths"})
    d = (await client.get("/api/v1/dashboard")).json()
    assert d["recent_quiz_results"][0]["percent"] == 100.0 and d["usage"]["tokens_used"] > 0
    assert len(d["recent_conversations"]) == 1


async def test_unauthenticated_learning_endpoints(client):
    for m, p in [("get", "/api/v1/lessons"), ("get", "/api/v1/quizzes"), ("get", "/api/v1/progress"),
                 ("get", "/api/v1/dashboard"), ("post", "/api/v1/tutor/chat"), ("get", "/api/v1/tutor/conversations"),
                 ("get", "/api/v1/usage"), ("get", "/api/v1/admin/diagnostics")]:
        assert (await getattr(client, m)(p)).status_code == 401, p


async def test_admin_authorization(client, db, make_client):
    await register(client)
    r = await client.get("/api/v1/admin/diagnostics")
    assert r.status_code == 403
    await db.users.update_one({"email": (await client.get("/api/v1/users/me")).json()["email"]}, {"$set": {"role": "admin"}})
    d = await client.get("/api/v1/admin/diagnostics")
    assert d.status_code == 200
    body = d.json()
    assert body["integrations"]["groq"]["model"] == "openai/gpt-oss-120b" and body["integrations"]["groq"]["live_verified"] is False
    assert "gsk_test" not in d.text and "rzp_test_secret" not in d.text  # no secret values
    assert {t["name"] for t in body["tools"]} >= {"search_documents", "calculate", "save_preference"}
    assert (await client.get("/api/v1/admin/users")).status_code == 200
    assert (await client.get("/api/v1/admin/audit")).status_code == 200


async def test_role_cannot_be_self_escalated(client):
    await register(client)
    r = await client.patch("/api/v1/users/me", json={"role": "admin"})
    assert r.status_code == 422
    assert (await client.get("/api/v1/admin/users")).status_code == 403
