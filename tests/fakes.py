"""In-memory stand-ins for MongoDB and the coding model, for end-to-end run_task tests."""
import copy

from reflex_harness import agent, config, controller, store


class FakeCollection:
    def __init__(self, docs=()):
        self.docs = [copy.deepcopy(d) for d in docs]

    @staticmethod
    def _match(d, flt):
        for k, v in (flt or {}).items():
            if isinstance(v, dict) and "$in" in v:
                if d.get(k) not in v["$in"]:
                    return False
            elif d.get(k) != v:
                return False
        return True

    def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

    def find(self, flt=None, projection=None):
        return [copy.deepcopy(d) for d in self.docs if self._match(d, flt)]

    def find_one(self, flt=None, projection=None):
        return next(iter(self.find(flt)), None)

    def distinct(self, key, flt=None):
        return list(dict.fromkeys(d[key] for d in self.docs if self._match(d, flt)))


class FakeDB(dict):
    def __missing__(self, name):
        self[name] = FakeCollection()
        return self[name]


def install(monkeypatch, script, *, tokens=(1000, 200), cost=0.001) -> FakeDB:
    """Patch the DB and the model. script[attempt_n - 1] = {path: content} returned by the model;
    every call writes one measured `calls` row, as agent.call does."""
    fake = FakeDB(configs=FakeCollection([{**c, "registry": config.REGISTRY} for c in config.CONFIGS_R1]))
    monkeypatch.setattr(controller, "db", lambda: fake)
    monkeypatch.setattr(store, "db", lambda: fake)

    def scripted(messages, *, run_id, phase, attempt_n, step="patch", **_):
        store.log_call(run_id=run_id, phase=phase, attempt_n=attempt_n, component="agent", model="fake",
                       input_tokens=tokens[0], output_tokens=tokens[1], cost_usd=cost, latency_ms=0)
        files = script[attempt_n - 1]
        return agent.AgentReply(data={"files": [{"path": p, "content": c} for p, c in files.items()], "note": "x"},
                                model="fake", model_reported=None, input_tokens=tokens[0], output_tokens=tokens[1],
                                cost_usd=cost, latency_ms=0, error=None)
    monkeypatch.setattr(agent, "call", scripted)
    return fake
