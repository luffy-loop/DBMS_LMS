import { useEffect, useState } from "react"
import {
  BookOpen,
  LayoutDashboard,
  ClipboardList,
  Award,
  Search,
  LogOut,
  User,
  Plus,
  X
} from "lucide-react"
import { useNavigate } from "react-router-dom"

const API = "http://127.0.0.1:8000"

type Course = {
  id: number
  title: string
  description: string
  teacher_id: number
}

export default function TeacherDashboard() {
  const navigate = useNavigate()

  const [courses, setCourses] = useState<Course[]>([])
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  const name = localStorage.getItem("name") || "Teacher"
  const role = localStorage.getItem("role")

  useEffect(() => {
    const token = localStorage.getItem("token")

    if (!token) {
      navigate("/login")
      return
    }

    if (role !== "teacher") {
      navigate("/dashboard")
      return
    }

    loadCourses(token)
  }, [navigate, role])

  async function loadCourses(token: string) {
    try {
      const res = await fetch(`${API}/courses`)

      if (res.ok) {
        const data = await res.json()

        const teacherId = Number(localStorage.getItem("userId"))

        setCourses(
          data.filter((course: Course) => course.teacher_id === teacherId)
        )
      }
    } catch {
      setError("Failed to load courses")
    } finally {
      setLoading(false)
    }
  }

  async function createCourse(e: React.FormEvent) {
    e.preventDefault()

    const token = localStorage.getItem("token")

    if (!token) {
      navigate("/login")
      return
    }

    setCreating(true)
    setMessage("")
    setError("")

    try {
      const res = await fetch(`${API}/courses`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          title,
          description
        })
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "Failed to create course")
      }

      setMessage("Course created successfully")
      setTitle("")
      setDescription("")
      setShowForm(false)

      await loadCourses(token)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create course"
      )
    } finally {
      setCreating(false)
    }
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
            className="flex w-full items-center gap-3 rounded-xl bg-white/10 px-4 py-3 text-sm"
          >
            <LayoutDashboard size={18} />
            Dashboard
          </button>

          <button
            onClick={() => navigate("/teacher")}
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
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
            onClick={() => navigate("/marks")}
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
          >
            <Award size={18} />
            Student Marks
          </button>

          <button
            onClick={() => navigate("/search")}
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
              Teacher Dashboard
            </p>

            <h2 className="mt-1 text-2xl font-semibold">
              Welcome back, {name}
            </h2>
          </div>

          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5">
            <User size={18} />
          </div>

        </header>

        <section className="p-6 lg:p-10">

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">

            <StatCard
              icon={<BookOpen size={20} />}
              title="My Courses"
              value={courses.length}
            />

            <StatCard
              icon={<ClipboardList size={20} />}
              title="Assignments"
              value={0}
            />

            <StatCard
              icon={<Award size={20} />}
              title="Student Submissions"
              value={0}
            />

          </div>

          <div className="mt-10 flex items-center justify-between">

            <div>
              <h3 className="text-xl font-semibold">
                My Courses
              </h3>

              <p className="mt-1 text-sm text-white/40">
                Manage the courses you teach.
              </p>
            </div>

            <button
              onClick={() => {
                setMessage("")
                setError("")
                setShowForm(true)
              }}
              className="flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-medium text-black transition hover:bg-white/90"
            >
              <Plus size={17} />
              Create Course
            </button>

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

          {showForm && (
            <div className="mt-6 rounded-2xl border border-white/10 bg-white/[0.035] p-6">

              <div className="mb-6 flex items-center justify-between">

                <div>
                  <h3 className="text-lg font-semibold">
                    Create New Course
                  </h3>

                  <p className="mt-1 text-sm text-white/40">
                    Add a course for students to enroll in.
                  </p>
                </div>

                <button
                  onClick={() => setShowForm(false)}
                  className="rounded-lg p-2 text-white/40 hover:bg-white/5 hover:text-white"
                >
                  <X size={19} />
                </button>

              </div>

              <form
                onSubmit={createCourse}
                className="space-y-5"
              >

                <div>
                  <label className="mb-2 block text-sm text-white/60">
                    Course Title
                  </label>

                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Database Management Systems"
                    required
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-white/30"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm text-white/60">
                    Course Description
                  </label>

                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe the course..."
                    required
                    rows={4}
                    className="w-full resize-none rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-white/30"
                  />
                </div>

                <button
                  type="submit"
                  disabled={creating}
                  className="w-full rounded-xl bg-white py-3 text-sm font-medium text-black transition hover:bg-white/90 disabled:opacity-50"
                >
                  {creating ? "Creating Course..." : "Create Course"}
                </button>

              </form>

            </div>
          )}

          <div className="mt-6">

            {loading ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center text-white/40">
                Loading courses...
              </div>
            ) : courses.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center">

                <BookOpen
                  className="mx-auto mb-4 text-white/30"
                  size={34}
                />

                <p className="text-white/60">
                  No courses created yet
                </p>

                <p className="mt-1 text-sm text-white/30">
                  Create your first course using the button above.
                </p>

              </div>
            ) : (
              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">

                {courses.map((course) => (
                  <div
                    key={course.id}
                    className="rounded-2xl border border-white/10 bg-white/[0.035] p-6 transition hover:border-white/20 hover:bg-white/[0.05]"
                  >

                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10">
                      <BookOpen size={20} />
                    </div>

                    <h4 className="mt-6 text-lg font-medium">
                      {course.title}
                    </h4>

                    <p className="mt-2 text-sm leading-6 text-white/40">
                      {course.description}
                    </p>

                    <p className="mt-5 text-xs text-white/30">
                      Course ID: {course.id}
                    </p>

                  </div>
                ))}

              </div>
            )}

          </div>

        </section>

      </main>

    </div>
  )
}

function StatCard({
  icon,
  title,
  value
}: {
  icon: React.ReactNode
  title: string
  value: number
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">

      <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-xl bg-white/10">
        {icon}
      </div>

      <p className="text-sm text-white/40">
        {title}
      </p>

      <p className="mt-1 text-2xl font-semibold">
        {value}
      </p>

    </div>
  )
}