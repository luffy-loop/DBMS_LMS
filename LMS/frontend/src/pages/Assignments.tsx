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
  X,
  Send
} from "lucide-react"
import { useNavigate } from "react-router-dom"

const API = "http://127.0.0.1:8000"

type Course = {
  id: number
  title: string
  description: string
  teacher_id: number
}

type Assignment = {
  id: number
  title: string
  description: string
  course_id: number
  teacher_id: number
}

export default function Assignments() {
  const navigate = useNavigate()

  const [role, setRole] = useState("")
  const [courses, setCourses] = useState<Course[]>([])
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [courseId, setCourseId] = useState("")
  const [answer, setAnswer] = useState("")
  const [selectedAssignment, setSelectedAssignment] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  const name = localStorage.getItem("name") || "User"

  useEffect(() => {
    const token = localStorage.getItem("token")
    const storedRole = localStorage.getItem("role")

    if (!token) {
      navigate("/login")
      return
    }

    setRole(storedRole || "student")
    loadData(token, storedRole || "student")
  }, [navigate])

  async function loadData(token: string, currentRole: string) {
    try {
      const coursesRes = await fetch(`${API}/courses`)

      if (!coursesRes.ok) {
        throw new Error("Failed to load courses")
      }

      const allCourses: Course[] = await coursesRes.json()

      if (currentRole === "teacher") {
        const teacherId = Number(localStorage.getItem("userId"))
        const teacherCourses = allCourses.filter(
          (course) => course.teacher_id === teacherId
        )

        setCourses(teacherCourses)

        if (teacherCourses.length > 0) {
          setCourseId(String(teacherCourses[0].id))
        }

        const results = await Promise.all(
          teacherCourses.map((course) =>
            fetch(`${API}/assignments/${course.id}`)
          )
        )

        const data = await Promise.all(
          results.map((res) => (res.ok ? res.json() : []))
        )

        setAssignments(data.flat())
      } else {
        const myCoursesRes = await fetch(`${API}/my-courses`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })

        if (!myCoursesRes.ok) {
          throw new Error("Failed to load enrolled courses")
        }

        const myCourses: Course[] = await myCoursesRes.json()
        setCourses(myCourses)

        const results = await Promise.all(
          myCourses.map((course) =>
            fetch(`${API}/assignments/${course.id}`)
          )
        )

        const data = await Promise.all(
          results.map((res) => (res.ok ? res.json() : []))
        )

        setAssignments(data.flat())
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load assignments")
    } finally {
      setLoading(false)
    }
  }

  async function createAssignment(e: React.FormEvent) {
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
      const res = await fetch(`${API}/assignments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          title,
          description,
          course_id: Number(courseId)
        })
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "Failed to create assignment")
      }

      setMessage("Assignment created successfully")
      setTitle("")
      setDescription("")
      setShowForm(false)

      await loadData(token, "teacher")
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to create assignment"
      )
    } finally {
      setCreating(false)
    }
  }

  async function submitAssignment(assignmentId: number) {
    const token = localStorage.getItem("token")

    if (!token) {
      navigate("/login")
      return
    }

    if (!answer.trim()) {
      setError("Please enter your answer")
      return
    }

    setSubmitting(true)
    setMessage("")
    setError("")

    try {
      const res = await fetch(`${API}/submissions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          assignment_id: assignmentId,
          answer
        })
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "Submission failed")
      }

      setMessage("Assignment submitted successfully")
      setAnswer("")
      setSelectedAssignment(null)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Submission failed"
      )
    } finally {
      setSubmitting(false)
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
            onClick={() =>
              navigate(role === "teacher" ? "/teacher" : "/dashboard")
            }
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
          >
            <LayoutDashboard size={18} />
            Dashboard
          </button>

          <button
            onClick={() =>
              navigate(role === "teacher" ? "/teacher" : "/courses")
            }
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
          >
            <BookOpen size={18} />
            My Courses
          </button>

          <button
            className="flex w-full items-center gap-3 rounded-xl bg-white/10 px-4 py-3 text-sm"
          >
            <ClipboardList size={18} />
            Assignments
          </button>

          <button
            onClick={() => navigate("/marks")}
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
          >
            <Award size={18} />
            {role === "teacher" ? "Student Marks" : "Marks"}
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
              {role === "teacher" ? "Teacher" : "Student"}
            </p>

            <h2 className="mt-1 text-2xl font-semibold">
              Assignments
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

          <div className="flex items-center justify-between">

            <div>
              <h3 className="text-xl font-semibold">
                {role === "teacher"
                  ? "Manage Assignments"
                  : "Your Assignments"}
              </h3>

              <p className="mt-1 text-sm text-white/40">
                {role === "teacher"
                  ? "Create assignments for your courses."
                  : "Complete and submit your course assignments."}
              </p>
            </div>

            {role === "teacher" && (
              <button
                onClick={() => {
                  setMessage("")
                  setError("")
                  setShowForm(true)
                }}
                className="flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-medium text-black hover:bg-white/90"
              >
                <Plus size={17} />
                Create Assignment
              </button>
            )}

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

          {showForm && role === "teacher" && (
            <div className="mt-6 rounded-2xl border border-white/10 bg-white/[0.035] p-6">

              <div className="mb-6 flex items-center justify-between">

                <div>
                  <h3 className="text-lg font-semibold">
                    Create Assignment
                  </h3>

                  <p className="mt-1 text-sm text-white/40">
                    Add an assignment to one of your courses.
                  </p>
                </div>

                <button
                  onClick={() => setShowForm(false)}
                  className="rounded-lg p-2 text-white/40 hover:bg-white/5 hover:text-white"
                >
                  <X size={19} />
                </button>

              </div>

              {courses.length === 0 ? (
                <div className="rounded-xl border border-white/10 p-5 text-sm text-white/40">
                  Create a course first before adding assignments.
                </div>
              ) : (
                <form
                  onSubmit={createAssignment}
                  className="space-y-5"
                >

                  <div>
                    <label className="mb-2 block text-sm text-white/60">
                      Course
                    </label>

                    <select
                      value={courseId}
                      onChange={(e) => setCourseId(e.target.value)}
                      required
                      className="w-full rounded-xl border border-white/10 bg-[#0d1320] px-4 py-3 text-sm outline-none focus:border-white/30"
                    >
                      {courses.map((course) => (
                        <option
                          key={course.id}
                          value={course.id}
                        >
                          {course.title}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="mb-2 block text-sm text-white/60">
                      Assignment Title
                    </label>

                    <input
                      type="text"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="e.g. SQL Queries Practice"
                      required
                      className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-white/30"
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm text-white/60">
                      Description
                    </label>

                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Describe the assignment..."
                      required
                      rows={4}
                      className="w-full resize-none rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-white/30"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={creating}
                    className="w-full rounded-xl bg-white py-3 text-sm font-medium text-black hover:bg-white/90 disabled:opacity-50"
                  >
                    {creating
                      ? "Creating Assignment..."
                      : "Create Assignment"}
                  </button>

                </form>
              )}

            </div>
          )}

          <div className="mt-8">

            {loading ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center text-white/40">
                Loading assignments...
              </div>
            ) : assignments.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center">

                <ClipboardList
                  className="mx-auto mb-4 text-white/30"
                  size={34}
                />

                <p className="text-white/60">
                  No assignments yet
                </p>

                <p className="mt-1 text-sm text-white/30">
                  {role === "teacher"
                    ? "Create an assignment for your students."
                    : "Assignments from your courses will appear here."}
                </p>

              </div>
            ) : (
              <div className="space-y-4">

                {assignments.map((assignment) => {

                  const course = courses.find(
                    (c) => c.id === assignment.course_id
                  )

                  return (
                    <div
                      key={assignment.id}
                      className="rounded-2xl border border-white/10 bg-white/[0.035] p-6"
                    >

                      <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">

                        <div>

                          <span className="text-xs text-white/30">
                            {course?.title || `Course #${assignment.course_id}`}
                          </span>

                          <h4 className="mt-2 text-lg font-medium">
                            {assignment.title}
                          </h4>

                          <p className="mt-2 max-w-2xl text-sm leading-6 text-white/40">
                            {assignment.description}
                          </p>

                        </div>

                        {role === "student" && (
                          <button
                            onClick={() => {
                              setSelectedAssignment(
                                selectedAssignment === assignment.id
                                  ? null
                                  : assignment.id
                              )
                              setAnswer("")
                              setMessage("")
                              setError("")
                            }}
                            className="flex shrink-0 items-center justify-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-medium text-black hover:bg-white/90"
                          >
                            <Send size={16} />
                            {selectedAssignment === assignment.id
                              ? "Close"
                              : "Submit"}
                          </button>
                        )}

                      </div>

                      {selectedAssignment === assignment.id && (
                        <div className="mt-6 border-t border-white/10 pt-6">

                          <label className="mb-2 block text-sm text-white/60">
                            Your Answer
                          </label>

                          <textarea
                            value={answer}
                            onChange={(e) => setAnswer(e.target.value)}
                            placeholder="Write your answer here..."
                            rows={6}
                            className="w-full resize-none rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-white/30"
                          />

                          <button
                            onClick={() =>
                              submitAssignment(assignment.id)
                            }
                            disabled={submitting}
                            className="mt-4 rounded-xl bg-white px-6 py-3 text-sm font-medium text-black hover:bg-white/90 disabled:opacity-50"
                          >
                            {submitting
                              ? "Submitting..."
                              : "Submit Assignment"}
                          </button>

                        </div>
                      )}

                    </div>
                  )
                })}

              </div>
            )}

          </div>

        </section>

      </main>

    </div>
  )
}