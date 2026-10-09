from ai_jobs import _generate_grounded_questions


def test_quiz_questions_are_grounded_and_correct_answer_is_an_option():
    source = {"title": "Database Normalization", "content": "Database normalization organizes relational tables to reduce redundant data and improve data integrity. It uses normal forms to guide schema design."}
    questions = _generate_grounded_questions([source], 5)
    assert questions
    assert all(q["context"] in source["content"] for q in questions)
    assert all(q["answer"] in q["options"] for q in questions)
    assert all(q["source"] == source["title"] for q in questions)
    assert all(all(option in source["content"] for option in q["options"]) for q in questions)


def test_quiz_generation_returns_empty_for_unusable_material():
    assert _generate_grounded_questions([{"title": "Empty", "content": ""}], 5) == []
    assert _generate_grounded_questions([{"title": "One sentence", "content": "This course has only one meaningful statement that cannot provide distractors."}], 5) == []


def test_quiz_job_uses_course_scoped_retrieval_without_embedding_model(monkeypatch):
    import vector_store
    from ai_jobs import _timed_search

    called = {}
    expected = ([{"title": "Course notes", "content": "A grounded statement from the selected course material."}], {"mode": "course_scoped_lexical"})

    def fake_search(query, course_id):
        called["query"] = query
        called["course_id"] = course_id
        return expected

    monkeypatch.setattr(vector_store, "search_resources_for_quiz", fake_search)
    result = _timed_search("course material", 42)
    assert result == expected
    assert called == {"query": "course material", "course_id": 42}
