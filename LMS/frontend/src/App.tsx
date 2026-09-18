import { motion } from "motion/react"
import { BookOpen, GraduationCap, Database, Search, ShieldCheck, Users } from "lucide-react"

const nodes = [
  { icon: GraduationCap, label: "Students", x: "12%", y: "22%" },
  { icon: Users, label: "Teachers", x: "82%", y: "22%" },
  { icon: ShieldCheck, label: "Admin", x: "12%", y: "72%" },
  { icon: Search, label: "AI Search", x: "82%", y: "72%" },
  { icon: Database, label: "Data Layer", x: "50%", y: "88%" },
]

function App() {
  return (
    <div className="min-h-screen overflow-hidden bg-[#070b14] text-white">

      <nav className="flex items-center justify-between border-b border-white/10 px-8 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-black">
            <BookOpen size={20} />
          </div>
          <span className="text-lg font-semibold">LMS</span>
        </div>

        <div className="hidden gap-8 text-sm text-white/60 md:flex">
          <span>Courses</span>
          <span>Assignments</span>
          <span>Smart Search</span>
          <span>About</span>
        </div>

          <button
            onClick={() => window.location.href = "/login"}
            className="rounded-full border border-white/15 px-5 py-2 text-sm hover:bg-white hover:text-black transition"
          >
            Login
          </button>
      </nav>

      <main className="mx-auto max-w-7xl px-6">

        <section className="grid min-h-[calc(100vh-80px)] items-center gap-10 py-16 lg:grid-cols-2">

          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs text-white/60">
              <span className="h-2 w-2 rounded-full bg-green-400" />
              Distributed Learning Platform
            </div>

            <h1 className="text-5xl font-semibold leading-tight tracking-tight sm:text-6xl">
              Learn.
              <br />
              Connect.
              <br />
              <span className="text-white/40">Grow.</span>
            </h1>

            <p className="mt-6 max-w-lg text-base leading-7 text-white/50">
              A scalable learning management system connecting students,
              teachers and administrators through one intelligent platform.
            </p>

            <div className="mt-8 flex gap-4">
              <button className="rounded-full bg-white px-6 py-3 text-sm font-medium text-black hover:bg-white/90">
                Get Started
              </button>

              <button className="rounded-full border border-white/15 px-6 py-3 text-sm text-white/70 hover:bg-white/5">
                Explore Courses
              </button>
            </div>
          </div>

          <div className="relative h-[520px] overflow-hidden rounded-3xl border border-white/10 bg-white/[0.025]">

            <div
              className="absolute inset-0 opacity-20"
              style={{
                backgroundImage:
                  "radial-gradient(circle, white 1px, transparent 1px)",
                backgroundSize: "30px 30px",
              }}
            />

            <svg
              className="absolute inset-0 h-full w-full"
              viewBox="0 0 600 520"
              fill="none"
            >
              <path d="M300 260 L90 115" stroke="white" strokeOpacity=".15" />
              <path d="M300 260 L510 115" stroke="white" strokeOpacity=".15" />
              <path d="M300 260 L90 390" stroke="white" strokeOpacity=".15" />
              <path d="M300 260 L510 390" stroke="white" strokeOpacity=".15" />
              <path d="M300 260 L300 465" stroke="white" strokeOpacity=".15" />

              <motion.path
                d="M300 260 L90 115"
                stroke="white"
                strokeOpacity=".8"
                strokeWidth="2"
                strokeDasharray="30 100"
                animate={{ strokeDashoffset: -130 }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
              />

              <motion.path
                d="M300 260 L510 115"
                stroke="white"
                strokeOpacity=".8"
                strokeWidth="2"
                strokeDasharray="30 100"
                animate={{ strokeDashoffset: -130 }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear", delay: .5 }}
              />

              <motion.path
                d="M300 260 L90 390"
                stroke="white"
                strokeOpacity=".8"
                strokeWidth="2"
                strokeDasharray="30 100"
                animate={{ strokeDashoffset: -130 }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear", delay: 1 }}
              />

              <motion.path
                d="M300 260 L510 390"
                stroke="white"
                strokeOpacity=".8"
                strokeWidth="2"
                strokeDasharray="30 100"
                animate={{ strokeDashoffset: -130 }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear", delay: 1.5 }}
              />
            </svg>

            <div className="absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2">
              <motion.div
                animate={{ scale: [1, 1.06, 1] }}
                transition={{ duration: 3, repeat: Infinity }}
                className="flex h-28 w-28 flex-col items-center justify-center rounded-3xl border border-white/20 bg-white text-black shadow-2xl"
              >
                <BookOpen size={30} />
                <span className="mt-2 text-sm font-semibold">LMS Core</span>
              </motion.div>
            </div>

            {nodes.map((node, i) => {
              const Icon = node.icon

              return (
                <motion.div
                  key={node.label}
                  initial={{ opacity: 0, scale: .7 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * .15 }}
                  style={{ left: node.x, top: node.y }}
                  className="absolute -translate-x-1/2 -translate-y-1/2"
                >
                  <div className="flex flex-col items-center gap-2">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/15 bg-[#0d1320] shadow-xl">
                      <Icon size={22} />
                    </div>
                    <span className="text-xs text-white/50">{node.label}</span>
                  </div>
                </motion.div>
              )
            })}

          </div>
        </section>

        <section className="grid gap-4 pb-20 sm:grid-cols-3">
          {[
            ["Role Based Access", "Student, Teacher and Admin dashboards"],
            ["Polyglot Persistence", "PostgreSQL and MongoDB data layers"],
            ["AI Smart Search", "Semantic retrieval for learning content"],
          ].map(([title, text]) => (
            <div
              key={title}
              className="rounded-2xl border border-white/10 bg-white/[0.03] p-6"
            >
              <h3 className="font-medium">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-white/40">{text}</p>
            </div>
          ))}
        </section>

      </main>
    </div>
  )
}

export default App