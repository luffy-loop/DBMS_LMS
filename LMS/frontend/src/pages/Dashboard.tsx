import { useEffect, useState } from "react"
import {
  BookOpen,
  ClipboardList,
  CheckCircle2,
  Award,
  LogOut,
  LayoutDashboard,
  Search,
  BrainCircuit,
  User,
  Sparkles,
  Target,
  ArrowRight,
  TrendingUp
} from "lucide-react"
import { useNavigate } from "react-router-dom"
import MobileNav from "../components/MobileNav"
import { API } from "../config"


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

type LearningInsight = {
  overall: { progress: number; average_marks: number | null; graded: number; submitted: number; total_assessments: number }
  courses: { id: number; title: string; assessments: number; submitted: number; graded: number; average_marks: number | null; progress: number }[]
  next_actions: { title: string; detail: string; priority: string; action: string }[]
  focus_course: { id: number; title: string; progress: number; average_marks: number | null } | null
}

export default function Dashboard() {
  const navigate = useNavigate()

  const [name, setName] = useState("")
  const [role, setRole] = useState("")
  const [courses, setCourses] = useState<Course[]>([])
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [insights, setInsights] = useState<LearningInsight | null>(null)
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

      const [coursesRes, submissionsRes, insightsRes] = await Promise.all([
        fetch(`${API}/my-courses`, { headers }),
        fetch(`${API}/my-submissions`, { headers }),
        fetch(`${API}/learning-insights`, { headers })
      ])

      if (coursesRes.ok) {
        const coursesData = await coursesRes.json()
        setCourses(coursesData)
      }

      if (submissionsRes.ok) {
        const submissionsData = await submissionsRes.json()
        setSubmissions(submissionsData)
      }
      if (insightsRes.ok) {
        const insightsData = await insightsRes.json()
        setInsights(insightsData)
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

      <aside className="lms-sidebar fixed left-0 top-0 hidden h-screen w-64 border-r p-5 lg:block">

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
            Marks
          </button>

          <button onClick={() => navigate("/search")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
            <Search size={18} />
            AI Search
          </button>

          <button onClick={() => navigate("/copilot")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
            <BrainCircuit size={18} />
            AI Study Hub
          </button>

          <button onClick={() => navigate("/quiz")} className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-white/50 hover:bg-white/5 hover:text-white">
            <Sparkles size={18} />
            Quiz Lab
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

          <button onClick={() => navigate("/profile")} className="lms-profile-trigger flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5" aria-label="Open profile">
            <User size={18} />
          </button>

        </header>

        <section className="lms-grid min-h-[calc(100vh-90px)] p-6 lg:p-10">

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

              <div className="lms-hero mt-8 rounded-3xl p-6 lg:p-8"><div className="relative z-[1] flex flex-col gap-6 md:flex-row md:items-end md:justify-between"><div><p className="text-sm font-medium text-violet-300">Personal learning space</p><h3 className="mt-2 text-2xl font-semibold tracking-tight">Keep your learning momentum.</h3><p className="mt-2 max-w-xl text-sm leading-6 text-white/45">Your courses, submissions and progress are collected here so you always know what to work on next.</p></div><button onClick={() => navigate("/copilot")} className="lms-btn-primary rounded-xl px-4 py-3 text-sm font-medium"><BrainCircuit size={16}/>Open AI Study Hub</button></div></div><div className="mt-10">

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
                  <div className="lms-empty rounded-2xl p-8 text-center text-white/40">
                    Loading courses...
                  </div>
                ) : courses.length === 0 ? (
                  <div className="lms-empty rounded-2xl p-8 text-center">
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
                        className="lms-card rounded-2xl p-6"
                      >

                        <div className="lms-icon mb-5 flex h-11 w-11 items-center justify-center rounded-xl">
                          <BookOpen size={20} />
                        </div>

                        <h4 className="text-lg font-medium">
                          {course.title}
                        </h4>

                        <p className="mt-2 text-sm leading-6 text-white/40">
                          {course.description}
                        </p>

                        <button className="mt-5 text-sm font-medium text-violet-300 transition hover:text-white">
                          View Course →
                        </button>

                      </div>
                    ))}

                  </div>
                )}

              </div>

              <div id="learning-path" className="lms-card mt-8 rounded-3xl p-6 lg:p-8">
                <div className="relative z-[1]">
                  <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex items-center gap-2 text-violet-300"><Sparkles size={18}/><span className="text-sm font-medium">Adaptive Learning Engine</span></div>
                      <h3 className="mt-2 text-2xl font-semibold">Your learning path</h3>
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-white/45">Your progress, submissions and marks are analyzed to suggest what you should focus on next.</p>
                    </div>
                    <div className="lms-icon flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"><Target size={22}/></div>
                  </div>
                  {insights ? (
                    <>
                      <div className="mt-7 grid gap-4 md:grid-cols-3">
                        <InsightMetric label="Course progress" value={insights.overall.progress + "%"} detail={insights.overall.submitted + " of " + insights.overall.total_assessments + " assessments submitted"} />
                        <InsightMetric label="Average marks" value={insights.overall.average_marks === null ? "—" : String(insights.overall.average_marks)} detail={insights.overall.graded + " graded submissions"} />
                        <InsightMetric label="Focus area" value={insights.focus_course?.title || "Getting started"} detail={insights.focus_course ? insights.focus_course.progress + "% course progress" : "Complete an assessment to unlock insights"} />
                      </div>
                      <div className="mt-7 grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
                        <div>
                          <div className="mb-3 flex items-center justify-between"><p className="text-sm font-medium">Overall progress</p><span className="text-xs text-white/35">{insights.overall.progress}%</span></div>
                          <div className="h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400 transition-all" style={{width: insights.overall.progress + "%"}}/></div>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/[.025] p-4">
                          <div className="flex items-center gap-2 text-white/70"><TrendingUp size={16}/><span className="text-sm font-medium">Next best actions</span></div>
                          <div className="mt-3 space-y-3">
                            {insights.next_actions.slice(0, 3).map((action, index) => (
                              <button key={index} onClick={() => navigate(action.action === "search" ? "/search" : action.action === "courses" ? "/courses" : "/assignments")} className="group flex w-full items-start gap-3 rounded-xl border border-white/5 bg-white/[.025] p-3 text-left transition hover:border-violet-400/20 hover:bg-white/[.05]">
                                <span className={"mt-0.5 h-2 w-2 shrink-0 rounded-full " + (action.priority === "high" ? "bg-violet-400" : "bg-cyan-400")}/>
                                <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{action.title}</span><span className="mt-1 block text-xs leading-5 text-white/35">{action.detail}</span></span>
                                <ArrowRight size={15} className="mt-1 shrink-0 text-white/25 transition group-hover:translate-x-1 group-hover:text-white/60"/>
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="mt-7 rounded-2xl border border-dashed border-white/10 p-6 text-sm text-white/35">Building your learning profile...</div>
                  )}
                </div>
              </div>

              <div className="mt-10 grid gap-4 md:grid-cols-2">
                <button onClick={() => navigate("/copilot")} className="lms-card rounded-2xl p-5 text-left">
                  <div className="lms-icon flex h-10 w-10 items-center justify-center rounded-xl"><BrainCircuit size={19}/></div>
                  <p className="mt-4 font-medium">AI Study Hub</p>
                  <p className="mt-2 text-sm leading-6 text-white/35">Ask basic questions, get course-grounded answers, and make quick revision notes.</p>
                </button>
                <button onClick={() => navigate("/quiz")} className="lms-card rounded-2xl p-5 text-left">
                  <div className="lms-icon flex h-10 w-10 items-center justify-center rounded-xl"><Sparkles size={19}/></div>
                  <p className="mt-4 font-medium">Quiz Lab</p>
                  <p className="mt-2 text-sm leading-6 text-white/35">Generate a fresh concept quiz and check your score instantly.</p>
                </button>
              </div>

              <div className="mt-10">

                <h3 className="text-xl font-semibold">
                  Recent Submissions
                </h3>

                <p className="mt-1 text-sm text-white/40">
                  Track your assignment submissions and marks
                </p>

                <div className="lms-card mt-5 overflow-hidden rounded-2xl">

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

function InsightMetric({label,value,detail}:{label:string;value:string;detail:string}) {
  return <div className="rounded-2xl border border-white/10 bg-white/[.025] p-4">
    <p className="text-xs uppercase tracking-wider text-white/30">{label}</p>
    <p className="mt-2 text-xl font-semibold">{value}</p>
    <p className="mt-1 text-xs text-white/35">{detail}</p>
  
    <MobileNav role={"student"} active="dashboard" />
</div>
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
    <div className="lms-stat rounded-2xl p-5">

      <div className="lms-icon mb-5 flex h-10 w-10 items-center justify-center rounded-xl">
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
    <div className="lms-card rounded-3xl p-10">
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
  </div>
  )
}