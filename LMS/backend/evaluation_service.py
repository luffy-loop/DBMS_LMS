import math
import re
import hashlib
import logging
import threading
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

# Dimension 384 to match all-MiniLM-L6-v2
VECTOR_DIMENSION = 384
logger = logging.getLogger(__name__)
_embedding_lock = threading.Lock()
_nli_lock = threading.Lock()


def _normalize_vector(vec: list[float]) -> list[float]:
    """L2 normalizes a vector to unit length."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm < 1e-9:
        return [0.0] * len(vec)
    return [round(x / norm, 6) for x in vec]


_embedding_fn = None


def _load_embedding_model():
    """
    Returns the real all-MiniLM-L6-v2 semantic embedding model.
    Tries SentenceTransformers first, then ChromaDB's ONNX all-MiniLM-L6-v2 transformer.
    Raises RuntimeError if neither is available so unreliable fake marks are never awarded.
    """
    global _embedding_fn
    if _embedding_fn is not None:
        return _embedding_fn

    # 1. Try sentence-transformers if installed
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        _embedding_fn = ("sentence_transformers", model)
        return _embedding_fn
    except Exception:
        pass

    # 2. Try ChromaDB's ONNX all-MiniLM-L6-v2 transformer
    try:
        import chromadb.utils.embedding_functions as ef
        model = ef.DefaultEmbeddingFunction()
        _embedding_fn = ("chroma_onnx", model)
        return _embedding_fn
    except Exception as e:
        raise RuntimeError(f"Semantic embedding model 'all-MiniLM-L6-v2' is unavailable: {e}")


def get_embedding_model():
    global _embedding_fn
    if _embedding_fn is not None:
        return _embedding_fn
    with _embedding_lock:
        if _embedding_fn is None:
            return _load_embedding_model()
        return _embedding_fn


def generate_embedding(text_content: str) -> list[float]:
    """
    Generates a 384-dimensional dense semantic embedding using the real
    all-MiniLM-L6-v2 model.
    Both teacher reference answers and student answers use this exact function,
    ensuring strictly identical representation, dimension, and normalization.
    Raises RuntimeError if the embedding model is unavailable.
    """
    clean_text = (text_content or "").strip()
    if not clean_text:
        return [0.0] * VECTOR_DIMENSION

    model_type, model = get_embedding_model()
    if model_type == "sentence_transformers":
        raw = model.encode(clean_text).tolist()
    elif model_type == "chroma_onnx":
        vecs = model([clean_text])
        raw = [float(x) for x in vecs[0]]
    else:
        raise RuntimeError("Unknown embedding model backend")
    if len(raw) != VECTOR_DIMENSION:
        raise ValueError(f"Invalid embedding dimension: expected {VECTOR_DIMENSION}, got {len(raw)}")
    if any(not math.isfinite(float(x)) for x in raw):
        raise ValueError("Embedding contains non-finite values")
    normalized = _normalize_vector([float(x) for x in raw])
    if not any(x != 0.0 for x in normalized):
        raise ValueError("Embedding model returned a zero vector")
    return normalized


_nli_model_tuple = None


def _load_nli_model():
    """
    Returns the cached NLI Cross-Encoder model.
    Uses 'cross-encoder/nli-distilroberta-base' loaded via local ONNX Runtime & tokenizers.
    Model files are cached locally in Hugging Face cache.
    Outputs 3 classes:
      0: contradiction
      1: entailment
      2: neutral
    Raises RuntimeError if NLI model files are unavailable.
    """
    global _nli_model_tuple
    if _nli_model_tuple is not None:
        return _nli_model_tuple

    try:
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
        import onnxruntime as ort

        repo_id = "cross-encoder/nli-distilroberta-base"
        try:
            tok_path = hf_hub_download(repo_id, "tokenizer.json", local_files_only=True)
            model_path = hf_hub_download(repo_id, "onnx/model.onnx", local_files_only=True)
        except Exception:
            tok_path = hf_hub_download(repo_id, "tokenizer.json")
            model_path = hf_hub_download(repo_id, "onnx/model.onnx")

        tokenizer = Tokenizer.from_file(tok_path)
        tokenizer.enable_truncation(max_length=256)
        tokenizer.enable_padding(pad_id=1, pad_token="<pad>", length=256)

        so = ort.SessionOptions()
        so.log_severity_level = 3
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        session = ort.InferenceSession(model_path, sess_options=so, providers=["CPUExecutionProvider"])
        _nli_model_tuple = ("onnx_nli", tokenizer, session)
        return _nli_model_tuple
    except Exception as e:
        raise RuntimeError(f"NLI model 'cross-encoder/nli-distilroberta-base' is unavailable: {e}")


def get_nli_model():
    global _nli_model_tuple
    if _nli_model_tuple is not None:
        return _nli_model_tuple
    with _nli_lock:
        if _nli_model_tuple is None:
            return _load_nli_model()
        return _nli_model_tuple


def classify_nli(premise: str, hypothesis: str) -> dict[str, float]:
    """
    Evaluates premise-hypothesis NLI relationship.
    Premise: Teacher reference answer / Rubric criterion
    Hypothesis: Student candidate sentence(s)
    Returns:
      {
        "contradiction": float,  # 0.0 - 1.0
        "entailment": float,     # 0.0 - 1.0
        "neutral": float         # 0.0 - 1.0
      }
    """
    clean_p = (premise or "").strip()[:8000]
    clean_h = (hypothesis or "").strip()[:8000]
    if not clean_p or not clean_h:
        return {"contradiction": 0.0, "entailment": 0.0, "neutral": 1.0}

    try:
        _, tokenizer, session = get_nli_model()
        import numpy as np

        enc = tokenizer.encode(clean_p, clean_h)
        input_ids = np.array([enc.ids], dtype=np.int64)
        attention_mask = np.array([enc.attention_mask], dtype=np.int64)
        feeds = {"input_ids": input_ids, "attention_mask": attention_mask}
        logits = session.run(None, feeds)[0][0]

        # Stable softmax
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)

        return {
            "contradiction": float(round(probs[0], 4)),
            "entailment": float(round(probs[1], 4)),
            "neutral": float(round(probs[2], 4))
        }
    except Exception as e:
        # Graceful fallback: return neutral and indicate fallback error internally
        return {
            "contradiction": 0.0,
            "entailment": 0.0,
            "neutral": 1.0,
            "fallback_error": str(e)
        }


def compute_pgvector_similarity(db: Session, student_vec: list[float], reference_vec: list[float]) -> float:
    """
    Uses PostgreSQL pgvector to calculate cosine similarity between two vectors.
    In pgvector, <=> is cosine distance (1 - cosine_similarity).
    Therefore, cosine_similarity = 1.0 - (v1 <=> v2).
    Includes safe fallback to in-memory cosine similarity if database query fails.
    """
    if not student_vec or not reference_vec:
        return 0.0

    if len(student_vec) != VECTOR_DIMENSION or len(reference_vec) != VECTOR_DIMENSION:
        raise ValueError(
            f"Vector dimension mismatch: expected {VECTOR_DIMENSION}, "
            f"got {len(student_vec)} and {len(reference_vec)}"
        )

    if all(x == 0 for x in student_vec) or all(x == 0 for x in reference_vec):
        return 0.0

    try:
        v1_str = str(student_vec)
        v2_str = str(reference_vec)

        query = text("SELECT 1.0 - (CAST(:v1 AS vector) <=> CAST(:v2 AS vector)) AS similarity")
        sim = db.execute(query, {"v1": v1_str, "v2": v2_str}).scalar()
        if sim is not None and not math.isnan(sim) and not math.isinf(sim):
            return max(0.0, min(1.0, float(sim)))
    except Exception:
        # Graceful fallback to in-memory cosine similarity
        pass

    dot = sum(a * b for a, b in zip(student_vec, reference_vec))
    norm_a = math.sqrt(sum(a * a for a in student_vec))
    norm_b = math.sqrt(sum(b * b for b in reference_vec))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    val = float(dot / (norm_a * norm_b))
    if math.isnan(val) or math.isinf(val):
        return 0.0
    return max(0.0, min(1.0, val))


def calculate_descriptive_marks(similarity: float, max_marks: int, student_answer: str) -> float:
    """
    Deterministic scoring function for descriptive questions:
    1. If student answer is empty, whitespace, or fewer than 2 words -> 0.0 marks.
    2. Cosine similarity thresholding:
       - Similarity < 0.20: Insufficient semantic match -> 0.0 marks.
       - Similarity in [0.20, 0.85]: Linear scaling from 0% to 100% credit.
         ratio = (similarity - 0.20) / (0.85 - 0.20)
       - Similarity >= 0.85: Strong conceptual match -> 100% credit.
    3. Awarded marks = round(ratio * max_marks, 1), bounded in [0.0, max_marks].
    """
    if max_marks <= 0:
        return 0.0

    cleaned = (student_answer or "").strip()
    words = cleaned.split()
    if not cleaned or len(words) < 2:
        return 0.0

    if similarity is None or math.isnan(similarity) or math.isinf(similarity):
        return 0.0

    if similarity < 0.20:
        ratio = 0.0
    elif similarity >= 0.85:
        ratio = 1.0
    else:
        ratio = (similarity - 0.20) / (0.85 - 0.20)

    awarded = round(ratio * float(max_marks), 1)
    return max(0.0, min(float(max_marks), awarded))


OPPOSITE_PAIRS = [
    ("connection-oriented", "connectionless"),
    ("connection oriented", "connectionless"),
    ("reliable", "unreliable"),
    ("reliable", "lossy"),
    ("lossless", "lossy"),
    ("relational", "non-relational"),
    ("relational", "nosql"),
    ("normalized", "unnormalized"),
    ("normalized", "denormalized"),
    ("clustered", "non-clustered"),
    ("clustered", "unclustered"),
    ("synchronous", "asynchronous"),
    ("blocking", "non-blocking"),
    ("mutable", "immutable"),
    ("deterministic", "non-deterministic"),
    ("deterministic", "random"),
    ("atomic", "non-atomic"),
    ("durable", "volatile"),
    ("durable", "non-durable"),
    ("durable", "ephemeral"),
    ("consistent", "inconsistent"),
    ("isolated", "unisolated"),
    ("unique", "duplicate"),
    ("unique", "non-unique"),
    ("ordered", "unordered"),
    ("stateful", "stateless"),
    ("symmetric", "asymmetric"),
    ("valid", "invalid"),
    ("connected", "disconnected"),
    ("primary", "secondary"),
    ("increasing", "decreasing"),
    ("ascending", "descending"),
    ("linear", "exponential"),
    ("logarithmic", "exponential"),
    ("allows", "prevents"),
    ("avoids", "causes"),
    ("reduces", "increases"),
    ("reduce", "increase"),
    ("decreases", "increases"),
    ("decrease", "increase"),
    ("no preemption", "preempted"),
    ("no preemption", "preemption"),
    ("no preemption", "preemptible"),
    ("non-preemptive", "preemptive"),
    ("greater", "smaller"),
    ("greater", "less"),
    ("greater than", "smaller than"),
    ("greater than", "less than"),
    ("maximum", "minimum"),
    ("max", "min"),
    ("more", "less"),
    ("overlap", "strictly one by one"),
    ("overlapping", "sequential"),
    ("o(log n)", "o(n^2)"),
    ("o(log n)", "o(n)"),
    ("o(1)", "o(n)"),
    ("o(1)", "o(n^2)"),
    ("logarithmic", "quadratic"),
    ("logarithmic", "linear"),
]

STOPWORDS: set[str] = {
    "is", "are", "provides", "provide", "operates", "operate", "a", "an", "the",
    "it", "used", "uses", "use", "using", "with", "without", "from", "by", "that",
    "which", "at", "for", "and", "in", "of", "to", "into", "as", "on",
    "enforces", "enforce", "enforcing", "ensures", "ensure", "guarantees", "guarantee"
}

SYNONYMS: dict[str, set[str]] = {
    "dependable": {"reliable", "trustworthy", "dependable"},
    "reliable": {"dependable", "trustworthy", "reliable"},
    "delivery": {"transfer", "transmission", "delivering", "delivery"},
    "transmission": {"transfer", "delivery", "transmission"},
    "loss-free": {"lossless", "without losing", "loss-free"},
    "tables": {"relations", "tabular", "tables", "table"},
    "tabular": {"tables", "relations", "tabular"},
    "keys": {"identifiers", "keys", "key"},
    "key": {"keys", "identifier", "identifiers", "primary key", "key"},
    "identifier": {"identifier", "identifiers", "identification", "identify", "identifies", "uniquely identifies"},
    "identification": {"identifier", "identifiers", "identification", "identify", "identifies"},
    "identify": {"identifier", "identifiers", "identification", "identify", "identifies"},
    "identifies": {"identifier", "identifiers", "identification", "identify", "identifies"},
    "unique": {"distinct", "unique", "uniquely", "uniqueness"},
    "uniquely": {"distinct", "unique", "uniquely", "uniqueness"},
    "integrity": {"invariants", "validity", "integrity", "distinct", "uniqueness"},
    "connection-oriented": {"connection", "handshake", "session", "connected", "connection-oriented"},
    "connection": {"connection-oriented", "handshake", "session", "connected", "connection"}
}


def _item_value(item, key: str, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def calculate_lexical_answer_score(student_answer: str, reference_answer: str) -> float:
    """
    Estimate concept overlap for short answers when embedding similarity is too strict.
    Returns an F1-style score in [0, 1], using meaningful words and known synonyms.
    """
    def tokens(value: str) -> list[str]:
        raw = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", (value or "").lower())
        result = []
        for token in raw:
            if token in STOPWORDS or len(token) < 2:
                continue
            if token.endswith("s") and len(token) > 4 and token[:-1] not in STOPWORDS:
                singular = token[:-1]
                if singular in {"key", "table", "relation", "identifier", "index", "database"}:
                    token = singular
            result.append(token)
        return result

    def canonicalize_phrases(value: str) -> str:
        # Normalize common equivalent ways of describing the same OS/DB concepts.
        # Keep this list explicit and conservative; it supplements, not replaces, model evidence.
        phrase_groups = [
            (r"\bwait(?:ing)?\s+(?:for|on)\s+each other\s+(?:forever|indefinitely)\b", "wait indefinitely for resources held by one another"),
            (r"\bwait(?:ing)?\s+(?:for|on)\s+one another\s+(?:forever|indefinitely)\b", "wait indefinitely for resources held by one another"),
            (r"\b(?:none of them can continue|none can continue|cannot continue|can't continue|unable to continue|cannot proceed|can't proceed)\b", "preventing further execution"),
            (r"\b(?:preventing|prevents|prevent)\s+(?:any\s+)?further execution\b", "preventing further execution"),
            (r"\b(?:wait forever|wait endlessly)\b", "wait indefinitely"),
            (r"\b(?:each other|one another)\b", "one another"),
        ]
        normalized = (value or "").lower()
        for pattern, replacement in phrase_groups:
            normalized = re.sub(pattern, replacement, normalized)
        return normalized

    student_tokens = tokens(canonicalize_phrases(student_answer))
    reference_tokens = tokens(canonicalize_phrases(reference_answer))
    if not student_tokens or not reference_tokens:
        return 0.0

    synonym_groups = [set([key, *values]) for key, values in SYNONYMS.items()]
    def equivalent(token: str) -> set[str]:
        matches = {token}
        for group in synonym_groups:
            if token in group:
                matches.update(group)
        return matches

    student_expanded = [equivalent(token) for token in student_tokens]
    reference_expanded = [equivalent(token) for token in reference_tokens]
    matched_reference = sum(
        1 for ref in reference_expanded
        if any(ref & student for student in student_expanded)
    )
    matched_student = sum(
        1 for student in student_expanded
        if any(student & ref for ref in reference_expanded)
    )
    recall = matched_reference / len(reference_expanded)
    precision = matched_student / len(student_expanded)
    if precision + recall <= 0:
        return 0.0
    return round(max(0.0, min(1.0, 2 * precision * recall / (precision + recall))), 4)


def get_crit_matches(crit_words: list[str], clean_ans: str) -> list[str]:
    stu_tokens = set(re.findall(r"[a-z0-9\-]+", clean_ans.lower()))
    matches = []
    for w in crit_words:
        syns = SYNONYMS.get(w, {w})
        if any(syn in clean_ans.lower() or syn in stu_tokens for syn in syns):
            matches.append(w)
    return matches


CONTRAST_MARKERS: list[str] = [
    r"\bunlike\b",
    r"\bwhereas\b",
    r"\bin contrast to\b",
    r"\bcompared to\b",
    r"\bas opposed to\b",
    r"\bdiffering from\b",
    r"\bwhile\b"
]


def is_contrast_context(text: str, term: str, affirmed_term: str) -> bool:
    """
    Returns True if term appears in a contrastive clause comparing a different entity,
    while affirmed_term is positively affirmed elsewhere in the answer.
    Prevents false contradictions like 'Unlike UDP which is connectionless, TCP is connection-oriented'.
    """
    if affirmed_term and affirmed_term not in text.lower():
        return False
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        s_lower = s.lower()
        if term in s_lower:
            if any(re.search(pat, s_lower) for pat in CONTRAST_MARKERS):
                return True
            clauses = re.split(r"[,;]+", s_lower)
            for c in clauses:
                if term in c and any(re.search(pat, c) for pat in CONTRAST_MARKERS):
                    return True
    return False


def detect_contradictions_and_correctness(
    student_answer: str,
    reference_answer: str,
    criteria_texts: list[str]
) -> tuple[bool, list[str], float]:
    """
    Deterministic contradiction & factual correctness engine:
    1. Checks for semantic antonym pairs and polarity reversals.
    2. Checks for syntactic negation flips (e.g. 'not reliable', 'never provides').
    3. Handles contrast clauses (e.g. 'Unlike UDP which is connectionless, TCP is connection-oriented').
    4. Returns (contradiction_detected, contradiction_details, overall_correctness).
    """
    stu_lower = (student_answer or "").lower()
    ref_combined = ((reference_answer or "") + " " + " ".join(criteria_texts)).lower()

    stu_tokens = set(re.findall(r"\b[a-z0-9\-]+\b", stu_lower))
    ref_tokens = set(re.findall(r"\b[a-z0-9\-]+\b", ref_combined))

    contradictions = []

    # 1. Antonym / Opposite polarity matching (with contrast context awareness)
    for pos, neg in OPPOSITE_PAIRS:
        # Case A: Reference asserts pos, student asserts neg
        if pos in ref_combined or pos in ref_tokens:
            stu_rem = re.sub(r"(?<![a-z0-9])" + re.escape(pos) + r"(?![a-z0-9])", "", stu_lower) if pos in stu_lower else stu_lower
            if re.search(r"(?<![a-z0-9])" + re.escape(neg) + r"(?![a-z0-9])", stu_rem):
                if not is_contrast_context(stu_lower, neg, pos):
                    contradictions.append(f"Student asserts '{neg}' which contradicts reference concept '{pos}'")
        # Case B: Reference asserts neg, student asserts pos
        elif neg in ref_combined or neg in ref_tokens:
            stu_rem = re.sub(r"(?<![a-z0-9])" + re.escape(neg) + r"(?![a-z0-9])", "", stu_lower) if neg in stu_lower else stu_lower
            if re.search(r"(?<![a-z0-9])" + re.escape(pos) + r"(?![a-z0-9])", stu_rem):
                if not is_contrast_context(stu_lower, pos, neg):
                    contradictions.append(f"Student asserts '{pos}' which contradicts reference concept '{neg}'")

    # 2. Syntactic Negation pattern matching (e.g., 'not <term>', 'no <term>', 'without <term>')
    negation_patterns = [
        r"\b(?:not|never|no|without|cannot|fails to|does not|doesn't|isn't|is not)\s+(?:any\s+|a\s+|the\s+)?([a-z\-]+)",
        r"\b([a-z\-]+)\s+(?:is not|cannot be|is never|does not provide)\b"
    ]
    for pattern in negation_patterns:
        for match in re.finditer(pattern, stu_lower):
            term = match.group(1)
            matched_ref = term if term in ref_tokens else next(
                (rt for rt in ref_tokens if (rt.startswith(term) or term.startswith(rt)) and len(rt) >= 5 and len(term) >= 5),
                None
            )
            if matched_ref and len(term) >= 4 and term not in ["the", "this", "that", "with", "have"]:
                if not re.search(r"\b(?:not|no|without|never)\s+(?:any\s+|a\s+|the\s+)?" + re.escape(term), ref_combined):
                    detail = f"Negation detected: student states '{match.group(0)}' whereas reference asserts '{matched_ref}'"
                    if detail not in contradictions:
                        contradictions.append(detail)

    contradiction_detected = len(contradictions) > 0

    # 3. Calculate overall factual correctness ratio
    if len(contradictions) >= 2:
        overall_correctness = 0.0
    elif len(contradictions) == 1:
        overall_correctness = 0.20
    else:
        overall_correctness = 1.0

    return contradiction_detected, contradictions, overall_correctness


def evaluate_hybrid_descriptive(
    db: Session,
    student_answer: str,
    question_max_marks: int,
    reference_answer: str | None,
    reference_embedding: list[float] | None,
    rubric_criteria: list
) -> tuple[float, float, dict]:
    """
    Hybrid descriptive evaluation:
    1. Overall semantic similarity via PostgreSQL pgvector.
    2. Rubric / key concept coverage evaluation against each criterion.
    3. Factual correctness & contradiction detection.
    4. Deterministic final score blending:
       - With rubrics: 60% Rubric + 20% Semantic + 20% Correctness.
       - If contradiction detected: substantial penalty applied (never full marks).
       - Legacy fallback: When question has no rubrics, evaluates via base pgvector.
    5. Always bounded: 0.0 <= awarded_marks <= question_max_marks.
    """
    if question_max_marks <= 0:
        return 0.0, 0.0, {
            "evaluator_version": "hybrid-v2-nli",
            "embedding_model": "all-MiniLM-L6-v2",
            "nli_model": "cross-encoder/nli-distilroberta-base",
            "overall_semantic_similarity": 0.0,
            "overall_correctness": 0.0,
            "contradiction_detected": False,
            "contradiction_details": [],
            "evaluator_confidence": 0.0,
            "confidence_basis": "insufficient_evidence",
            "review_status": "review_required",
            "evaluation_state": "invalid_maximum",
            "degraded_capabilities": [],
            "criteria": []
        }

    clean_ans = (student_answer or "").strip()[:12000]
    words = clean_ans.split()
    if not clean_ans or len(words) < 2:
        return 0.0, 0.0, {
            "evaluator_version": "hybrid-v2-nli",
            "embedding_model": "all-MiniLM-L6-v2",
            "nli_model": "cross-encoder/nli-distilroberta-base",
            "overall_semantic_similarity": 0.0,
            "overall_correctness": 0.0,
            "contradiction_detected": False,
            "contradiction_details": [],
            "evaluator_confidence": 0.0,
            "confidence_basis": "insufficient_evidence",
            "review_status": "review_required",
            "evaluation_state": "empty_or_too_short_answer",
            "degraded_capabilities": [],
            "criteria": []
        }

    # Embedding models are optional at grading time: a model download/cache failure
    # must not turn a valid submission into an HTTP 500 or an unreviewed grade.
    embedding_fallback_used = False
    nli_fallback_used = False
    embedding_failure_reason = None

    def safe_generate_embedding(text_content: str) -> list[float]:
        nonlocal embedding_fallback_used, embedding_failure_reason
        try:
            vector = generate_embedding(text_content)
            if len(vector) != VECTOR_DIMENSION or any(not math.isfinite(float(x)) for x in vector):
                raise ValueError("Invalid embedding shape or values")
            if not any(float(x) != 0.0 for x in vector):
                raise ValueError("Embedding is a zero vector")
            return [float(x) for x in vector]
        except Exception as exc:
            embedding_fallback_used = True
            if embedding_failure_reason is None:
                embedding_failure_reason = f"{type(exc).__name__}: {str(exc)[:240]}"
            logger.warning("AI grading embedding unavailable (%s)", embedding_failure_reason)
            return [0.0] * VECTOR_DIMENSION

    # Generate 384-dimensional vector embedding for student answer
    stu_vec = safe_generate_embedding(clean_ans)

    # Compute overall pgvector similarity against reference answer
    if reference_embedding:
        overall_sim = compute_pgvector_similarity(db, stu_vec, reference_embedding)
    else:
        overall_sim = 0.0

    if math.isnan(overall_sim) or math.isinf(overall_sim):
        overall_sim = 0.0

    # Sentence-level breakdown for granular criterion matching
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_ans) if len(s.strip().split()) >= 2]
    sentence_vecs = [safe_generate_embedding(s) for s in sentences] if sentences else []

    criteria_texts = [_item_value(c, "criterion_text", "") for c in rubric_criteria]

    # Contradiction and factual correctness check
    contradiction_detected, contradiction_details, overall_correctness = detect_contradictions_and_correctness(
        clean_ans, reference_answer or "", criteria_texts
    )

    criteria_eval_list = []
    all_crit_embs = []

    if rubric_criteria and len(rubric_criteria) > 0:
        for c in rubric_criteria:
            crit_id = _item_value(c, "id")
            crit_text = _item_value(c, "criterion_text", "")
            crit_max = float(_item_value(c, "max_marks", 1.0))
            crit_emb = _item_value(c, "criterion_embedding")

            if not crit_emb:
                crit_emb = safe_generate_embedding(crit_text)
            else:
                crit_emb = list(crit_emb)

            all_crit_embs.append(crit_emb)

            # 1. Compare full criterion embedding against student answer & individual sentences
            sim_full = compute_pgvector_similarity(db, stu_vec, crit_emb)
            sim_sents = [compute_pgvector_similarity(db, sv, crit_emb) for sv in sentence_vecs] if sentence_vecs else [0.0]
            max_sent_sim = max(sim_sents)

            # 2. Extract key conceptual predicate (excluding common generic stopwords and subject)
            first_tokens = reference_answer.split()[:2] if reference_answer else []
            subject = first_tokens[0].lower().rstrip(",.:;") if first_tokens else ""
            pred_words = [w for w in re.findall(r"[a-z0-9\-]+", crit_text.lower()) if w not in STOPWORDS and w != subject and (len(w) >= 2 or w.isdigit())]
            pred_text = " ".join(pred_words) if pred_words else crit_text

            matches = get_crit_matches(pred_words, clean_ans)
            match_ratio = len(matches) / len(pred_words) if pred_words else 0.0

            pred_emb = safe_generate_embedding(pred_text) if pred_text != crit_text else crit_emb
            sim_pred_sents = max([compute_pgvector_similarity(db, sv, pred_emb) for sv in sentence_vecs]) if sentence_vecs else 0.0
            sim_pred_full = compute_pgvector_similarity(db, stu_vec, pred_emb)
            pred_sim = max(sim_pred_full, sim_pred_sents)

            effective_sim = max(sim_full, max_sent_sim, pred_sim)
            crit_sim = effective_sim

            # 3. Shortlist relevant candidate student sentence via pgvector
            best_candidate_sentence = clean_ans
            candidate_sim = sim_full
            if sentences and sentence_vecs:
                ranked_candidates = sorted(
                    zip(sim_sents, sentences),
                    key=lambda x: x[0],
                    reverse=True
                )
                if ranked_candidates:
                    candidate_sim, best_candidate_sentence = ranked_candidates[0]

            # 4. NLI Inference on shortlisted candidate (only when candidate has relevance to avoid false contradiction on omitted concepts)
            is_relevant_candidate = (effective_sim >= 0.20 or match_ratio > 0 or candidate_sim >= 0.20)
            if is_relevant_candidate and not embedding_fallback_used:
                try:
                    nli_result = classify_nli(premise=crit_text, hypothesis=best_candidate_sentence)
                    if nli_result.get("fallback_error"):
                        nli_fallback_used = True
                        logger.warning("AI grading NLI unavailable: %s", str(nli_result["fallback_error"])[:240])
                    nli_contra = nli_result.get("contradiction", 0.0)
                    nli_entail = nli_result.get("entailment", 0.0)
                    nli_neut = nli_result.get("neutral", 1.0)
                except Exception as exc:
                    nli_fallback_used = True
                    logger.warning("AI grading NLI inference failed: %s: %s", type(exc).__name__, str(exc)[:240])
                    nli_contra = 0.0
                    nli_entail = 0.0
                    nli_neut = 1.0
            else:
                nli_contra = 0.0
                nli_entail = 0.0
                nli_neut = 1.0

            # 5. Check if this specific criterion was contradicted in student answer
            crit_words = re.findall(r"[a-z]{4,}", crit_text.lower())
            is_crit_det_contradicted = any(
                detail for detail in contradiction_details
                if any(w in detail.lower() for w in crit_words)
            )
            # Only trust NLI contradiction when student actually engages with the criterion topic.
            # If match_ratio == 0 (student uses NONE of criterion's key terms) and the deterministic
            # engine also found no contradiction for this criterion, then NLI is detecting "omission"
            # not true contradiction.  Omission → 0 marks for criterion, but NOT the global 90% penalty.
            is_nli_contradicted = (
                is_relevant_candidate
                and nli_contra >= 0.70
                and nli_contra > nli_entail
                and (match_ratio > 0 or is_crit_det_contradicted)
            )
            is_crit_contradicted = is_crit_det_contradicted or is_nli_contradicted

            if is_crit_contradicted:
                crit_sim = 0.0
                covered = False
                score_ratio = 0.0
                awarded_marks = 0.0
                crit_confidence = max(0.85, nli_contra)
                if is_nli_contradicted and not is_crit_det_contradicted:
                    detail = f"NLI contradiction ({round(nli_contra*100, 1)}%) detected on criterion: '{crit_text}'"
                    if detail not in contradiction_details:
                        contradiction_details.append(detail)
                        contradiction_detected = True
            else:
                # Concept is covered if:
                # a) High NLI entailment + good rubric semantic similarity / predicate match
                # b) Distinct predicate is semantically represented or synonym matched
                # c) High neutral gives partial / proportional credit
                if nli_entail >= 0.60 and (effective_sim >= 0.25 or match_ratio >= 0.40):
                    score_ratio = 1.0
                    covered = True
                    crit_confidence = min(0.98, max(0.82, 0.4 * effective_sim + 0.6 * nli_entail))
                elif (match_ratio >= 0.60 and effective_sim >= 0.25) or (match_ratio >= 0.50 and effective_sim >= 0.55) or (sim_full >= 0.75 and pred_sim >= 0.40) or (max_sent_sim >= 0.75):
                    score_ratio = 1.0
                    covered = True
                    crit_confidence = min(0.95, max(0.78, 0.6 * effective_sim + 0.4 * (1.0 - nli_contra)))
                elif match_ratio >= 0.50:
                    score_ratio = min(1.0, max(0.0, round((effective_sim - 0.35) / (0.55 - 0.35), 2)))
                    covered = (score_ratio >= 0.50)
                    crit_confidence = 0.65 if covered else 0.55
                elif match_ratio > 0 and pred_sim >= 0.42:
                    score_ratio = min(1.0, max(0.0, round((pred_sim - 0.35) / (0.50 - 0.35), 2)))
                    covered = (score_ratio >= 0.50)
                    crit_confidence = 0.60 if covered else 0.50
                elif pred_sim >= 0.40:
                    score_ratio = min(1.0, max(0.0, round((pred_sim - 0.40) / (0.52 - 0.40), 2)))
                    covered = (score_ratio >= 0.50)
                    crit_confidence = 0.55 if covered else 0.45
                elif nli_entail >= 0.45 and effective_sim >= 0.20:
                    score_ratio = round(nli_entail * 0.75, 2)
                    covered = (score_ratio >= 0.50)
                    crit_confidence = 0.60
                else:
                    score_ratio = 0.0
                    covered = False
                    crit_confidence = 0.88 if effective_sim < 0.20 else 0.50

                score_ratio = max(0.0, min(1.0, score_ratio))

            # Lexical concept coverage supplements embeddings for close paraphrases.
            # Never use this fallback to override an explicit contradiction.
            lexical_ratio = calculate_lexical_answer_score(clean_ans, crit_text)
            if not is_crit_contradicted and lexical_ratio >= 0.50:
                score_ratio = max(score_ratio, lexical_ratio)
                covered = score_ratio >= 0.50
                if lexical_ratio >= 0.75:
                    crit_confidence = max(crit_confidence, 0.80)
                else:
                    crit_confidence = max(crit_confidence, 0.60)

            awarded_marks = round(score_ratio * crit_max, 2)

            criteria_eval_list.append({
                "criterion_id": crit_id,
                "criterion_text": crit_text,
                "max_marks": crit_max,
                "semantic_similarity": round(crit_sim, 4),
                "similarity": round(crit_sim, 4),
                "nli": {
                    "entailment": round(nli_entail, 4),
                    "contradiction": round(nli_contra, 4),
                    "neutral": round(nli_neut, 4)
                },
                "covered": covered,
                "confidence": round(crit_confidence, 4),
                "score_ratio": score_ratio,
                "awarded_marks": awarded_marks
            })

        rubric_max = sum(item["max_marks"] for item in criteria_eval_list)
        rubric_awarded = sum(item["awarded_marks"] for item in criteria_eval_list)
        rubric_ratio = min(1.0, max(0.0, rubric_awarded / rubric_max)) if rubric_max > 0 else 0.0

        semantic_ratio = calculate_descriptive_marks(overall_sim, 1.0, clean_ans)

        # Content score blends rubric coverage (60%), semantic similarity (20%), and factual correctness (20%)
        if rubric_ratio == 0.0 and semantic_ratio == 0.0:
            blended_ratio = 0.0
        else:
            correctness_ratio = max(0.0, min(1.0, overall_correctness))
            blended_ratio = (0.60 * rubric_ratio) + (0.20 * semantic_ratio) + (0.20 * correctness_ratio)

        # Critical requirement: Contradictory answer MUST NOT receive full marks!
        if contradiction_detected:
            blended_ratio = blended_ratio * 0.10

        # Multi-sentence conciseness & dilution penalty for long padded answers
        relevance_factor = 1.0
        if len(sentences) >= 3 and reference_embedding:
            rel_count = sum(1 for sv in sentence_vecs if max([compute_pgvector_similarity(db, sv, reference_embedding)] + [compute_pgvector_similarity(db, sv, ce) for ce in all_crit_embs]) >= 0.30)
            rel_ratio = rel_count / len(sentences)
            relevance_factor = min(1.0, max(0.40, 0.30 + 0.70 * rel_ratio))

        final_marks = round(blended_ratio * relevance_factor * float(question_max_marks), 1)
        final_marks = max(0.0, min(float(question_max_marks), final_marks))

        # Overall Evaluator Confidence
        avg_crit_conf = sum(item["confidence"] for item in criteria_eval_list) / len(criteria_eval_list)
        if contradiction_detected:
            evaluator_confidence = round(min(0.95, avg_crit_conf), 2)
        elif relevance_factor < 0.8:
            evaluator_confidence = round(avg_crit_conf * relevance_factor, 2)
        else:
            evaluator_confidence = round(avg_crit_conf, 2)

    else:
        # Legacy descriptive evaluation (without a teacher-authored rubric).
        # Combine semantic similarity with meaningful-token coverage so concise,
        # correctly paraphrased answers can receive partial credit.
        lexical_score = calculate_lexical_answer_score(clean_ans, reference_answer or "")
        semantic_score = calculate_descriptive_marks(overall_sim, 1.0, clean_ans)
        evidence_score = max(float(lexical_score), float(semantic_score))
        base_marks = round(evidence_score * float(question_max_marks), 1)

        nli_res = classify_nli(premise=reference_answer or "", hypothesis=clean_ans) if reference_answer and not embedding_fallback_used else {"contradiction": 0.0, "entailment": 0.0, "neutral": 1.0}
        if nli_res.get("fallback_error"):
            nli_fallback_used = True
            logger.warning("AI grading NLI unavailable: %s", str(nli_res["fallback_error"])[:240])
        legacy_contra = nli_res.get("contradiction", 0.0)
        legacy_entail = nli_res.get("entailment", 0.0)

        if legacy_contra >= 0.70:
            contradiction_detected = True
            contradiction_details.append(f"NLI contradiction detected with reference answer ({round(legacy_contra*100, 1)}% probability)")
            overall_correctness = 0.0

        if contradiction_detected:
            base_marks = round(base_marks * 0.15, 1)

        final_marks = max(0.0, min(float(question_max_marks), base_marks))

        if contradiction_detected:
            evaluator_confidence = 0.88
        elif evidence_score < 0.20:
            evaluator_confidence = 0.35
        elif evidence_score < 0.45:
            evaluator_confidence = 0.58
        elif evidence_score >= 0.75 and (legacy_entail >= 0.35 or legacy_contra < 0.10):
            evaluator_confidence = 0.86
        else:
            evaluator_confidence = 0.68

    evaluator_confidence = max(0.0, min(1.0, float(evaluator_confidence)))
    if embedding_fallback_used or nli_fallback_used:
        # Heuristic evidence strength is not a statistically calibrated probability.
        evaluator_confidence = min(evaluator_confidence, 0.49)
    # Model confidence is never teacher approval. Every AI suggestion remains reviewable.
    review_status = "review_required" if embedding_fallback_used or nli_fallback_used or evaluator_confidence < 0.75 else "review_recommended"
    degraded_capabilities = []
    if embedding_fallback_used:
        degraded_capabilities.append("semantic_embeddings")
    if nli_fallback_used:
        degraded_capabilities.append("natural_language_inference")

    eval_dict = {
        "evaluator_version": "hybrid-v3-review-safe",
        "confidence_basis": "heuristic_evidence_strength_not_calibrated_probability",
        "evaluation_state": "degraded" if degraded_capabilities else "evaluated",
        "degraded_capabilities": degraded_capabilities,
        "embedding_failure_reason": embedding_failure_reason,
        "embedding_model": "all-MiniLM-L6-v2",
        "nli_model": "cross-encoder/nli-distilroberta-base",
        "overall_semantic_similarity": round(overall_sim, 4),
        "overall_correctness": round(overall_correctness, 2),
        "contradiction_detected": contradiction_detected,
        "contradiction_details": contradiction_details,
        "evaluator_confidence": round(evaluator_confidence, 2),
        "review_status": review_status,
        "embedding_fallback_used": embedding_fallback_used,
        "nli_fallback_used": nli_fallback_used,
        "scoring_fallback": "lexical_review_required" if embedding_fallback_used else ("nli_unavailable_review_required" if nli_fallback_used else None),
        "criteria": criteria_eval_list
    }

    return final_marks, round(overall_sim, 4), eval_dict


def suggest_rubric_from_reference_answer(
    question_text: str,
    reference_answer: str,
    max_marks: int
) -> list[dict]:
    """
    Deconstructs a reference answer into discrete, measurable key concepts/criteria
    summing precisely to max_marks.
    """
    clean_ref = (reference_answer or "").strip()
    if not clean_ref:
        return []

    # Split into logical sentence/clause units
    parts = [p.strip() for p in re.split(r"(?<=[.?!;])\s+", clean_ref) if len(p.strip().split()) >= 3]
    if len(parts) < 2:
        # Split on conjunctions
        subparts = [p.strip() for p in re.split(r",\s*(?:and|while|whereas|by|which|allowing)\s+", clean_ref) if len(p.strip().split()) >= 3]
        if len(subparts) >= 2:
            parts = subparts

    if not parts:
        parts = [clean_ref]

    # Limit to at most 5 criteria
    parts = parts[:5]
    n = len(parts)

    # Allocate marks so sum(marks) == max_marks exactly
    base = max_marks // n
    remainder = max_marks % n

    criteria = []
    for idx, text_part in enumerate(parts):
        allocated = base + (1 if idx < remainder else 0)
        criteria.append({
            "criterion_text": text_part,
            "max_marks": float(allocated),
            "order_index": idx + 1
        })

    return criteria


def evaluate_mcq_answer(selected_option_id: int | None, correct_option_id: int | None, max_marks: int) -> tuple[float, bool | None, str]:
    """
    MCQ Evaluation:
    - If unanswered (selected_option_id is None): 0.0 marks, is_correct = None, status = "unanswered"
    - If selected_option_id == correct_option_id: max_marks, is_correct = True, status = "evaluated"
    - If wrong: 0.0 marks, is_correct = False, status = "evaluated"
    """
    if selected_option_id is None:
        return 0.0, None, "unanswered"
    if correct_option_id is not None and int(selected_option_id) == int(correct_option_id):
        return float(max_marks), True, "evaluated"
    return 0.0, False, "evaluated"
