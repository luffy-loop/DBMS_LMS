import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import MobileNav from "../components/MobileNav"
import { BookOpen, LayoutDashboard, ClipboardList, Award, Search, LogOut, UserRound, GraduationCap, Users, ShieldCheck, CalendarDays, Clock3, ArrowRight, Sparkles, Building2 } from "lucide-react"
import { API } from "../config"

type Course={id:number;title:string;description:string}
type Upcoming={id:number;title:string;type:string;course:string;start_time:string|null;deadline:string}
type ProfileData={id:number;name:string;email:string;role:string;section:string;courses:Course[];upcoming:Upcoming[]}

export default function Profile(){
 const navigate=useNavigate()
 const [data,setData]=useState<ProfileData|null>(null)
 const [error,setError]=useState("")
 useEffect(()=>{
  const token=localStorage.getItem("token")
  if(!token){navigate("/login");return}
  fetch(API+"/profile",{headers:{Authorization:"Bearer "+token}})
   .then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.detail||"Unable to load profile");setData(d)})
   .catch(e=>setError(e instanceof Error?e.message:"Unable to load profile"))
 },[navigate])
 function logout(){localStorage.clear();navigate("/login")}
 const role=data?.role||localStorage.getItem("role")||"student"
 const rolePath=role==="teacher"?"/teacher":role==="admin"?"/admin":"/dashboard"
 return <div className="lms-shell min-h-screen text-white">
  <aside className="lms-sidebar fixed left-0 top-0 hidden h-screen w-64 border-r p-5 lg:block">
   <Brand role={role}/>
   <nav className="mt-8 space-y-2">
    <Nav onClick={()=>navigate(rolePath)} icon={<LayoutDashboard size={18}/>} text="Dashboard"/>
    {role==="student"&&<Nav onClick={()=>navigate("/courses")} icon={<BookOpen size={18}/>} text="My Courses"/>}
    {role==="teacher"&&<Nav onClick={()=>navigate("/teacher")} icon={<BookOpen size={18}/>} text="My Courses"/>}
    {role!=="admin"&&<Nav onClick={()=>navigate("/assignments")} icon={<ClipboardList size={18}/>} text="Assignments"/>}
    {role==="student"&&<Nav onClick={()=>navigate("/marks")} icon={<Award size={18}/>} text="Marks"/>}
    <Nav onClick={()=>navigate("/search")} icon={<Search size={18}/>} text="AI Search"/>
    <Nav active icon={<UserRound size={18}/>} text="Profile"/>
   </nav>
   <button onClick={logout} className="lms-nav absolute bottom-6 left-5 right-5"><LogOut size={18}/>Logout</button>
  </aside>

  <main className="lg:ml-64">
   <header className="lms-topbar sticky top-0 z-20 border-b px-6 py-5 lg:px-10">
    <div className="flex items-center justify-between gap-4">
     <div><p className="text-sm text-white/40">Account</p><h2 className="mt-1 text-2xl font-semibold">My Profile</h2></div>
     <button onClick={()=>navigate(rolePath)} className="lms-btn-secondary rounded-xl px-4 py-2.5 text-sm"><ArrowRight size={16}/>Back to dashboard</button>
    </div>
   </header>

   <section className="lms-grid min-h-[calc(100vh-90px)] p-6 lg:p-10">
    <div className="mx-auto max-w-6xl">
     {error&&<div className="mb-6 rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-300">{error}</div>}
     {!data&&!error?<div className="lms-card rounded-3xl p-12 text-center text-white/40">Loading your profile...</div>:data&&<>
      <div className="profile-hero lms-card rounded-3xl p-7 lg:p-9">
       <div className="relative z-[1] flex flex-col gap-7 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-5">
         <div className="profile-avatar flex h-20 w-20 shrink-0 items-center justify-center rounded-3xl"><UserRound size={34}/></div>
         <div><div className="flex flex-wrap items-center gap-2"><h3 className="text-2xl font-semibold">{data.name}</h3><span className="profile-role">{data.role}</span></div><p className="mt-2 text-sm text-white/45">LMS account #{data.id} · {data.email}</p></div>
        </div>
        <div className="profile-role-card"><RoleIcon role={data.role}/><div><p className="text-xs uppercase tracking-[.18em] text-white/35">Account type</p><p className="mt-1 font-medium capitalize">{data.role} workspace</p></div></div>
       </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
       <Info label="Full name" value={data.name} icon={<UserRound size={18}/>}/>
       <Info label="Roll / ID" value={data.email} icon={<GraduationCap size={18}/>}/>
       <Info label="Section allotted" value={data.section} icon={<Building2 size={18}/>}/>
       <Info label="Role" value={data.role} icon={<ShieldCheck size={18}/>}/>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.25fr_.75fr]">
       <div className="lms-card rounded-3xl p-7">
        <div className="flex items-center justify-between gap-4"><div><p className="text-xs uppercase tracking-[.18em] text-violet-300/70">Schedule</p><h3 className="mt-2 text-xl font-semibold">Upcoming assignments</h3><p className="mt-1 text-sm text-white/35">Assessments connected to your role and courses.</p></div><div className="lms-icon flex h-11 w-11 items-center justify-center rounded-xl"><CalendarDays size={19}/></div></div>
        <div className="mt-6 space-y-3">
         {data.upcoming.length?data.upcoming.map(a=><div key={a.id} className="profile-assessment rounded-2xl border border-white/8 p-4"><div className="flex items-start gap-4"><div className="profile-date"><span>{formatDay(a.deadline)}</span><small>{formatMonth(a.deadline)}</small></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="font-medium">{a.title}</p><span className="rounded-full border border-cyan-400/15 bg-cyan-400/10 px-2.5 py-1 text-[10px] uppercase tracking-wider text-cyan-200">{a.type}</span></div><p className="mt-1 text-sm text-white/40">{a.course}</p><div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-white/30"><span className="inline-flex items-center gap-1.5"><Clock3 size={13}/>Due {formatDate(a.deadline)}</span>{a.start_time&&<span className="inline-flex items-center gap-1.5"><CalendarDays size={13}/>Opens {formatDate(a.start_time)}</span>}</div></div><button onClick={()=>navigate("/assignments")} className="lms-icon hidden h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white/45 hover:text-white sm:flex"><ArrowRight size={16}/></button></div></div>):<div className="lms-empty rounded-2xl p-8 text-center"><CalendarDays className="mx-auto text-white/25" size={28}/><p className="mt-3 font-medium text-white/60">No upcoming assessments</p><p className="mt-1 text-sm text-white/30">Your schedule will appear here when assessments are published.</p></div>}
        </div>
       </div>

       <div className="space-y-6">
        <div className="lms-card rounded-3xl p-7"><div className="flex items-center gap-3"><BookOpen className="text-violet-300" size={19}/><h3 className="font-semibold">{role==="teacher"?"Courses you teach":role==="admin"?"Platform courses":"Enrolled courses"}</h3></div><p className="mt-1 text-sm text-white/35">{data.courses.length} course{data.courses.length===1?"":"s"}</p><div className="mt-5 space-y-2">{data.courses.slice(0,5).map(c=><div key={c.id} className="profile-course"><span className="lms-icon flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"><BookOpen size={15}/></span><span className="min-w-0 flex-1 truncate text-sm">{c.title}</span></div>)}{!data.courses.length&&<div className="lms-empty rounded-xl p-5 text-center text-sm text-white/30">No courses linked yet.</div>}</div></div>
        <div className="lms-card rounded-3xl p-7"><div className="flex items-center gap-3"><Sparkles className="text-cyan-300" size={19}/><h3 className="font-semibold">Profile status</h3></div><div className="mt-5 rounded-2xl border border-emerald-400/15 bg-emerald-400/5 p-4"><p className="text-sm font-medium text-emerald-300">Account active</p><p className="mt-1 text-xs leading-5 text-white/35">Your role-based LMS access is connected to this profile.</p></div></div>
       </div>
      </div>
     </>}
    </div>
   </section>
  </main>
    <MobileNav role={role} active="profile />
  </div>
}

function Brand({role}:{role:string}){return <div className="flex items-center gap-3 px-3 py-4"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-black"><BookOpen size={21}/></div><div><h1 className="font-semibold">LMS</h1><p className="text-xs text-white/40 capitalize">{role} Workspace</p></div></div>}
function Nav({onClick,active,icon,text}:{onClick?:()=>void;active?:boolean;icon:React.ReactNode;text:string}){return <button onClick={onClick} className={"lms-nav "+(active?"active":"")}>{icon}{text}</button>}
function Info({label,value,icon}:{label:string;value:string;icon:React.ReactNode}){return <div className="profile-info lms-stat rounded-2xl p-5"><div className="lms-icon flex h-10 w-10 items-center justify-center rounded-xl">{icon}</div><p className="mt-4 text-xs uppercase tracking-wider text-white/30">{label}</p><p className="mt-1 truncate text-sm font-medium capitalize">{value}</p></div>}
function RoleIcon({role}:{role:string}){return role==="teacher"?<Users size={20}/>:role==="admin"?<ShieldCheck size={20}/>:<GraduationCap size={20}/>}
function formatDay(v:string){return new Date(v).toLocaleDateString("en-IN",{day:"2-digit"})}
function formatMonth(v:string){return new Date(v).toLocaleDateString("en-IN",{month:"short"}).toUpperCase()}
function formatDate(v:string){return new Date(v).toLocaleString("en-IN",{day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"})}
