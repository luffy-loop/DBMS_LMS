import { BookOpen, LayoutDashboard, BookOpenText, ClipboardList, Award, Search, BrainCircuit, Sparkles, Route, BarChart3, UserRound, LogOut, Menu, X } from "lucide-react"
import { useEffect, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import NotificationBell from "./NotificationBell"

type Role = "student" | "teacher" | "admin"

type NavItem = { path:string; label:string; icon:typeof BookOpen }

export default function AppLayout({ children, title, subtitle, roleOverride }: { children:React.ReactNode; title?:string; subtitle?:string; roleOverride?:Role }) {
  const navigate = useNavigate()
  const location = useLocation()
  const role = roleOverride || (localStorage.getItem("role") as Role) || "student"
  const name = localStorage.getItem("name") || "User"
  const [menuOpen, setMenuOpen] = useState(false)

  const dashboard = role === "teacher" ? "/teacher" : role === "admin" ? "/admin" : "/dashboard"
  const items: NavItem[] = [
    { path:dashboard, label:"Dashboard", icon:LayoutDashboard },
    { path:"/courses", label:"Courses", icon:BookOpenText },
    { path:"/assignments", label:"Assignments", icon:ClipboardList },
    { path:"/marks", label:role === "teacher" ? "Student Marks" : "Marks", icon:Award },
    { path:"/search", label:"AI Search", icon:Search },
    { path:"/copilot", label:"Study Copilot", icon:BrainCircuit },
    { path:"/quiz", label:"Quiz Lab", icon:Sparkles },
  ]
  if (role === "student") items.push({ path:"/learning-path", label:"Learning Path", icon:Route })
  if (role === "teacher") items.push({ path:"/teacher/insights", label:"Teaching Insights", icon:BarChart3 })

  function active(path:string) {
    return location.pathname === path || (path !== dashboard && location.pathname.startsWith(path + "/"))
  }
  function logout() {
    localStorage.clear()
    navigate("/login", { replace:true })
  }

  useEffect(() => setMenuOpen(false), [location.pathname])

  return <div className="lms-shell min-h-screen text-white">
    <aside className="lms-sidebar fixed inset-y-0 left-0 z-40 hidden w-64 border-r p-5 lg:flex lg:flex-col">
      <div className="flex items-center gap-3 px-3 py-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-black"><BookOpen size={21}/></div>
        <div><h1 className="font-semibold">LMS</h1><p className="text-xs text-white/40">Learning Platform</p></div>
      </div>
      <nav className="mt-7 flex-1 space-y-1 overflow-y-auto pr-1" aria-label="Primary navigation">
        {items.map(({path,label,icon:Icon}) => <button key={path} onClick={() => navigate(path)} className={"lms-nav " + (active(path) ? "active" : "")} aria-current={active(path) ? "page" : undefined}><Icon size={18}/>{label}</button>)}
      </nav>
      <button onClick={() => navigate("/profile")} className={"lms-nav " + (active("/profile") ? "active" : "")}><UserRound size={18}/>Profile</button>
      <button onClick={logout} className="lms-nav"><LogOut size={18}/>Logout</button>
    </aside>

    {menuOpen && <button aria-label="Close navigation menu" className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={() => setMenuOpen(false)}/>}
    <div className="lg:pl-64">
      <header className="lms-topbar sticky top-0 z-30 flex min-h-[76px] items-center justify-between gap-4 border-b px-4 py-4 sm:px-6 lg:px-10">
        <div className="min-w-0">
          <p className="truncate text-xs text-white/35">{subtitle || "Learning Platform"}</p>
          {title && <h1 className="truncate text-xl font-semibold sm:text-2xl">{title}</h1>}
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
          <span className="hidden max-w-40 truncate text-sm text-white/40 sm:block">{name}</span>
          <NotificationBell/>
          <button onClick={() => setMenuOpen(v => !v)} className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 lg:hidden" aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}>{menuOpen ? <X size={18}/> : <Menu size={18}/>}</button>
          <button onClick={() => navigate("/profile")} className="hidden h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 sm:flex" aria-label="Open profile"><UserRound size={17}/></button>
        </div>
      </header>
      {menuOpen && <nav className="fixed right-3 top-[68px] z-50 w-[min(90vw,300px)] rounded-2xl border border-white/10 bg-[#0b101a] p-3 shadow-2xl lg:hidden" aria-label="Mobile navigation">
        {items.map(({path,label,icon:Icon}) => <button key={path} onClick={() => navigate(path)} className={"lms-nav " + (active(path) ? "active" : "")}><Icon size={18}/>{label}</button>)}
        <button onClick={() => navigate("/profile")} className={"lms-nav " + (active("/profile") ? "active" : "")}><UserRound size={18}/>Profile</button>
        <button onClick={logout} className="lms-nav"><LogOut size={18}/>Logout</button>
      </nav>}
      <main className="lms-page min-w-0 pb-8 sm:pb-10">{children}</main>
    </div>
    <nav className="lms-mobile-nav lg:hidden" aria-label="Mobile quick navigation">
      {[{path:dashboard,label:"Home",icon:LayoutDashboard},{path:"/courses",label:"Courses",icon:BookOpenText},{path:"/assignments",label:"Tasks",icon:ClipboardList},{path:"/copilot",label:"AI",icon:Sparkles},{path:"/profile",label:"Profile",icon:UserRound}].map(({path,label,icon:Icon}) => <button key={path} onClick={() => navigate(path)} className={active(path) ? "active" : ""} aria-current={active(path) ? "page" : undefined}><Icon size={18}/><span>{label}</span></button>)}
    </nav>
  </div>
}
