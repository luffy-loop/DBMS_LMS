# DSA algorithm integration notes

## Purpose

This document records how selected ideas from the separate [DSA-A6 repository](https://github.com/luffy-loop/DSA-A6) are applied in [DBMS_LMS](https://github.com/luffy-loop/DBMS_LMS). The repositories intentionally remain separate. No files or commits are moved into DSA-A6, and its history is left unchanged.

## Source algorithms and application

| DSA-A6 source | Relevant idea | LMS use |
| --- | --- | --- |
| [NeedlemanWunsch.java](https://github.com/luffy-loop/DSA-A6/blob/main/src/texthack/dynamicprogramming/NeedlemanWunsch.java) | Dynamic programming to align sequences | Inspiration for a token-level alignment signal between student and reference answers |
| [SmithWaterman.java](https://github.com/luffy-loop/DSA-A6/blob/main/src/texthack/dynamicprogramming/SmithWaterman.java) | Local sequence alignment | A useful future comparison point for finding the best-matching part of a longer answer; it is not claimed as the current implementation |
| [EditDistance.java](https://github.com/luffy-loop/DSA-A6/blob/main/src/texthack/dynamicprogramming/EditDistance.java) | Edit operations and string similarity | A possible future signal for spelling variation; it is not claimed as the current scoring implementation |

## Current implementation

The integration lives in `LMS/backend/evaluation_service.py`, in `calculate_sequence_alignment_score(student_answer, reference_answer)`.

The current helper:
- tokenizes and normalizes answer text;
- canonicalizes selected equivalent phrases and recognizes a limited set of synonyms;
- uses dynamic programming to find aligned/equivalent tokens;
- converts the alignment into a bounded overlap-style score;
- limits the input token count to avoid unbounded work.

The score is used as supplementary text evidence alongside lexical and semantic signals. At the criterion level, the evaluator exposes `sequence_alignment_score` in its evidence metadata. It must not override an explicit contradiction. It is not a direct Java import, and it is not the same as a full affine-gap Needleman–Wunsch implementation.

## Regression coverage

The associated tests in `LMS/backend/tests/test_answer_similarity_scoring.py` cover:
- a paraphrased deadlock definition receiving a strong alignment score;
- unrelated content receiving a low alignment score;
- scores staying within their valid bounds and empty input behavior.

The GitHub Actions run for the integration commit passed both backend tests and the frontend build: [workflow run](https://github.com/luffy-loop/DBMS_LMS/actions/runs/38067746043).

## Reliability boundaries

Sequence overlap is only one evidence source. Similar words do not prove that an answer is true, and different wording does not prove it is wrong. This heuristic should be validated on representative answers from several subjects, including counterexamples and contradictions, before relying on it for consequential grading. Low-confidence or degraded model results should remain reviewable by a teacher.

## Repository separation

- DSA coursework and learning history: [DSA-A6](https://github.com/luffy-loop/DSA-A6)
- Application and grading-engine implementation: [DBMS_LMS](https://github.com/luffy-loop/DBMS_LMS)

Keep future algorithm experiments in DSA-A6 when they are coursework, and port or adapt only the justified implementation into DBMS_LMS with tests and a clear attribution note.
