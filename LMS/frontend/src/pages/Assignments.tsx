import { useEffect, useState, useRef } from "react"
import { BookOpen, LayoutDashboard, ClipboardList, Award, Search, LogOut, Plus, X, Send, Clock, FileText, Upload, Download, ListChecks, CheckCircle2, Trash2 } from "lucide-react"
import { useNavigate } from "react-router-dom"
import MobileNav from "../components/MobileNav"
import { API } from "../config"

type Course = { id: number; title: string; description: string; teacher_id: number }
type A = {
  id: number
  title: string
  description: string
  course_id: number
  teacher_id: number
  type: string
  start_time: string | null
  end_time: string | null
  duration_minutes: number | null
  deadline: string | null
  status: "upcoming" | "open" | "closed"
  submitted: boolean
  handout: { id: string; title: string; filename: string } | null
}

type MCQOption = { id: number; option_text: string; is_correct?: boolean }
type RubricCriterion = { id?: number; criterion_text: string; max_marks: number; order_index?: number }
type Question = {
  id: number
  question_text: string
  question_type: "mcq" | "descriptive"
  max_marks: number
  order_index?: number
  options?: MCQOption[]
  correct_option_id?: number
  reference_answer?: string
  rubric_criteria?: RubricCriterion[]
}

type SubmissionResult = {
  submission_id: number
  total_marks: number
  max_marks: number
  percentage: number
  status: string
  questions: {
    question_id: number
    question_text: string
    question_type: string
    max_marks: number
    awarded_marks: number
  }[]
}

export default function Assignments() {
  const startRef = useRef<HTMLInputElement>(null)
  const endRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const [role, setRole] = useState("")
  const [courses, setCourses] = useState<Course[]>([])
  const [items, setItems] = useState<A[]>([])
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [courseId, setCourseId] = useState("")
  const [type, setType] = useState("assignment")
  const [start, setStart] = useState("")
  const [end, setEnd] = useState("")
  const [duration, setDuration] = useState("")
  const [handout, setHandout] = useState<File | null>(null)
  const [answer, setAnswer] = useState("")
  const [submissionFile, setSubmissionFile] = useState<File | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [show, setShow] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  // Question Management State (Teacher)
  const [managingAsgn, setManagingAsgn] = useState<A | null>(null)
  const [asgnQuestions, setAsgnQuestions] = useState<Question[]>([])
  const [qType, setQType] = useState<"mcq" | "descriptive">("mcq")
  const [qText, setQText] = useState("")
  const [qMaxMarks, setQMaxMarks] = useState("5")
  const [mcqOptions, setMcqOptions] = useState<string[]>(["", "", "", ""])
  const [mcqCorrectIndex, setMcqCorrectIndex] = useState(0)
  const [refAnswer, setRefAnswer] = useState("")
  const [rubricCriteria, setRubricCriteria] = useState<{ criterion_text: string; max_marks: string }[]>([])
  const [suggestingRubric, setSuggestingRubric] = useState(false)
  const [qLoading, setQLoading] = useState(false)

  // Student Exam Taking State
  const [examQuestions, setExamQuestions] = useState<Question[]>([])
  const [examAnswers, setExamAnswers] = useState<Record<number, { selected_option_id?: number; student_answer?: string }>>({})
  const [evalResult, setEvalResult] = useState<SubmissionResult | null>(null)
  const [submittingExam, setSubmittingExam] = useState(false)
  const [creating, setCreating] = useState(false)

  const [loadingQuestions, setLoadingQuestions] = useState(false)
  const [nowTime, setNowTime] = useState(Date.now())

  useEffect(() => {
    const t = localStorage.getItem("token")
    const r = localStorage.getItem("role") || "student"
    if (!t) { navigate("/login"); return }
    setRole(r)
    load(t, r)
  }, [navigate])

  useEffect(() => {
    const id = window.setInterval(() => setNowTime(Date.now()), 10000)
    return () => window.clearInterval(id)
  }, [])

  async function load(t: string, r: string) {
    try {
      const [coursesRes, assignmentsRes] = await Promise.all([
        fetch(API + (r === "teacher" ? "/my-courses" : "/my-courses"), { headers: { Authorization: "Bearer " + t } }),
        fetch(API + "/my-assignments", { headers: { Authorization: "Bearer " + t } })
      ])
      const cs = coursesRes.ok ? await coursesRes.json() : []
      setCourses(cs)
      setCourseId(prev => (prev && cs.some((c: Course) => String(c.id) === prev) ? prev : (cs[0] ? String(cs[0].id) : "")))
      
      if (assignmentsRes.ok) {
        setItems(await assignmentsRes.json())
      } else {
        const d = await Promise.all(
          cs.map((c: Course) => fetch(API + "/assignments/" + c.id, { headers: { Authorization: "Bearer " + t } }).then(x => x.ok ? x.json() : []))
        )
        setItems(d.flat())
      }
    } catch {
      setError("Failed to load assessments")
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault()
    if (creating) return
    const t = localStorage.getItem("token")
    if (!t) return
    if ((start && !end) || (!start && end)) { setError("Set both start and end time"); return }
    if (duration && !start) { setError("Start time is required for a duration"); return }
    setCreating(true)
    try {
      setError("")
      const b = new FormData()
      b.append("course_id", courseId)
      b.append("title", title)
      b.append("description", description)
      b.append("type", type)
      if (start) b.append("start_time", new Date(start).toISOString())
      if (end) b.append("end_time", new Date(end).toISOString())
      if (duration) b.append("duration_minutes", duration)
      if (handout) b.append("file", handout)
      const r = await fetch(API + "/assignments", { method: "POST", headers: { Authorization: "Bearer " + t }, body: b })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || "Creation failed")
      setMessage("Assessment created successfully")
      setShow(false); setTitle(""); setDescription(""); setStart(""); setEnd(""); setDuration(""); setHandout(null)
      await load(t, "teacher")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Creation failed")
    } finally {
      setCreating(false)
    }
  }

  // Load questions when teacher opens question manager
  async function openQuestionManager(asgn: A) {
    setManagingAsgn(asgn)
    setError("")
    setMessage("")
    const t = localStorage.getItem("token")
    if (!t) return
    try {
      const res = await fetch(API + `/assignments/${asgn.id}/questions`, { headers: { Authorization: "Bearer " + t } })
      if (res.ok) {
        setAsgnQuestions(await res.json())
      }
    } catch {
      setError("Failed to load questions")
    }
  }

  // Teacher adds question
  async function generateSuggestedRubric() {
    if (!managingAsgn) return
    const t = localStorage.getItem("token")
    if (!t) return
    if (!refAnswer.trim() || refAnswer.trim().split(" ").length < 2) {
      setError("Please provide a reference answer first to generate rubric criteria")
      return
    }
    setSuggestingRubric(true)
    setError("")
    try {
      const res = await fetch(API + `/assignments/${managingAsgn.id}/questions/suggest-rubric`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + t },
        body: JSON.stringify({
          question_text: qText.trim() || "Question",
          reference_answer: refAnswer.trim(),
          max_marks: Number(qMaxMarks) || 10
        })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Failed to generate rubric")
      if (data.criteria && Array.isArray(data.criteria)) {
        setRubricCriteria(data.criteria.map((c: { criterion_text: string; max_marks: number }) => ({
          criterion_text: c.criterion_text,
          max_marks: String(c.max_marks)
        })))
        setMessage("Rubric criteria suggested from reference answer! You can review and edit them.")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to suggest rubric")
    } finally {
      setSuggestingRubric(false)
    }
  }

  // Teacher adds question
  async function addQuestion(e: React.FormEvent) {
    e.preventDefault()
    if (!managingAsgn || qLoading) return
    const t = localStorage.getItem("token")
    if (!t) return

    setQLoading(true)
    setError("")
    try {
      const payload: Record<string, unknown> = {
        question_text: qText.trim(),
        question_type: qType,
        max_marks: Number(qMaxMarks) || 10,
        order_index: asgnQuestions.length + 1
      }

      if (qType === "mcq") {
        const validOpts = mcqOptions.map(o => o.trim()).filter(Boolean)
        if (validOpts.length < 2) throw new Error("MCQ requires at least 2 non-empty options")
        payload.options = validOpts.map((optText, idx) => ({
          option_text: optText,
          is_correct: idx === mcqCorrectIndex,
          order_index: idx
        }))
      } else {
        if (!refAnswer.trim() || refAnswer.trim().split(" ").length < 2) {
          throw new Error("Descriptive question requires a detailed reference answer")
        }
        payload.reference_answer = refAnswer.trim()

        const validCriteria = rubricCriteria.filter(c => c.criterion_text.trim())
        if (validCriteria.length > 0) {
          const totalCritMarks = validCriteria.reduce((sum, c) => sum + (parseFloat(c.max_marks) || 0), 0)
          const targetMarks = Number(qMaxMarks) || 10
          if (Math.abs(totalCritMarks - targetMarks) > 0.001) {
            throw new Error(`Rubric criteria marks total (${totalCritMarks}) must equal question maximum marks (${targetMarks})`)
          }
          payload.rubric_criteria = validCriteria.map((c, idx) => ({
            criterion_text: c.criterion_text.trim(),
            max_marks: parseFloat(c.max_marks) || 1,
            order_index: idx + 1
          }))
        }
      }

      const res = await fetch(API + `/assignments/${managingAsgn.id}/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + t },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Failed to add question")

      setMessage("Question added successfully")
      setQText("")
      setRefAnswer("")
      setRubricCriteria([])
      setMcqOptions(["", "", "", ""])
      setMcqCorrectIndex(0)
      await openQuestionManager(managingAsgn)
      await load(t, role)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add question")
    } finally {
      setQLoading(false)
    }
  }

  // Teacher deletes question
  async function deleteQuestion(qId: number) {
    if (!managingAsgn) return
    const t = localStorage.getItem("token")
    if (!t) return
    try {
      const res = await fetch(API + `/assignments/${managingAsgn.id}/questions/${qId}`, {
        method: "DELETE",
        headers: { Authorization: "Bearer " + t }
      })
      if (!res.ok) throw new Error("Failed to delete question")
      setMessage("Question deleted")
      openQuestionManager(managingAsgn)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete question")
    }
  }

  // Student selects an assessment to submit
  async function toggleStudentSubmit(asgnId: number) {
    if (selected === asgnId) {
      setSelected(null)
      setExamQuestions([])
      setExamAnswers({})
      setEvalResult(null)
      return
    }
    setSelected(asgnId)
    setEvalResult(null)
    setAnswer("")
    setSubmissionFile(null)
    const t = localStorage.getItem("token")
    if (!t) return
    setLoadingQuestions(true)
    try {
      const res = await fetch(API + `/assignments/${asgnId}/questions`, { headers: { Authorization: "Bearer " + t } })
      if (res.ok) {
        const qList = await res.json()
        setExamQuestions(qList)
        const initAnswers: Record<number, { selected_option_id?: number; student_answer?: string }> = {}
        qList.forEach((q: Question) => {
          initAnswers[q.id] = q.question_type === "mcq" ? {} : { student_answer: "" }
        })
        setExamAnswers(initAnswers)
      } else {
        setExamQuestions([])
      }
    } catch {
      setExamQuestions([])
    } finally {
      setLoadingQuestions(false)
    }
  }

  // Student views their evaluated result for a submitted assessment
  async function viewSubmittedResult(asgnId: number) {
    if (selected === asgnId && evalResult) {
      setSelected(null)
      setEvalResult(null)
      return
    }
    const t = localStorage.getItem("token")
    if (!t) return
    setSelected(asgnId)
    setEvalResult(null)
    setError("")
    try {
      const subsRes = await fetch(API + "/my-submissions", { headers: { Authorization: "Bearer " + t } })
      if (subsRes.ok) {
        const subs = await subsRes.json()
        const sub = subs.find((s: { assignment_id: number }) => s.assignment_id === asgnId)
        if (sub) {
          const evalRes = await fetch(API + `/submissions/${sub.id}/evaluation`, { headers: { Authorization: "Bearer " + t } })
          if (evalRes.ok) {
            setEvalResult(await evalRes.json())
          }
        }
      }
    } catch {
      setError("Failed to load result")
    }
  }

  // Student submits standard assignment or auto-evaluated exam
  async function submitExam(asgnId: number) {
    const t = localStorage.getItem("token")
    if (!t || submittingExam) return
    setSubmittingExam(true)
    setError("")
    try {
      if (examQuestions.length > 0) {
        // Structured auto-evaluated exam submission
        const answersList = Object.entries(examAnswers).map(([qid, ans]) => ({
          question_id: Number(qid),
          selected_option_id: ans.selected_option_id || null,
          student_answer: ans.student_answer || ""
        }))

        const res = await fetch(API + `/assignments/${asgnId}/submit-exam`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + t },
          body: JSON.stringify({ assignment_id: asgnId, answers: answersList })
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || "Exam submission failed")

        setEvalResult(data)
        setMessage("Exam submitted & automatically evaluated successfully!")
        await load(t, "student")
      } else {
        // Standard legacy assignment submission
        if (!answer.trim() && !submissionFile) { setError("Write an answer or upload a PDF"); return }
        const b = new FormData()
        b.append("assignment_id", String(asgnId))
        b.append("answer", answer)
        if (submissionFile) b.append("file", submissionFile)
        const r = await fetch(API + "/submissions", { method: "POST", headers: { Authorization: "Bearer " + t }, body: b })
        const d = await r.json()
        if (!r.ok) throw new Error(d.detail || "Submission failed")
        setMessage("Submission successful")
        setSelected(null)
        setAnswer("")
        setSubmissionFile(null)
        await load(t, "student")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed")
    } finally {
      setSubmittingExam(false)
    }
  }

  async function openPdf(id: string) {
    const t = localStorage.getItem("token")
    if (!t) return navigate("/login")
    try {
      const r = await fetch(API + "/resources/" + id + "/download", { headers: { Authorization: "Bearer " + t } })
      if (!r.ok) throw new Error("Unable to open PDF")
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      window.open(url, "_blank", "noopener,noreferrer")
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to open PDF")
    }
  }

  function fmt(v: string | null) {
    return v ? new Date(v).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "No deadline"
  }

  function remaining(v: string | null) {
    if (!v) return ""
    const ms = new Date(v).getTime() - nowTime
    if (ms <= 0) return "Time expired"
    const s = Math.floor(ms / 1000), d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60
    return d ? `${d}d ${h}h ${m}m` : h ? `${h}h ${m}m` : m ? `${m}m ${sec}s` : `${sec}s`
  }

  function logout() { localStorage.clear(); navigate("/login") }

  return (
    <div className="min-h-screen bg-[#070b14] text-white">
      <aside className="fixed left-0 top-0 hidden h-screen w-64 border-r border-white/10 bg-[#0b101a] p-5 lg:block">
        <Brand />
        <nav className="mt-8 space-y-2">
          <Nav onClick={() => navigate(role === "teacher" ? "/teacher" : "/dashboard")} icon={<LayoutDashboard size={18} />} text="Dashboard" />
          <Nav onClick={() => navigate(role === "teacher" ? "/teacher" : "/courses")} icon={<BookOpen size={18} />} text="My Courses" />
          <Nav active onClick={() => {}} icon={<ClipboardList size={18} />} text="Assignments" />
          <Nav onClick={() => navigate("/marks")} icon={<Award size={18} />} text={role === "teacher" ? "Student Marks" : "Marks"} />
          <Nav onClick={() => navigate("/search")} icon={<Search size={18} />} text="AI Search" />
        </nav>
        <button onClick={logout} className="nav absolute bottom-6 left-5 right-5"><LogOut size={18} />Logout</button>
      </aside>

      <main className="lg:ml-64">
        <header className="border-b border-white/10 px-6 py-5 lg:px-10">
          <p className="text-sm text-white/40">{role === "teacher" ? "Teacher" : "Student"}</p>
          <h2 className="mt-1 text-2xl font-semibold">Assignments & Tests</h2>
        </header>

        <section className="p-6 lg:p-10">
          <div className="flex flex-wrap justify-between gap-3">
            <div>
              <h3 className="text-xl font-semibold">{role === "teacher" ? "Manage Assessments" : "Your Assessments"}</h3>
              <p className="mt-1 text-sm text-white/40">Assignments, tests, automatic evaluation, and question authoring.</p>
            </div>
            {role === "teacher" && (
              <button onClick={() => setShow(true)} className="flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-medium text-black">
                <Plus size={17} />Create Assessment
              </button>
            )}
          </div>

          {message && <Msg text={message} ok />}
          {error && <Msg text={error} />}

          {/* Teacher: Create Assessment Form */}
          {show && (
            <div className="mt-6 rounded-2xl border border-white/10 p-6">
              <div className="mb-6 flex justify-between">
                <h3 className="font-semibold">Create Assessment</h3>
                <button onClick={() => setShow(false)}><X size={19} /></button>
              </div>
              <form onSubmit={create} className="space-y-5">
                <Field label="Course">
                  <select value={courseId} onChange={e => setCourseId(e.target.value)} className="input">
                    {courses.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
                  </select>
                </Field>
                <Field label="Type">
                  <select value={type} onChange={e => setType(e.target.value)} className="input">
                    <option value="assignment">Assignment</option>
                    <option value="test">Test</option>
                  </select>
                </Field>
                <Field label="Title">
                  <input value={title} onChange={e => setTitle(e.target.value)} required className="input" placeholder="e.g. DBMS Midterm Exam" />
                </Field>
                <Field label="Instructions">
                  <textarea value={description} onChange={e => setDescription(e.target.value)} required rows={4} className="input resize-none" placeholder="Add instructions for students..." />
                </Field>
                <div className="grid gap-4 md:grid-cols-3">
                  <Field label="Opens"><DateField inputRef={startRef} value={start} onChange={setStart} onClear={() => setStart("")} /></Field>
                  <Field label="Closes"><DateField inputRef={endRef} value={end} onChange={setEnd} onClear={() => setEnd("")} /></Field>
                  <Field label="Duration (min)"><input type="number" min="1" value={duration} onChange={e => setDuration(e.target.value)} placeholder="60" className="input" /></Field>
                </div>
                <Field label="Handout / Question PDF (optional)">
                  <label className="lms-upload-zone">
                    <input type="file" accept=".pdf,application/pdf" onChange={e => setHandout(e.target.files?.[0] || null)} className="sr-only" />
                    <span className="lms-upload-button"><Upload size={16} />Choose PDF</span>
                    <span className="lms-upload-name">{handout?.name || "No PDF selected"}</span>
                  </label>
                </Field>
                <button disabled={!courseId || creating} className="w-full rounded-xl bg-white py-3 text-sm font-medium text-black disabled:opacity-50">
                  {creating ? "Creating..." : handout ? <><Upload size={15} className="mr-2 inline" />Create & Upload</> : "Create Assessment"}
                </button>
              </form>
            </div>
          )}

          {/* Teacher: Question Management Modal */}
          {managingAsgn && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
              <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-white/15 bg-[#0b101a] p-6 shadow-2xl">
                <div className="flex items-start justify-between border-b border-white/10 pb-4">
                  <div>
                    <span className="text-xs uppercase tracking-wider text-white/40">Question Authoring & Automatic Evaluation</span>
                    <h3 className="mt-1 text-xl font-semibold">{managingAsgn.title}</h3>
                    <p className="text-xs text-white/40">Add MCQs (relational evaluation) or Descriptive questions (pgvector semantic evaluation).</p>
                  </div>
                  <button onClick={() => { setManagingAsgn(null); const t = localStorage.getItem("token"); if (t) load(t, role); }} className="rounded-lg p-1 text-white/50 hover:bg-white/10 hover:text-white"><X size={20} /></button>
                </div>

                {/* Existing Questions List */}
                <div className="mt-6">
                  <h4 className="text-sm font-semibold text-white/80">Existing Questions ({asgnQuestions.length})</h4>
                  {asgnQuestions.length === 0 ? (
                    <p className="mt-2 rounded-xl border border-white/5 bg-white/[0.02] p-4 text-xs text-white/40">No questions added yet. Use the form below to add questions.</p>
                  ) : (
                    <div className="mt-3 space-y-3">
                      {asgnQuestions.map((q, idx) => (
                        <div key={q.id} className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <span className="inline-block rounded-md bg-white/10 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-white/70">
                                {q.question_type} · {q.max_marks} marks
                              </span>
                              <p className="mt-2 text-sm font-medium text-white/90">Q{idx + 1}. {q.question_text}</p>
                              {q.question_type === "mcq" && q.options && (
                                <div className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                                  {q.options.map(opt => (
                                    <div key={opt.id} className={`rounded-lg border px-3 py-1.5 text-xs ${opt.id === q.correct_option_id ? "border-green-400/40 bg-green-400/10 text-green-300" : "border-white/5 text-white/60"}`}>
                                      {opt.id === q.correct_option_id && <CheckCircle2 size={13} className="mr-1.5 inline" />}
                                      {opt.option_text}
                                    </div>
                                  ))}
                                </div>
                              )}
                              {q.question_type === "descriptive" && q.reference_answer && (
                                <div className="mt-2 rounded-lg border border-white/5 bg-black/30 p-2.5 text-xs text-white/60">
                                  <span className="font-semibold text-white/80">Reference Answer: </span>
                                  {q.reference_answer}
                                </div>
                              )}
                              {q.question_type === "descriptive" && q.rubric_criteria && q.rubric_criteria.length > 0 && (
                                <div className="mt-2 space-y-1">
                                  <p className="text-[11px] font-semibold text-white/70">Rubric Criteria ({q.rubric_criteria.reduce((s, c) => s + c.max_marks, 0)} marks):</p>
                                  <div className="space-y-1">
                                    {q.rubric_criteria.map((c, i) => (
                                      <div key={i} className="flex justify-between items-center rounded bg-black/25 px-2.5 py-1 text-[11px] text-white/60">
                                        <span>• {c.criterion_text}</span>
                                        <span className="font-medium text-white/80">{c.max_marks} marks</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                            <button onClick={() => deleteQuestion(q.id)} className="rounded-lg p-2 text-red-400 hover:bg-red-400/10" title="Delete question">
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Add New Question Form */}
                <div className="mt-8 border-t border-white/10 pt-6">
                  <h4 className="text-sm font-semibold text-white/80">Add New Question</h4>
                  <form onSubmit={addQuestion} className="mt-4 space-y-4">
                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => setQType("mcq")}
                        className={`flex-1 rounded-xl py-2.5 text-xs font-medium transition ${qType === "mcq" ? "bg-white text-black" : "border border-white/10 text-white/60 hover:bg-white/5"}`}
                      >
                        Multiple Choice (MCQ)
                      </button>
                      <button
                        type="button"
                        onClick={() => setQType("descriptive")}
                        className={`flex-1 rounded-xl py-2.5 text-xs font-medium transition ${qType === "descriptive" ? "bg-white text-black" : "border border-white/10 text-white/60 hover:bg-white/5"}`}
                      >
                        Descriptive (pgvector Semantic Evaluation)
                      </button>
                    </div>

                    <Field label="Question Text">
                      <input
                        value={qText}
                        onChange={e => setQText(e.target.value)}
                        required
                        className="input"
                        placeholder={qType === "mcq" ? "e.g. Which clause removes duplicates in SQL?" : "e.g. Explain the ACID properties in database management."}
                      />
                    </Field>

                    <div className="w-36">
                      <Field label="Max Marks">
                        <input
                          type="number"
                          min="1"
                          max="100"
                          value={qMaxMarks}
                          onChange={e => setQMaxMarks(e.target.value)}
                          required
                          className="input"
                        />
                      </Field>
                    </div>

                    {qType === "mcq" ? (
                      <div className="space-y-3">
                        <label className="block text-xs font-medium text-white/70">
                          Options (select the radio button next to the correct answer)
                        </label>
                        {mcqOptions.map((opt, idx) => (
                          <div key={idx} className="flex items-center gap-3">
                            <input
                              type="radio"
                              name="mcq_correct_option"
                              checked={mcqCorrectIndex === idx}
                              onChange={() => setMcqCorrectIndex(idx)}
                              className="h-4 w-4 accent-green-400"
                              title="Mark as correct option"
                            />
                            <input
                              value={opt}
                              onChange={e => {
                                const next = [...mcqOptions]
                                next[idx] = e.target.value
                                setMcqOptions(next)
                              }}
                              required={idx < 2}
                              className="input flex-1"
                              placeholder={`Option ${idx + 1}`}
                            />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <Field label="Teacher Reference Answer (stored & embedded with pgvector for semantic cosine similarity)">
                          <textarea
                            value={refAnswer}
                            onChange={e => setRefAnswer(e.target.value)}
                            required
                            rows={4}
                            className="input resize-none"
                            placeholder="Provide the comprehensive model answer students are expected to articulate..."
                          />
                        </Field>

                        {/* Rubric Criteria Builder */}
                        <div className="rounded-xl border border-white/10 bg-black/20 p-4 space-y-3">
                          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                            <div>
                              <h5 className="text-xs font-semibold text-white/90">Grading Rubric / Key Concepts (Optional)</h5>
                              <p className="text-[11px] text-white/50">Break question into criteria. Rubric marks sum must equal Question Max Marks.</p>
                            </div>
                            <button
                              type="button"
                              onClick={generateSuggestedRubric}
                              disabled={suggestingRubric}
                              className="rounded-lg border border-purple-500/30 bg-purple-500/10 px-3 py-1.5 text-[11px] font-medium text-purple-300 hover:bg-purple-500/20 transition disabled:opacity-50"
                            >
                              {suggestingRubric ? "Generating..." : "✨ Suggest Rubric"}
                            </button>
                          </div>

                          {rubricCriteria.length > 0 && (
                            <div className="space-y-2">
                              {rubricCriteria.map((crit, idx) => (
                                <div key={idx} className="flex items-center gap-2">
                                  <input
                                    value={crit.criterion_text}
                                    onChange={e => {
                                      const next = [...rubricCriteria]
                                      next[idx].criterion_text = e.target.value
                                      setRubricCriteria(next)
                                    }}
                                    placeholder={`Criterion ${idx + 1} (e.g. Explains connection setup)`}
                                    className="input flex-1 text-xs py-1.5"
                                  />
                                  <input
                                    type="number"
                                    step="0.5"
                                    min="0.5"
                                    value={crit.max_marks}
                                    onChange={e => {
                                      const next = [...rubricCriteria]
                                      next[idx].max_marks = e.target.value
                                      setRubricCriteria(next)
                                    }}
                                    placeholder="Marks"
                                    className="input w-20 text-xs py-1.5 text-center"
                                  />
                                  <button
                                    type="button"
                                    onClick={() => setRubricCriteria(rubricCriteria.filter((_, i) => i !== idx))}
                                    className="rounded p-1 text-red-400 hover:bg-red-400/10"
                                    title="Remove criterion"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}

                          <div className="flex items-center justify-between pt-1">
                            <button
                              type="button"
                              onClick={() => setRubricCriteria([...rubricCriteria, { criterion_text: "", max_marks: "2" }])}
                              className="rounded-lg border border-white/10 px-3 py-1 text-[11px] text-white/70 hover:bg-white/5"
                            >
                              + Add Criterion
                            </button>
                            {rubricCriteria.length > 0 && (
                              <div className={`text-xs font-medium ${
                                Math.abs(rubricCriteria.reduce((s, c) => s + (parseFloat(c.max_marks) || 0), 0) - (Number(qMaxMarks) || 10)) < 0.001
                                  ? "text-green-400"
                                  : "text-amber-400"
                              }`}>
                                Rubric Total: {rubricCriteria.reduce((s, c) => s + (parseFloat(c.max_marks) || 0), 0)} / {qMaxMarks || 10} marks
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="flex justify-end gap-3 pt-2">
                      <button
                        type="button"
                        onClick={() => { setManagingAsgn(null); const t = localStorage.getItem("token"); if (t) load(t, role); }}
                        className="rounded-xl border border-white/10 px-5 py-2.5 text-xs text-white/60 hover:bg-white/5"
                      >
                        Done
                      </button>
                      <button
                        type="submit"
                        disabled={qLoading}
                        className="rounded-xl bg-white px-6 py-2.5 text-xs font-semibold text-black hover:bg-white/90 disabled:opacity-50"
                      >
                        {qLoading ? "Saving..." : "Add Question"}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>
          )}

          {/* Assessment List */}
          <div className="mt-8 space-y-4">
            {items.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center">
                <ClipboardList className="mx-auto mb-4 text-white/30" size={34} />
                <p className="text-white/60">
                  {role === "teacher"
                    ? "No assessments created yet. Click 'Create Assessment' above to get started."
                    : "No assessments assigned to your enrolled courses yet."}
                </p>
              </div>
            ) : (
              items.map(a => (
              <div key={a.id} className="rounded-2xl border border-white/10 bg-white/[0.035] p-6">
                <div className="flex flex-col gap-4 md:flex-row md:justify-between">
                  <div className="min-w-0">
                    <span className="text-xs uppercase tracking-wider text-white/30">
                      {a.type} · {courses.find(x => x.id === a.course_id)?.title || "Course #" + a.course_id}
                    </span>
                    <h4 className="mt-2 text-lg font-medium">{a.title}</h4>
                    <p className="mt-2 text-sm text-white/40">{a.description}</p>
                    <div className="mt-4 flex flex-wrap gap-4 text-xs text-white/40">
                      <span className="flex items-center gap-1">
                        <Clock size={14} />{a.start_time ? "Opens " + fmt(a.start_time) : "Open now"}
                      </span>
                      <span>Deadline: {fmt(a.deadline)}</span>
                      <span>Duration: {a.duration_minutes ? a.duration_minutes + " min" : "No limit"}</span>
                      {role === "student" && a.status === "open" && !a.submitted && (
                        <span className="text-white/70">Time left: {remaining(a.deadline)}</span>
                      )}
                    </div>
                    {a.handout && (
                      <button onClick={() => openPdf(a.handout!.id)} className="mt-4 flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm hover:bg-white/5">
                        <FileText size={15} />{a.handout.title}<Download size={14} />
                      </button>
                    )}
                  </div>

                  <div className="flex items-start gap-3">
                    {role === "teacher" && (
                      <button
                        onClick={() => openQuestionManager(a)}
                        className="flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-xs font-medium text-white hover:bg-white/10"
                      >
                        <ListChecks size={15} />
                        Manage Questions
                      </button>
                    )}
                    {role === "student" && (
                      <div>
                        <span className="rounded-full bg-white/10 px-3 py-1 text-xs">
                          {a.submitted ? "submitted" : a.status}
                        </span>
                        {a.status === "open" && !a.submitted && (
                          <button
                            onClick={() => toggleStudentSubmit(a.id)}
                            className="mt-3 flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-medium text-black"
                          >
                            <Send size={16} />
                            {selected === a.id ? "Close" : "Take Exam / Submit"}
                          </button>
                        )}
                        {a.submitted && (
                          <button
                            onClick={() => viewSubmittedResult(a.id)}
                            className="mt-3 flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-xs font-medium text-white hover:bg-white/10"
                          >
                            <Award size={15} />
                            {selected === a.id && evalResult ? "Hide Result" : "View Result"}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Student Exam / Assessment Submission & Result Panel */}
                {selected === a.id && (
                  <div className="mt-6 border-t border-white/10 pt-6">
                    {/* Post-submission Evaluated Result Banner */}
                    {evalResult && (
                      <div className="rounded-2xl border border-green-400/30 bg-green-500/10 p-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-xs uppercase tracking-wider text-green-300 font-semibold">Automatic Evaluation Complete</span>
                            <h4 className="mt-1 text-2xl font-bold text-white">Score: {evalResult.total_marks} / {evalResult.max_marks}</h4>
                            <p className="mt-1 text-xs text-white/60">Percentage: {evalResult.percentage}% · Status: {evalResult.status}</p>
                          </div>
                          <span className={`rounded-xl px-4 py-2 text-sm font-semibold ${evalResult.status === "Passed" ? "bg-green-400/20 text-green-300" : "bg-red-400/20 text-red-300"}`}>
                            {evalResult.status}
                          </span>
                        </div>
                        {evalResult.questions && evalResult.questions.length > 0 && (
                          <div className="mt-4 divide-y divide-white/10 border-t border-white/10 pt-3">
                            {evalResult.questions.map((q, idx) => (
                              <div key={q.question_id} className="flex items-center justify-between py-2 text-xs">
                                <span className="text-white/80">Question {idx + 1} ({q.question_type.toUpperCase()}): {q.question_text || `Question #${q.question_id}`}</span>
                                <span className="font-semibold text-white">Awarded: {q.awarded_marks} / {q.max_marks} marks</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Interactive Exam Questions (Student View) */}
                    {!a.submitted && a.status === "open" && !evalResult && (
                    loadingQuestions ? (
                      <div className="py-8 text-center text-xs text-white/40">
                        <div className="mx-auto mb-2 h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                        Loading assessment questions...
                      </div>
                    ) : examQuestions.length > 0 ? (
                      <div className="space-y-6">
                        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 text-xs text-white/50">
                          This test contains {examQuestions.length} auto-evaluated question(s). Answer each question below and click submit.
                        </div>

                        {examQuestions.map((q, idx) => (
                          <div key={q.id} className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
                            <div className="flex items-center justify-between">
                              <span className="text-xs uppercase tracking-wider text-white/40">
                                Question {idx + 1} · {q.question_type.toUpperCase()}
                              </span>
                              <span className="rounded-lg bg-white/10 px-2.5 py-1 text-xs font-medium text-white/80">
                                {q.max_marks} marks
                              </span>
                            </div>
                            <p className="mt-3 text-sm font-medium leading-relaxed text-white/90">{q.question_text}</p>

                            {/* MCQ Options (Student never receives correct answer) */}
                            {q.question_type === "mcq" && q.options && (
                              <div className="mt-4 space-y-2.5">
                                {q.options.map(opt => (
                                  <label
                                    key={opt.id}
                                    className={`flex cursor-pointer items-center gap-3 rounded-xl border p-3.5 text-sm transition ${examAnswers[q.id]?.selected_option_id === opt.id ? "border-white bg-white/10 text-white font-medium" : "border-white/10 bg-white/[0.015] text-white/70 hover:bg-white/5"}`}
                                  >
                                    <input
                                      type="radio"
                                      name={`exam_q_${q.id}`}
                                      checked={examAnswers[q.id]?.selected_option_id === opt.id}
                                      onChange={() => setExamAnswers(prev => ({
                                        ...prev,
                                        [q.id]: { ...prev[q.id], selected_option_id: opt.id }
                                      }))}
                                      className="h-4 w-4 accent-white"
                                    />
                                    <span>{opt.option_text}</span>
                                  </label>
                                ))}
                              </div>
                            )}

                            {/* Descriptive Answer (Student writes response, evaluated via pgvector) */}
                            {q.question_type === "descriptive" && (
                              <div className="mt-4">
                                <textarea
                                  value={examAnswers[q.id]?.student_answer || ""}
                                  onChange={e => setExamAnswers(prev => ({
                                    ...prev,
                                    [q.id]: { ...prev[q.id], student_answer: e.target.value }
                                  }))}
                                  rows={5}
                                  className="input resize-none text-sm"
                                  placeholder="Type your descriptive answer here..."
                                />
                              </div>
                            )}
                          </div>
                        ))}

                        <button
                          onClick={() => submitExam(a.id)}
                          disabled={submittingExam}
                          className="mt-6 flex items-center justify-center gap-2 rounded-xl bg-white px-8 py-3.5 text-sm font-semibold text-black hover:bg-white/90 disabled:opacity-50"
                        >
                          <Send size={16} />
                          {submittingExam ? "Evaluating Exam..." : "Submit Exam & Auto-Evaluate"}
                        </button>
                      </div>
                    ) : (
                      /* Standard Assignment Submission Fallback */
                      <div>
                        <textarea
                          value={answer}
                          onChange={e => setAnswer(e.target.value)}
                          rows={6}
                          className="input resize-none"
                          placeholder="Write your answer here..."
                        />
                        <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.02] p-4">
                          <p className="mb-2 text-sm font-medium">Attach PDF submission <span className="text-white/30">(optional)</span></p>
                          <input type="file" accept=".pdf,application/pdf" onChange={e => setSubmissionFile(e.target.files?.[0] || null)} className="block w-full text-sm text-white/50" />
                          <p className="mt-2 text-xs text-white/30">Upload your solved assignment, handwritten work or supporting document.</p>
                        </div>
                        <button
                          onClick={() => submitExam(a.id)}
                          disabled={submittingExam}
                          className="mt-4 rounded-xl bg-white px-6 py-3 text-sm font-medium text-black"
                        >
                          {submittingExam ? "Submitting..." : "Submit Assessment"}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )))}
          </div>
        </section>
      </main>

      <MobileNav role={role} active="assignments" />
    </div>
  )
}

function DateField({ inputRef, value, onChange, onClear }: { inputRef: React.RefObject<HTMLInputElement | null>; value: string; onChange: (v: string) => void; onClear: () => void }) {
  const open = () => { const el = inputRef.current; if (!el) return; try { el.showPicker() } catch { el.focus() } }
  return (
    <div className="lms-date-wrap">
      <button type="button" onClick={open} className="lms-date-display">
        <span>{value ? new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "Select date & time"}</span>
        <span className="lms-date-icon"><Clock size={17} /></span>
      </button>
      <input ref={inputRef} type="datetime-local" value={value} onChange={e => onChange(e.target.value)} className="lms-date-native" />
      {value && <button type="button" onClick={onClear} className="lms-date-clear" aria-label="Clear date">×</button>}
    </div>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-3 px-3 py-4">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-black"><BookOpen size={21} /></div>
      <div><h1 className="font-semibold">LMS</h1><p className="text-xs text-white/40">Learning Platform</p></div>
    </div>
  )
}

function Nav({ onClick, active, icon, text }: { onClick: () => void; active?: boolean; icon: React.ReactNode; text: string }) {
  return <button onClick={onClick} className={"nav " + (active ? "active" : "")}>{icon}{text}</button>
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="mb-2 block text-sm text-white/60">{label}</label>{children}</div>
}

function Msg({ text, ok = false }: { text: string; ok?: boolean }) {
  return (
    <div className={"mt-6 rounded-xl border px-4 py-3 text-sm " + (ok ? "border-green-400/20 bg-green-400/10 text-green-300" : "border-red-400/20 bg-red-400/10 text-red-300")}>
      {text}
    </div>
  )
}