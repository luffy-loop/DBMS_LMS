import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { API } from "../config"
import { BookOpen, ArrowLeft } from "lucide-react"



export default function Register() {
  const [name, setName] = useState("")
  const [rollNo, setRollNo] = useState("")
  const [password, setPassword] = useState("")
  const [role, setRole] = useState("student")
  const [section, setSection] = useState("A1")
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function register(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setMessage("")
    setLoading(true)

    try {
      const res = await fetch(`${API}/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name,
          roll_no: rollNo,
          password,
          role,
          section,
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "Registration failed")
      }

      setMessage("Registration successful. You can now sign in.")
      setName("")
      setRollNo("")
      setPassword("")
      setRole("student")
      setSection("A1")
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Registration failed"
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="lms-auth min-h-screen bg-[#070b14] text-white flex items-center justify-center px-6">

      <button
        onClick={() => navigate("/")}
        className="absolute left-6 top-6 flex items-center gap-2 text-sm text-white/50 hover:text-white"
      >
        <ArrowLeft size={17} />
        Back
      </button>

      <div className="w-full max-w-md">

        <div className="mb-8 text-center">

          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-black">
            <BookOpen size={27} />
          </div>

          <h1 className="text-3xl font-semibold">
            Create your account
          </h1>

          <p className="mt-2 text-sm text-white/40">
            Join the LMS platform
          </p>
          <div className="mt-4 inline-flex items-center rounded-full border border-violet-400/15 bg-violet-400/5 px-3 py-1.5 text-xs text-violet-200">
            Faculty sections are assigned by Admin
          </div>

        </div>

        <form
          onSubmit={register}
          className="rounded-3xl border border-white/10 bg-white/[0.035] p-8 backdrop-blur-xl"
        >

          <div className="space-y-5">

            <div>
              <label className="mb-2 block text-sm text-white/60">
                Full Name
              </label>

              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your name"
                required
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-white/30"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm text-white/60">
                College Roll Number
              </label>

              <input
                type="text"
                value={rollNo}
                onChange={(e) => setRollNo(e.target.value)}
                placeholder="Enter your college roll number"
                required
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-white/30"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm text-white/60">
                Password
              </label>

              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Create a password"
                required
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-white/30"
              />
            </div>

            {role === "student" ? (
              <div>
                <label className="mb-2 block text-sm text-white/60">Section / Batch</label>
                <select value={section} onChange={(e) => setSection(e.target.value)} className="lms-input">
                  {["A1","A2","A3","A4","A5","A6","A7"].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <p className="mt-2 text-xs text-white/30">Students choose their registered section.</p>
              </div>
            ) : role === "teacher" ? (
              <div className="rounded-xl border border-violet-400/15 bg-violet-400/5 px-4 py-3 text-sm">
                <p className="text-violet-200">Section assigned by Admin</p>
                <p className="mt-1 text-xs text-white/35">Your faculty section will be allotted after registration.</p>
              </div>
            ) : null}

            <div>
              <label className="mb-2 block text-sm text-white/60">
                Role
              </label>

              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-[#0d1320] px-4 py-3 text-sm outline-none focus:border-white/30"
              >
                <option value="student">Student</option>
                <option value="teacher">Teacher</option>
                <option value="admin">Admin</option>
              </select>
            </div>

          </div>

          {error && (
            <div className="mt-5 rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {message && (
            <div className="mt-5 rounded-xl border border-green-400/20 bg-green-400/10 px-4 py-3 text-sm text-green-300">
              {message}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-7 w-full rounded-xl bg-white py-3 text-sm font-medium text-black transition hover:bg-white/90 disabled:opacity-50"
          >
            {loading ? "Creating account..." : "Create Account"}
          </button>

          <p className="mt-6 text-center text-sm text-white/40">
            Already have an account?{" "}

            <button
              type="button"
              onClick={() => navigate("/login")}
              className="text-white hover:underline"
            >
              Sign in
            </button>
          </p>

        </form>

      </div>

    </div>
  )
}