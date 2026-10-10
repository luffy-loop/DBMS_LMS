from ai_jobs import _generate_grounded_questions


def test_quiz_questions_are_meaningful_and_grounded():
    source = {"title": "Database Notes", "content": (
        "A primary key is a column that uniquely identifies each row in a relational table. "
        "A foreign key is a column that references a key in another table and maintains referential integrity. "
        "Normalization is a process that organizes relational data to reduce redundant values and prevent anomalies. "
        "An index is a data structure that helps locate rows faster for suitable queries in a database."
    )}
    questions = _generate_grounded_questions([source], 5)
    assert len(questions) >= 1
    assert all(q["source"] == source["title"] for q in questions)
    assert all(q["answer"] in q["options"] for q in questions)
    assert all(len(q["options"]) == 4 for q in questions)
    assert all(len({option.casefold() for option in q["options"]}) == 4 for q in questions)
    assert all(q["question"].startswith("Which concept matches this description:") for q in questions)
    assert all(q["answer"].casefold() not in q["question"].casefold() for q in questions)
    assert all(q["answer"].casefold() not in q["context"].casefold() for q in questions)
    assert len({q["question"].casefold() for q in questions}) == len(questions)


def test_quiz_generation_fails_closed_for_insufficient_or_generic_material():
    assert _generate_grounded_questions([{"title": "Empty", "content": ""}], 5) == []
    assert _generate_grounded_questions([{"title": "Generic", "content": "This course has only one meaningful statement that cannot provide distractors."}], 5) == []
    assert _generate_grounded_questions([{"title": "Template-like", "content": (
        "Students should read the material carefully before the examination. "
        "The lecture discusses several topics from the selected course. "
        "Assignments should be submitted before the deadline."
    )}], 5) == []


def test_quiz_generation_deduplicates_questions_and_options():
    source = {"title": "Notes", "content": (
        "A process is a program in execution managed by the operating system. "
        "A thread is an execution path within a process that shares process memory. "
        "A deadlock is a state where processes wait indefinitely for unavailable resources. "
        "A mutex is a synchronization mechanism that protects a shared critical section."
    )}
    questions = _generate_grounded_questions([source, source], 10)
    assert len({q["question"].casefold() for q in questions}) == len(questions)
    assert all(q["answer"] in q["options"] for q in questions)
    assert all(len(q["options"]) == 4 for q in questions)


def test_quiz_generation_supports_explanatory_sentences_without_is_definitions():
    source = {
        "title": "Operating Systems Notes",
        "content": (
            "Mutex locks protect a critical section by allowing only one thread to access shared data at a time. "
            "Semaphores use a counter to coordinate access to shared resources and signal waiting processes. "
            "A deadlock occurs when processes wait indefinitely for resources held by one another. "
            "Context switching saves one process state and loads another so the CPU can resume execution."
        ),
    }
    questions = _generate_grounded_questions([source], 4)
    assert len(questions) >= 1
    assert all(q["source"] == source["title"] for q in questions)
    assert all(q["answer"] in q["options"] for q in questions)
    assert all(len(q["options"]) == 4 for q in questions)
    assert all(len({option.casefold() for option in q["options"]}) == 4 for q in questions)
