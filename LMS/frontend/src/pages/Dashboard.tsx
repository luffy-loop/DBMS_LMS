import { useEffect, useState } from "react"
import {
  BookOpen,
  ClipboardList,
  CheckCircle2,
  Award,
  LogOut,
  LayoutDashboard,
  Search,
  User
} from "lucide-react"
import { useNavigate } from "react-router-dom"

const API = "http://127.0.0.1:8000"

type Course = {
  id: number
  title: string
  description: string
}

type Submission = {
  id: number
  assignment_id: number
  answer: string
  marks: number | null
}

export default function Dashboard() {
  const navigate = useNavigate()

  const [name, setName] = useState("")
  const [role, setRole] = useState("")
  const [courses, setCourses] = useState<Course[]>([])
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem("token")
    const storedName = localStorage.getItem("name")
    const storedRole = localStorage.getItem("role")

    if (!token) {
      navigate("/login")
      return
    }

    setName(storedName || "User")
    setRole(storedRole || "student")

    if (storedRole === "student") {
      loadStudentData(token)
    } else {
      setLoading(false)
    }
  }, [navigate])

  async function loadStudentData(token: string) {
    try {
      const headers = {
        Authorization: `Bearer ${token}`
      }

      const [coursesRes, submissionsRes] = await Promise.all([
        fetch(`${API}/my-courses`, { headers }),
        fetch(`${API}/my-submissions`, { headers })
      ])

      if (coursesRes.ok) {
        const coursesData = await coursesRes.json()
        setCourses(coursesData)
      }

      if (submissionsRes.ok) {
        const submissionsData = await submissionsRes.json()
        setSubmissions(submissionsData)
      }
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  function logout() {
    localStorage.clear()
    navigate("/login")
  }

  const graded = submissions.filter((s) => s.marks !== null).length

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

          <button className="flex w-full items-center gap-3 rounded-xl bg-white/10 px-4 py-3 text-sm">
            <LayoutDashboard size={18} />
            Dashboard
          </button>

            <button
            onClick={() => navigate("/courses")}
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white"
            >
            <BookOpen size={18} />
            My Courses
            </button>

          <button className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
            <ClipboardList size={18} />
            Assignments
          </button>

          <button className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
            <Award size={18} />
            Marks
          </button>

          <button className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
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
              {role.charAt(0).toUpperCase() + role.slice(1)} Dashboard
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

          {role === "student" && (
            <>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

                <StatCard
                  icon={<BookOpen size={20} />}
                  title="My Courses"
                  value={courses.length}
                />

                <StatCard
                  icon={<ClipboardList size={20} />}
                  title="Submissions"
                  value={submissions.length}
                />

                <StatCard
                  icon={<CheckCircle2 size={20} />}
                  title="Graded"
                  value={graded}
                />

                <StatCard
                  icon={<Award size={20} />}
                  title="Marks"
                  value={submissions.reduce(
                    (sum, s) => sum + (s.marks ?? 0),
                    0
                  )}
                />

              </div>

              <div className="mt-10">

                <div className="mb-5 flex items-center justify-between">
                  <div>
                    <h3 className="text-xl font-semibold">
                      My Courses
                    </h3>

                    <p className="mt-1 text-sm text-white/40">
                      Courses you are currently enrolled in
                    </p>
                  </div>
                </div>

                {loading ? (
                  <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 text-center text-white/40">
                    Loading courses...
                  </div>
                ) : courses.length === 0 ? (
                  <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 text-center">
                    <BookOpen
                      className="mx-auto mb-3 text-white/30"
                      size={30}
                    />

                    <p className="text-white/60">
                      No courses yet
                    </p>

                    <p className="mt-1 text-sm text-white/30">
                      Your enrolled courses will appear here.
                    </p>
                  </div>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">

                    {courses.map((course) => (
                      <div
                        key={course.id}
                        className="rounded-2xl border border-white/10 bg-white/[0.035] p-6 transition hover:border-white/20 hover:bg-white/[0.05]"
                      >

                        <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl bg-white/10">
                          <BookOpen size={20} />
                        </div>

                        <h4 className="text-lg font-medium">
                          {course.title}
                        </h4>

                        <p className="mt-2 text-sm leading-6 text-white/40">
                          {course.description}
                        </p>

                        <button className="mt-5 text-sm text-white/70 hover:text-white">
                          View Course →
                        </button>

                      </div>
                    ))}

                  </div>
                )}

              </div>

              <div className="mt-10">

                <h3 className="text-xl font-semibold">
                  Recent Submissions
                </h3>

                <p className="mt-1 text-sm text-white/40">
                  Track your assignment submissions and marks
                </p>

                <div className="mt-5 overflow-hidden rounded-2xl border border-white/10">

                  {submissions.length === 0 ? (
                    <div className="p-8 text-center text-white/40">
                      No submissions yet.
                    </div>
                  ) : (
                    submissions.map((submission) => (
                      <div
                        key={submission.id}
                        className="flex items-center justify-between border-b border-white/10 px-6 py-5 last:border-0"
                      >

                        <div>
                          <p className="font-medium">
                            Assignment #{submission.assignment_id}
                          </p>

                          <p className="mt-1 text-sm text-white/40">
                            Submission #{submission.id}
                          </p>
                        </div>

                        <div className="text-right">

                          {submission.marks !== null ? (
                            <>
                              <p className="font-medium">
                                {submission.marks} marks
                              </p>

                              <p className="text-xs text-white/40">
                                Graded
                              </p>
                            </>
                          ) : (
                            <p className="text-sm text-white/40">
                              Pending
                            </p>
                          )}

                        </div>

                      </div>
                    ))
                  )}

                </div>

              </div>
            </>
          )}

          {role === "teacher" && (
            <RolePlaceholder
              title="Teacher Dashboard"
              description="Manage courses, assignments, submissions and student marks."
            />
          )}

          {role === "admin" && (
            <RolePlaceholder
              title="Admin Dashboard"
              description="Manage users and monitor the LMS platform."
            />
          )}

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

function RolePlaceholder({
  title,
  description
}: {
  title: string
  description: string
}) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-10">
      <h3 className="text-2xl font-semibold">
        {title}
      </h3>

      <p className="mt-2 text-white/40">
        {description}
      </p>

      <div className="mt-8 grid gap-4 md:grid-cols-3">

        <div className="rounded-2xl border border-white/10 p-6">
          <BookOpen className="mb-4" />
          <p className="font-medium">Courses</p>
        </div>

        <div className="rounded-2xl border border-white/10 p-6">
          <ClipboardList className="mb-4" />
          <p className="font-medium">Assignments</p>
        </div>

        <div className="rounded-2xl border border-white/10 p-6">
          <Award className="mb-4" />
          <p className="font-medium">Marks</p>
        </div>

      </div>
    </div>
  )
}