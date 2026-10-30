"""The .env.example must list exactly the variables the code reads, with no real secrets."""
import re
from pathlib import Path

from app.core.config import Settings

ENV = Path(__file__).resolve().parents[2] / ".env.example"


def test_env_example_matches_settings_fields():
    declared = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", ENV.read_text(), re.M))
    fields = {n.upper() for n in Settings.model_fields}
    assert declared == fields, (declared ^ fields)


def test_env_example_has_no_secrets():
    values = dict(re.findall(r"^([A-Z][A-Z0-9_]+)=([^\s#]*)", ENV.read_text(), re.M))
    for k in ("GROQ_API_KEY", "GOOGLE_API_KEY", "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET",
              "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "EMBEDDING_PROVIDER", "VECTOR_STORE_PROVIDER"):
        assert values[k] == "", k
    assert values["APP_SECRET_KEY"] == "replace_with_a_random_secret" and values["GROQ_MODEL"] == "openai/gpt-oss-120b"


def test_env_example_loads_cleanly():
    import os
    old = dict(os.environ)
    try:
        for k, v in re.findall(r"^([A-Z][A-Z0-9_]+)=([^\s#]*)", ENV.read_text(), re.M):
            os.environ[k] = v
        s = Settings(_env_file=None)
        assert s.app_env == "development" and s.rag_top_k == 5 and s.user_monthly_token_limit == 250000
    finally:
        os.environ.clear()
        os.environ.update(old)
