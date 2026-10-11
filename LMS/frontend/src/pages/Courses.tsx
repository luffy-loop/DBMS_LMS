import { useCallback, useEffect, useState } from "react"
import { BookOpen, CheckCircle2, Loader2, RefreshCw, Users } from "lucide-react"
import { useNavigate } from "react-router-dom"
import AppLayout from "../components/AppLayout"
import { apiJson } from "../api"

type Course = { id: number; title: string; description: string | null; teacher_id?: number }

export default function Courses() {
  const navigate = useNavigate()
  const role = sessionStorage.getItem("role") || "student"
  const [courses, setCourses] = useState<Course[]>([])
  const [enrolledIds, setEnrolledIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [busyCourseId, setBusyCourseId] = useState<number | null>(null)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const [allCourses, myCourses] = await Promise.all([
        apiJson<Course[]>("/courses?page_size=100"),
        apiJson<Course[]>("/my-courses"),
      ])
      setEnrolledIds(new Set(myCourses.map(course => course.id)))
      const visible = role === "teacher"
        ? myCourses
        : allCourses
      setCourses(visible)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load courses")
    } finally {
      setLoading(false)
    }
  }, [role])

  useEffect(() => {
    if (!sessionStorage.getItem("token")) {
      navigate("/login")
      return
    }
    void load()
  }, [load, navigate])

  async function enroll(course: Course) {
    setBusyCourseId(course.id)
    setError("")
    setMessage("")
    try {
      await apiJson("/enroll", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ course_id: course.id }),
      })
      setEnrolledIds(current => new Set(current).add(course.id))
      setMessage("You are now enrolled in " + course.title + ".")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to enroll in this course")
    } finally {
      setBusyCourseId(null)
    }
  }

  return (
    <AppLayout
      title="Course Library"
      subtitle={role === "teacher" ? "Teaching Workspace" : "Learning Materials"}
    >
      <section className="lms-grid min-h-[calc(100vh-76px)] p-4 sm:p-6 lg:p-10">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold">
                {role === "student" ? "Available Courses" : "My Courses"}
              </h2>
              <p className="mt-1 text-sm text-white/45">
                Browse available courses and open a course to start learning.
              </p>
            </div>
            <button onClick={() => void load()} disabled={loading} className="lms-btn-secondary rounded-xl px-4 py-2.5 text-sm disabled:opacity-50">
              <RefreshCw size={15} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>

          {error && (
            <div role="alert" className="mt-5 rounded-xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">
              {error}
            </div>
          )}
          {message && (
            <div role="status" className="mt-5 rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-300">
              {message}
            </div>
          )}

          {loading ? (
            <div className="mt-8 flex items-center gap-3 text-sm text-white/45">
              <Loader2 size={18} className="animate-spin" /> Loading courses...
            </div>
          ) : courses.length ? (
            <div className="mt-8 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {courses.map(course => {
                const enrolled = enrolledIds.has(course.id)
                return (
                  <article key={course.id} className="lms-card flex flex-col rounded-2xl p-5">
                    <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-violet-300/15 bg-violet-300/10 text-violet-200">
                      <BookOpen size={20} />
                    </div>
                    <h3 className="font-semibold">{course.title}</h3>
                    <p className="mt-2 flex-1 whitespace-pre-wrap text-sm leading-6 text-white/45">
                      {course.description || "No course description provided."}
                    </p>
                    {role === "student" ? (
                      <button
                        onClick={() => void enroll(course)}
                        disabled={enrolled || busyCourseId !== null}
                        className="lms-btn-primary mt-5 flex w-full items-center justify-center rounded-xl px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {busyCourseId === course.id ? <Loader2 size={16} className="animate-spin" /> : enrolled ? <CheckCircle2 size={16} /> : <Users size={16} />}
                        {busyCourseId === course.id ? "Enrolling..." : enrolled ? "Enrolled" : "Enroll in course"}
                      </button>
                    ) : (
                      <p className="mt-5 text-xs text-white/35">Course ID: {course.id}</p>
                    )}
                  </article>
                )
              })}
            </div>
          ) : (
            <div className="lms-card mt-8 rounded-2xl p-8 text-center">
              <BookOpen size={28} className="mx-auto text-white/35" />
              <h3 className="mt-4 font-semibold">No courses available yet</h3>
              <p className="mt-2 text-sm text-white/45">
                Courses will appear here when they are available to your account.
              </p>
              {role === "teacher" && (
                <button onClick={() => navigate("/teacher")} className="lms-btn-primary mt-5 rounded-xl px-4 py-3 text-sm">
                  Go to teaching workspace
                </button>
              )}
            </div>
          )}
        </div>
      </section>
    </AppLayout>
  )
}
