from fastapi.testclient import TestClient

from app.main import app
from app.core import llm_factory


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    def __init__(self):
        self.invoked = False

    def invoke(self, _messages):
        self.invoked = True
        return _FakeResponse(
            """
            {
              "purchase": {"option":"退货","remark":"测试","evidence":["llm"]},
              "planning": {"option":"特采","remark":"测试","evidence":["llm"]},
              "production": {"option":"加工/选用","remark":"测试","evidence":["llm"]},
              "engineering": {"option":"特采","remark":"测试","evidence":["llm"]},
              "quality": {"option":"退货","remark":"测试","evidence":["llm"]}
            }
            """
        )


def test_exception_suggestion_ok(monkeypatch):
    # mock 掉 LLM，避免真实网络调用
    fake_llm = _FakeLLM()
    monkeypatch.setattr(llm_factory.LLMFactory, "get_instance", lambda *args, **kwargs: fake_llm)

    client = TestClient(app)
    resp = client.post("/ai/exception_suggestion", json={"orderNo": "TEST-001"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["purchase"]["option"] == "退货"
    assert data["planning"]["option"] == "特采"
    assert fake_llm.invoked is True
