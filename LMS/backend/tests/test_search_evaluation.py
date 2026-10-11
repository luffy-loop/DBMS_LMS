import os
os.environ["ENVIRONMENT"]="test"
os.environ["RUN_DB_SETUP"]="false"
os.environ["ENABLE_RESOURCE_VECTOR_SEARCH"]="false"

from tests.performance.search_corpus_evaluation import evaluate
from vector_store import _lexical_search

CORPUS={"documents":[
 {"id":"db","title":"Database Indexing","content":"B-tree index improves query lookup performance","type":"resource","course_id":7},
 {"id":"os","title":"Process Synchronization","content":"Mutex semaphore critical section race condition","type":"resource","course_id":8}],
 "queries":[{"query":"B-tree index query lookup","relevant_titles":["Database Indexing"]},
 {"query":"mutex semaphore critical section","relevant_titles":["Process Synchronization"]}]}


def test_labelled_corpus_compares_lexical_and_reports_semantic_model_unavailability(monkeypatch):
    import evaluation_service
    monkeypatch.setattr(evaluation_service,"generate_embedding",lambda text: (_ for _ in ()).throw(RuntimeError("model unavailable")))
    report=evaluate(CORPUS,use_semantic=True)
    assert report["query_count"]==2
    assert report["lexical"]["hit_at_1"]==1.0
    # The evaluator must not silently claim semantic success when the model cannot load.
    assert report["semantic"]["available"] is False


def test_lexical_search_respects_explicit_course_fixture_filter():
    rows=_lexical_search("mutex semaphore", [CORPUS["documents"][1]])
    assert [row["title"] for row in rows]==["Process Synchronization"]


def test_search_scoping_passes_only_authorized_course_ids(monkeypatch):
    import vector_store
    observed = []
    monkeypatch.setattr(vector_store, "_resources", lambda ids: observed.append(ids) or CORPUS["documents"])
    monkeypatch.setattr(vector_store, "_lexical_search", lambda query, rows: [{"title": "scoped"}])
    vector_store.clear_search_cache()
    results, _ = vector_store.search_resources_detailed("unique scoped query", [7])
    assert results == [{"title": "scoped"}]
    assert observed == [(7,)]
    vector_store.clear_search_cache()
