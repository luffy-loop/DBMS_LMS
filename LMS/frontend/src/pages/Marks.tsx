import { useEffect, useState } from "react"
import { BookOpen, LayoutDashboard, ClipboardList, Award, Search, LogOut, User, ChevronDown, ChevronUp, CheckCircle2, XCircle } from "lucide-react"
import { useNavigate } from "react-router-dom"
import MobileNav from "../components/MobileNav"
import { API } from "../config"

type Submission = {
  id: number
  assignment_id: number
  assignment_title?: string | null
  student_id: number
  student_name?: string | null
  answer: string
  marks: number | null
  max_marks?: number | null
  file_id: string | null
  file_name: string | null
}

type QuestionEval = {
  question_id: number
  question_text: string
  question_type: string
  max_marks: number
  awarded_marks: number
  similarity_score?: number
  student_answer?: string
  reference_answer?: string
  is_correct?: boolean | null
  evaluator_version?: string
  teacher_override_marks?: number | null
  teacher_review_note?: string | null
  review_status?: string
  evaluator_confidence?: number | null
  reviewed_at?: string | null
  reviewed_by?: number | null
  rubric_evaluation?: {
    evaluator_version?: string
    embedding_model?: string
    nli_model?: string
    overall_semantic_similarity?: number
    overall_correctness?: number
    contradiction_detected?: boolean
    contradiction_details?: string[]
    evaluator_confidence?: number
    review_status?: string
    criteria?: {
      criterion_id?: number
      criterion_text: string
      max_marks: number
      similarity: number
      covered: boolean
      score_ratio: number
      awarded_marks: number
      confidence?: number
      nli?: { entailment: number; contradiction: number; neutral: number }
    }[]
  }
}

export default function Marks() {
  const navigate = useNavigate()
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [loading, setLoading] = useState(true)
  const [marks, setMarks] = useState<Record<number, string>>({})
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [evalBreakdowns, setEvalBreakdowns] = useState<Record<number, QuestionEval[]>>({})
  const [loadingBreakdown, setLoadingBreakdown] = useState<Record<number, boolean>>({})
  const [reviewOverrides, setReviewOverrides] = useState<Record<string, string>>({})
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({})
  const [reviewLoading, setReviewLoading] = useState<Record<number, boolean>>({})

  const role = localStorage.getItem("role") || "student"
  const name = localStorage.getItem("name") || "User"

  useEffect(() => {
    const token = localStorage.getItem("token")
    if (!token) { navigate("/login"); return }
    loadSubmissions(token)
  }, [navigate, role])

  async function loadSubmissions(token: string) {
    try {
      const endpoint = role === "teacher" ? "/teacher/submissions" : "/my-marks"
      const res = await fetch(`${API}${endpoint}`, { headers: { Authorization: `Bearer ${token}` } })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Failed to load marks")
      setSubmissions(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load marks")
    } finally {
      setLoading(false)
    }
  }

  async function toggleBreakdown(subId: number) {
    if (evalBreakdowns[subId]) {
      setEvalBreakdowns(prev => {
        const next = { ...prev }
        delete next[subId]
        return next
      })
      return
    }

    const token = localStorage.getItem("token")
    if (!token) return
    setLoadingBreakdown(prev => ({ ...prev, [subId]: true }))
    try {
      const res = await fetch(`${API}/submissions/${subId}/evaluation`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setEvalBreakdowns(prev => ({ ...prev, [subId]: data.questions || [] }))
      }
    } catch {
      // Ignored if legacy submission
    } finally {
      setLoadingBreakdown(prev => ({ ...prev, [subId]: false }))
    }
  }

  async function openPdf(id: number) {
    const token = localStorage.getItem("token")
    if (!token) return navigate("/login")
    try {
      const res = await fetch(`${API}/submissions/${id}/download`, { headers: { Authorization: `Bearer ${token}` } })
      if (!res.ok) throw new Error("Unable to open PDF")
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      window.open(url, "_blank", "noopener,noreferrer")
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open PDF")
    }
  }

  async function submitReview(subId: number) {
    const token = localStorage.getItem("token")
    if (!token) return
    const questions = evalBreakdowns[subId]
    if (!questions) return
    setReviewLoading(prev => ({ ...prev, [subId]: true }))
    try {
      setError(""); setMessage("")
      const reviews = questions
        .filter(q => q.question_type === "descriptive")
        .map(q => {
          const key = `${subId}-${q.question_id}`
          const ovr = reviewOverrides[key]
          const note = reviewNotes[key]
          const item: { question_id: number; override_marks?: number; review_note?: string } = { question_id: q.question_id }
          if (ovr !== undefined && ovr !== "") item.override_marks = Number(ovr)
          if (note) item.review_note = note
          return item
        })
        .filter(r => r.override_marks !== undefined || r.review_note)
      if (reviews.length === 0) { setError("No changes to submit"); return }
      const res = await fetch(`${API}/submissions/${subId}/review`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ reviews })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Review failed")
      setMessage("Review submitted successfully")
      setReviewOverrides({}); setReviewNotes({})
      await loadSubmissions(token)
      toggleBreakdown(subId); setTimeout(() => toggleBreakdown(subId), 100)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed")
    } finally {
      setReviewLoading(prev => ({ ...prev, [subId]: false }))
    }
  }

  async function giveMarks(id: number) {
    const token = localStorage.getItem("token")
    const value = marks[id]
    if (!token || !value) return
    const score = Number(value)
    if (!Number.isInteger(score) || score < 0 || score > 100) {
      setError("Marks must be a whole number from 0 to 100")
      return
    }
    try {
      setError(""); setMessage("")
      const res = await fetch(`${API}/submissions/${id}/marks?marks=${score}`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Failed to update marks")
      setMessage("Marks updated successfully")
      await loadSubmissions(token)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update marks")
    }
  }

  function logout() { localStorage.clear(); navigate("/login") }

  return (
    <div className="min-h-screen bg-[#070b14] text-white">
      <aside className="fixed left-0 top-0 hidden h-screen w-64 border-r border-white/10 bg-[#0b101a] p-5 lg:block">
        <div className="flex items-center gap-3 px-3 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-black"><BookOpen size={21} /></div>
          <div><h1 className="font-semibold">LMS</h1><p className="text-xs text-white/40">Learning Platform</p></div>
        </div>
        <nav className="mt-8 space-y-2">
          <button onClick={() => navigate(role === "teacher" ? "/teacher" : "/dashboard")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
            <LayoutDashboard size={18} />Dashboard
          </button>
          <button onClick={() => navigate(role === "teacher" ? "/teacher" : "/courses")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
            <BookOpen size={18} />My Courses
          </button>
          <button onClick={() => navigate("/assignments")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
            <ClipboardList size={18} />Assignments
          </button>
          <button className="flex w-full items-center gap-3 rounded-xl bg-white/10 px-4 py-3 text-sm">
            <Award size={18} />{role === "teacher" ? "Student Marks" : "Marks"}
          </button>
          <button onClick={() => navigate("/search")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
            <Search size={18} />AI Search
          </button>
        </nav>
        <button onClick={logout} className="absolute bottom-6 left-5 right-5 flex items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
          <LogOut size={18} />Logout
        </button>
      </aside>

      <main className="lg:ml-64">
        <header className="flex items-center justify-between border-b border-white/10 px-6 py-5 lg:px-10">
          <div>
            <p className="text-sm text-white/40">{role === "teacher" ? "Teacher Marks" : "My Marks"}</p>
            <h2 className="mt-1 text-2xl font-semibold">{role === "teacher" ? "Student Submissions" : "My Marks & Grades"}</h2>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-white/40 sm:block">{name}</span>
            <button onClick={() => navigate("/profile")} className="lms-profile-trigger flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5" aria-label="Open profile">
              <User size={18} />
            </button>
          </div>
        </header>

        <section className="p-6 lg:p-10">
          {message && <div className="mb-6 rounded-xl border border-green-400/20 bg-green-400/10 px-4 py-3 text-sm text-green-300">{message}</div>}
          {error && <div className="mb-6 rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-300">{error}</div>}

          {loading ? (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center text-white/40">Loading marks...</div>
          ) : submissions.length === 0 ? (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center">
              <Award className="mx-auto mb-4 text-white/30" size={34} />
              <p className="text-white/60">{role === "teacher" ? "No pending submissions" : "No marks available yet"}</p>
            </div>
          ) : (
            <div className="space-y-5">
              {submissions.map(submission => (
                <div key={submission.id} className="rounded-2xl border border-white/10 bg-white/[0.035] p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs text-white/30">Submission ID: #{submission.id}</p>
                      <h3 className="mt-2 text-lg font-medium">{submission.assignment_title ? `${submission.assignment_title} (Assignment #${submission.assignment_id})` : `Assignment #${submission.assignment_id}`}</h3>
                      {role === "teacher" && <p className="mt-1 text-sm text-white/40">{submission.student_name ? `Student: ${submission.student_name} (ID: ${submission.student_id})` : `Student ID: ${submission.student_id}`}</p>}
                    </div>

                    <div className="flex items-center gap-3">
                      {submission.marks !== null && (
                        <div className="rounded-xl border border-white/10 bg-white/10 px-4 py-2 text-sm">
                          Marks: <span className="font-semibold text-white">{submission.marks}</span>
                          {submission.max_marks ? <span className="text-white/40"> / {submission.max_marks}</span> : ""}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="mt-5 rounded-xl border border-white/10 bg-black/20 p-4">
                    <p className="mb-2 text-xs text-white/30">Answer Summary</p>
                    <p className="text-sm leading-6 text-white/70">{submission.answer}</p>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    {submission.file_id && (
                      <button onClick={() => openPdf(submission.id)} className="flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm hover:bg-white/5">
                        <span>PDF: {submission.file_name}</span>
                        <span>Open</span>
                      </button>
                    )}

                    <button
                      onClick={() => toggleBreakdown(submission.id)}
                      className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-white/70 hover:bg-white/10 hover:text-white"
                    >
                      {evalBreakdowns[submission.id] ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                      {loadingBreakdown[submission.id] ? "Loading Details..." : evalBreakdowns[submission.id] ? "Hide Breakdown" : "Question Breakdown"}
                    </button>
                  </div>

                  {/* Question Breakdown Drawer */}
                  {evalBreakdowns[submission.id] && evalBreakdowns[submission.id].length > 0 && (
                    <div className="mt-5 rounded-2xl border border-white/10 bg-black/30 p-5">
                      <h4 className="text-xs uppercase tracking-wider text-white/40 font-semibold mb-3">
                        {role === "teacher" ? "Teacher Evaluation Audit" : "Question Marks Breakdown"}
                      </h4>
                      <div className="space-y-3">
                        {evalBreakdowns[submission.id].map((q, idx) => (
                          <div key={q.question_id} className="rounded-xl border border-white/5 bg-white/[0.02] p-4 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-white/80">Question {idx + 1} ({q.question_type.toUpperCase()})</span>
                              <span className="font-bold text-white">Awarded: {q.awarded_marks} / {q.max_marks} marks</span>
                            </div>
                            <p className="mt-1 text-white/60">{q.question_text}</p>

                            {/* TEACHER-ONLY AUDIT FIELDS (Strictly hidden from students) */}
                            {role === "teacher" && (
                              <div className="mt-3 border-t border-white/5 pt-2 text-[11px] text-white/50 space-y-1">
                                {q.question_type === "mcq" && (
                                  <div className="flex items-center gap-1.5">
                                    {q.is_correct ? <CheckCircle2 size={13} className="text-green-400" /> : <XCircle size={13} className="text-red-400" />}
                                    <span>Outcome: {q.is_correct ? "Correct (Full Marks)" : "Incorrect (0 Marks)"}</span>
                                  </div>
                                )}
                                {q.question_type === "descriptive" && (
                                  <>
                                    <div><span className="font-medium text-white/70">pgvector Cosine Similarity: </span>{q.similarity_score !== undefined ? (q.similarity_score * 100).toFixed(1) + "%" : "N/A"}</div>
                                    {q.student_answer && <div><span className="font-medium text-white/70">Student Answer: </span>{q.student_answer}</div>}
                                    {q.reference_answer && <div><span className="font-medium text-white/70">Reference Answer: </span>{q.reference_answer}</div>}
                                    {/* Review Status & Confidence */}
                                    {q.review_status && (
                                      <div className="flex items-center gap-2 mt-1">
                                        <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                                          q.review_status === "review_required" ? "bg-red-500/20 text-red-300" :
                                          q.review_status === "review_recommended" ? "bg-yellow-500/20 text-yellow-300" :
                                          q.review_status === "reviewed" ? "bg-blue-500/20 text-blue-300" :
                                          "bg-green-500/20 text-green-300"
                                        }`}>{q.review_status.replace(/_/g, " ").toUpperCase()}</span>
                                        {q.evaluator_confidence != null && <span className="text-[10px] text-white/40">Confidence: {(q.evaluator_confidence * 100).toFixed(0)}%</span>}
                                        {q.teacher_override_marks != null && <span className="text-[10px] text-blue-300">Override: {q.teacher_override_marks}</span>}
                                      </div>
                                    )}
                                    {q.rubric_evaluation && (
                                      <div className="mt-2 space-y-1.5 rounded-lg border border-white/5 bg-black/30 p-2.5">
                                        <div className="flex items-center justify-between text-[10px] text-white/60">
                                          <span>Evaluator: {q.rubric_evaluation.evaluator_version || "hybrid-v2-nli"} ({q.rubric_evaluation.embedding_model || "all-MiniLM-L6-v2"}{q.rubric_evaluation.nli_model ? " + " + q.rubric_evaluation.nli_model : ""})</span>
                                          {q.rubric_evaluation.contradiction_detected ? (
                                            <span className="text-red-400 font-semibold">⚠️ Contradiction Detected</span>
                                          ) : (
                                            <span className="text-green-400">✓ No Contradictions</span>
                                          )}
                                        </div>
                                        {q.rubric_evaluation.criteria && q.rubric_evaluation.criteria.length > 0 && (
                                          <div className="mt-1 space-y-1">
                                            <span className="font-semibold text-white/80">Rubric Criteria Breakdown:</span>
                                            {q.rubric_evaluation.criteria.map((c, i) => (
                                              <div key={i} className="rounded bg-white/5 px-2 py-1 text-[10px]">
                                                <div className="flex justify-between items-center">
                                                  <span className="text-white/70">{c.covered ? "✓" : "✗"} {c.criterion_text}</span>
                                                  <span className="text-white/90 font-medium">{c.awarded_marks} / {c.max_marks} marks</span>
                                                </div>
                                                {c.nli && <span className="text-white/30 ml-4">NLI: E={c.nli.entailment.toFixed(2)} C={c.nli.contradiction.toFixed(2)} N={c.nli.neutral.toFixed(2)}{c.confidence != null ? ` · conf=${(c.confidence*100).toFixed(0)}%` : ""}</span>}
                                              </div>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    )}
                                    {/* Teacher Override Controls */}
                                    {q.question_type === "descriptive" && q.review_status !== "reviewed" && (
                                      <div className="mt-2 space-y-1.5">
                                        <div className="flex gap-2 items-center">
                                          <input type="number" min="0" max={q.max_marks} step="0.5"
                                            placeholder="Override marks"
                                            value={reviewOverrides[`${submission.id}-${q.question_id}`] ?? ""}
                                            onChange={e => setReviewOverrides(prev => ({...prev, [`${submission.id}-${q.question_id}`]: e.target.value}))}
                                            className="w-28 rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] outline-none placeholder:text-white/20"
                                          />
                                          <input type="text" placeholder="Review note"
                                            value={reviewNotes[`${submission.id}-${q.question_id}`] ?? ""}
                                            onChange={e => setReviewNotes(prev => ({...prev, [`${submission.id}-${q.question_id}`]: e.target.value}))}
                                            className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] outline-none placeholder:text-white/20"
                                          />
                                        </div>
                                      </div>
                                    )}
                                  </>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                      {/* Submit Review Button */}
                      {role === "teacher" && evalBreakdowns[submission.id]?.some(q => q.question_type === "descriptive" && q.review_status !== "reviewed") && (
                        <div className="mt-3 flex justify-end">
                          <button
                            onClick={() => submitReview(submission.id)}
                            disabled={reviewLoading[submission.id]}
                            className="rounded-lg bg-white/10 px-4 py-1.5 text-xs font-medium text-white hover:bg-white/20 disabled:opacity-40"
                          >{reviewLoading[submission.id] ? "Submitting…" : "Submit Review"}</button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Manual Grading fallback for teacher if ungraded */}
                  {role === "teacher" && submission.marks === null && (
                    <div className="mt-5 flex gap-3">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={marks[submission.id] || ""}
                        onChange={e => setMarks(current => ({ ...current, [submission.id]: e.target.value }))}
                        placeholder="Enter marks"
                        className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-white/30"
                      />
                      <button onClick={() => giveMarks(submission.id)} className="rounded-xl bg-white px-6 py-3 text-sm font-medium text-black hover:bg-white/90">
                        Give Marks
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <MobileNav role={role} active="marks" />
    </div>
  )
}
