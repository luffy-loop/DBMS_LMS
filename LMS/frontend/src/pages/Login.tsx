import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { BookOpen, ArrowLeft } from "lucide-react"

const API = "http://127.0.0.1:8000"


export default function Login() {
  const [rollNo, setRollNo] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function login(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setLoading(true)

    try {
      const res = await fetch(`${API}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          roll_no: rollNo,
          password,
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "Login failed")
      }

      localStorage.setItem("token", data.token)
      localStorage.setItem("role", data.role)
      localStorage.setItem("name", data.name)
      localStorage.setItem("userId", data.id)

      if (data.role === "teacher") {
        navigate("/teacher")
      } else if (data.role === "admin") {
        navigate("/admin")
      } else {
        navigate("/dashboard")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#070b14] text-white flex items-center justify-center px-6">

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
            Welcome back
          </h1>

          <p className="mt-2 text-sm text-white/40">
            Sign in to continue to your LMS
          </p>

        </div>

        <form
          onSubmit={login}
          className="rounded-3xl border border-white/10 bg-white/[0.035] p-8 backdrop-blur-xl"
        >

          <div className="space-y-5">

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
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none transition placeholder:text-white/20 focus:border-white/30"
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
                placeholder="Enter your password"
                required
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none transition placeholder:text-white/20 focus:border-white/30"
              />
            </div>

          </div>

          {error && (
            <div className="mt-5 rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-7 w-full rounded-xl bg-white py-3 text-sm font-medium text-black transition hover:bg-white/90 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>

          <p className="mt-6 text-center text-sm text-white/40">
            Don't have an account?{" "}

            <button
              type="button"
              onClick={() => navigate("/register")}
              className="text-white hover:underline"
            >
              Create one
            </button>
          </p>

        </form>

      </div>

    </div>
  )
}