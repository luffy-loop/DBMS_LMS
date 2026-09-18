import { useEffect, useState } from "react"
import {
  BookOpen,
  LayoutDashboard,
  ClipboardList,
  Award,
  Search,
  LogOut,
  User,
  Check
} from "lucide-react"
import { useNavigate } from "react-router-dom"

const API = "http://127.0.0.1:8000"

type Course = {
  id: number
  title: string
  description: string
  teacher_id: number
}

export default function Courses() {
  const navigate = useNavigate()

  const [courses, setCourses] = useState<Course[]>([])
  const [myCourses, setMyCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  const name = localStorage.getItem("name") || "User"
  const role = localStorage.getItem("role") || "student"

  useEffect(() => {
    const token = localStorage.getItem("token")

    if (!token) {
      navigate("/login")
      return
    }

    loadCourses(token)
  }, [navigate])

  async function loadCourses(token: string) {
    try {
      const [allRes, myRes] = await Promise.all([
        fetch(`${API}/courses`),
        fetch(`${API}/my-courses`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
      ])

      if (allRes.ok) {
        setCourses(await allRes.json())
      }

      if (myRes.ok) {
        setMyCourses(await myRes.json())
      }
    } catch {
      setError("Failed to load courses")
    } finally {
      setLoading(false)
    }
  }

  async function enroll(courseId: number) {
    const token = localStorage.getItem("token")

    if (!token) {
      navigate("/login")
      return
    }

    setMessage("")
    setError("")

    try {
      const res = await fetch(`${API}/enroll`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          course_id: courseId
        })
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "Enrollment failed")
      }

      setMessage("Successfully enrolled in the course")

      await loadCourses(token)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enrollment failed")
    }
  }

  function isEnrolled(courseId: number) {
    return myCourses.some((course) => course.id === courseId)
  }

  function logout() {
    localStorage.clear()
    navigate("/login")
  }

  return (
    <div className="min-h-screen bg-[#070b14] text-white">

      <aside className="fixed left-0 top-0 hidden h-screen w-64 border-r border-white/10 bg-[#0b101a] p-5 lg:block">

        <div className="flex items-center gap-3 px-3 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-black">
            <BookOpen size={21} />
          </div>

          <div>
            <h1 className="font-semibold">LMS</h1>
            <p className="text-xs text-white/40">
              Learning Platform
            </p>
          </div>
        </div>

        <nav className="mt-8 space-y-2">

          <button
            onClick={() => navigate("/dashboard")}
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
          >
            <LayoutDashboard size={18} />
            Dashboard
          </button>

          <button
            className="flex w-full items-center gap-3 rounded-xl bg-white/10 px-4 py-3 text-sm"
          >
            <BookOpen size={18} />
            My Courses
          </button>

          <button
            onClick={() => navigate("/assignments")}
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
            >
            <ClipboardList size={18} />
            Assignments
        </button>

          <button
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
          >
            <Award size={18} />
            Marks
          </button>

          <button
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
          >
            <Search size={18} />
            AI Search
          </button>

        </nav>

        <button
          onClick={logout}
          className="absolute bottom-6 left-5 right-5 flex items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
        >
          <LogOut size={18} />
          Logout
        </button>

      </aside>

      <main className="lg:ml-64">

        <header className="flex items-center justify-between border-b border-white/10 px-6 py-5 lg:px-10">

          <div>
            <p className="text-sm text-white/40">
              Student
            </p>

            <h2 className="mt-1 text-2xl font-semibold">
              My Courses
            </h2>
          </div>

          <div className="flex items-center gap-3">

            <span className="hidden text-sm text-white/40 sm:block">
              {name}
            </span>

            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5">
              <User size={18} />
            </div>

          </div>

        </header>

        <section className="p-6 lg:p-10">

          <div>
            <h3 className="text-xl font-semibold">
              Available Courses
            </h3>

            <p className="mt-1 text-sm text-white/40">
              Explore courses and enroll to start learning.
            </p>
          </div>

          {message && (
            <div className="mt-6 rounded-xl border border-green-400/20 bg-green-400/10 px-4 py-3 text-sm text-green-300">
              {message}
            </div>
          )}

          {error && (
            <div className="mt-6 rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {loading ? (
            <div className="mt-8 rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center text-white/40">
              Loading courses...
            </div>
          ) : courses.length === 0 ? (
            <div className="mt-8 rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center">

              <BookOpen
                className="mx-auto mb-4 text-white/30"
                size={34}
              />

              <p className="text-white/60">
                No courses available
              </p>

              <p className="mt-1 text-sm text-white/30">
                Courses created by teachers will appear here.
              </p>

            </div>
          ) : (
            <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">

              {courses.map((course) => {
                const enrolled = isEnrolled(course.id)

                return (
                  <div
                    key={course.id}
                    className="rounded-2xl border border-white/10 bg-white/[0.035] p-6 transition hover:border-white/20 hover:bg-white/[0.05]"
                  >

                    <div className="flex items-start justify-between">

                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10">
                        <BookOpen size={20} />
                      </div>

                      {enrolled && (
                        <div className="flex items-center gap-1 rounded-full bg-green-400/10 px-3 py-1 text-xs text-green-300">
                          <Check size={13} />
                          Enrolled
                        </div>
                      )}

                    </div>

                    <h4 className="mt-6 text-lg font-medium">
                      {course.title}
                    </h4>

                    <p className="mt-2 min-h-12 text-sm leading-6 text-white/40">
                      {course.description}
                    </p>

                    <button
                      disabled={enrolled}
                      onClick={() => enroll(course.id)}
                      className={`mt-6 w-full rounded-xl py-3 text-sm font-medium transition ${
                        enrolled
                          ? "cursor-default bg-white/5 text-white/30"
                          : "bg-white text-black hover:bg-white/90"
                      }`}
                    >
                      {enrolled ? "Already Enrolled" : "Enroll Now"}
                    </button>

                  </div>
                )
              })}

            </div>
          )}

        </section>

      </main>

    </div>
  )
}