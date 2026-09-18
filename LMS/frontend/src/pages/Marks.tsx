import { useEffect, useState } from "react"
import { BookOpen, LayoutDashboard, ClipboardList, Award, Search, LogOut, User } from "lucide-react"
import { useNavigate } from "react-router-dom"

const API = "http://127.0.0.1:8000"

type Submission = { id: number; assignment_id: number; student_id: number; answer: string; marks: number | null }

export default function Marks() {
  const navigate = useNavigate()
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [loading, setLoading] = useState(true)
  const [marks, setMarks] = useState<Record<number, string>>({})
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const role = localStorage.getItem("role")
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
    } finally { setLoading(false) }
  }

  async function giveMarks(id: number) {
    const token = localStorage.getItem("token")
    const value = marks[id]
    if (!token || !value) return
    const score = Number(value)
    if (!Number.isInteger(score) || score < 0 || score > 100) { setError("Marks must be a whole number from 0 to 100"); return }
    try {
      setError(""); setMessage("")
      const res = await fetch(`${API}/submissions/${id}/marks?marks=${score}`, { method: "PUT", headers: { Authorization: `Bearer ${token}` } })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Failed to update marks")
      setMessage("Marks updated successfully")
      await loadSubmissions(token)
    } catch (err) { setError(err instanceof Error ? err.message : "Failed to update marks") }
  }

  function logout() { localStorage.clear(); navigate("/login") }

  return <div className="min-h-screen bg-[#070b14] text-white">
    <aside className="fixed left-0 top-0 hidden h-screen w-64 border-r border-white/10 bg-[#0b101a] p-5 lg:block">
      <div className="flex items-center gap-3 px-3 py-4"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-black"><BookOpen size={21}/></div><div><h1 className="font-semibold">LMS</h1><p className="text-xs text-white/40">Learning Platform</p></div></div>
      <nav className="mt-8 space-y-2">
        <button onClick={() => navigate(role === "teacher" ? "/teacher" : "/dashboard")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"><LayoutDashboard size={18}/>Dashboard</button>
        <button onClick={() => navigate(role === "teacher" ? "/teacher" : "/courses")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"><BookOpen size={18}/>My Courses</button>
        <button onClick={() => navigate("/assignments")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"><ClipboardList size={18}/>Assignments</button>
        <button className="flex w-full items-center gap-3 rounded-xl bg-white/10 px-4 py-3 text-sm"><Award size={18}/>{role === "teacher" ? "Student Marks" : "Marks"}</button>
        <button onClick={() => navigate("/search")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"><Search size={18}/>AI Search</button>
      </nav>
      <button onClick={logout} className="absolute bottom-6 left-5 right-5 flex items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"><LogOut size={18}/>Logout</button>
    </aside>
    <main className="lg:ml-64">
      <header className="flex items-center justify-between border-b border-white/10 px-6 py-5 lg:px-10"><div><p className="text-sm text-white/40">{role === "teacher" ? "Teacher Marks" : "My Marks"}</p><h2 className="mt-1 text-2xl font-semibold">{role === "teacher" ? "Student Submissions" : "My Marks"}</h2></div><div className="flex items-center gap-3"><span className="hidden text-sm text-white/40 sm:block">{name}</span><div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5"><User size={18}/></div></div></header>
      <section className="p-6 lg:p-10">
        {message && <div className="mb-6 rounded-xl border border-green-400/20 bg-green-400/10 px-4 py-3 text-sm text-green-300">{message}</div>}
        {error && <div className="mb-6 rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-300">{error}</div>}
        {loading ? <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center text-white/40">Loading marks...</div> : submissions.length === 0 ? <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center"><Award className="mx-auto mb-4 text-white/30" size={34}/><p className="text-white/60">{role === "teacher" ? "No pending submissions" : "No marks available yet"}</p></div> : <div className="space-y-5">{submissions.map((submission) => <div key={submission.id} className="rounded-2xl border border-white/10 bg-white/[0.035] p-6"><div className="flex items-start justify-between gap-4"><div><p className="text-xs text-white/30">Submission ID: {submission.id}</p><h3 className="mt-2 text-lg font-medium">Assignment #{submission.assignment_id}</h3>{role === "teacher" && <p className="mt-1 text-sm text-white/40">Student ID: {submission.student_id}</p>}</div>{submission.marks !== null && <div className="rounded-xl bg-white/10 px-4 py-2 text-sm">Marks: <span className="font-semibold">{submission.marks}</span></div>}</div><div className="mt-5 rounded-xl border border-white/10 bg-black/20 p-4"><p className="mb-2 text-xs text-white/30">Answer</p><p className="text-sm leading-6 text-white/70">{submission.answer}</p></div>{role === "teacher" && submission.marks === null && <div className="mt-5 flex gap-3"><input type="number" min="0" max="100" value={marks[submission.id] || ""} onChange={(e) => setMarks((current) => ({ ...current, [submission.id]: e.target.value }))} placeholder="Enter marks" className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-white/30"/><button onClick={() => giveMarks(submission.id)} className="rounded-xl bg-white px-6 py-3 text-sm font-medium text-black hover:bg-white/90">Give Marks</button></div>}</div>)}</div>}
      </section>
    </main>
  </div>
}
