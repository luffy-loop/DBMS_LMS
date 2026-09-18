import { useEffect, useState } from "react"
import { BookOpen, LayoutDashboard, ClipboardList, Award, Search, LogOut, Plus, X, Upload, FileText, BarChart3, Sparkles, UserRound } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { API } from "../config"

type Course={id:number;title:string;description:string;teacher_id:number}
type Stats={courses:number;assessments:number;course_pdfs:number;submissions:number;pending_grading:number}

export default function TeacherDashboard(){
 const navigate=useNavigate()
 const [courses,setCourses]=useState<Course[]>([])
 const [stats,setStats]=useState<Stats>({courses:0,assessments:0,course_pdfs:0,submissions:0,pending_grading:0})
 const [title,setTitle]=useState("")
 const [description,setDescription]=useState("")
 const [show,setShow]=useState(false)
 const [mode,setMode]=useState<"course"|"resource">("course")
 const [resourceCourse,setResourceCourse]=useState("")
 const [resourceTitle,setResourceTitle]=useState("")
 const [file,setFile]=useState<File|null>(null)
 const [busy,setBusy]=useState(false)
 const [loading,setLoading]=useState(true)
 const [message,setMessage]=useState("")
 const [error,setError]=useState("")
 const name=localStorage.getItem("name")||"Teacher"

 useEffect(()=>{
  const t=localStorage.getItem("token")
  if(!t){navigate("/login");return}
  if(localStorage.getItem("role")!=="teacher"){navigate("/dashboard");return}
  load()
 },[navigate])

 async function load(){
  const t=localStorage.getItem("token")
  if(!t)return
  setLoading(true);setError("")
  try{
   const [cr,sr]=await Promise.all([
    fetch(API+"/courses",{headers:{Authorization:"Bearer "+t}}),
    fetch(API+"/teacher/overview",{headers:{Authorization:"Bearer "+t}})
   ])
   if(cr.status===401||sr.status===401){localStorage.clear();navigate("/login");return}
   if(!cr.ok)throw new Error("Unable to load courses")
   const all=await cr.json()
   const mine=all.filter((c:Course)=>c.teacher_id===Number(localStorage.getItem("userId")))
   setCourses(mine)
   if(sr.ok)setStats(await sr.json())
   else setStats(s=>({...s,courses:mine.length}))
  }catch(e){setError(e instanceof Error?e.message:"Failed to load dashboard")}
  finally{setLoading(false)}
 }

 function openCourseForm(){
  setMode("course");setMessage("");setError("");setTitle("");setDescription("");setShow(true)
 }

 function openResourceForm(courseId?:number){
  if(!courses.length)return
  setMode("resource");setResourceCourse(String(courseId||courses[0].id));setResourceTitle("");setFile(null);setMessage("");setError("");setShow(true)
 }

 async function create(e:React.FormEvent){
  e.preventDefault()
  const t=localStorage.getItem("token");if(!t)return
  setBusy(true);setError("")
  try{
   const r=await fetch(API+"/courses",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+t},body:JSON.stringify({title,description})})
   const d=await r.json()
   if(!r.ok)throw new Error(d.detail||"Failed to create course")
   setMessage("Course created successfully")
   setShow(false)
   await load()
  }catch(e){setError(e instanceof Error?e.message:"Failed to create course")}
  finally{setBusy(false)}
 }

 async function upload(e:React.FormEvent){
  e.preventDefault()
  const t=localStorage.getItem("token")
  if(!t||!file)return
  setBusy(true);setError("")
  try{
   const b=new FormData();b.append("file",file);b.append("title",resourceTitle)
   const r=await fetch(API+"/courses/"+resourceCourse+"/resources",{method:"POST",headers:{Authorization:"Bearer "+t},body:b})
   const d=await r.json()
   if(!r.ok)throw new Error(d.detail||"Upload failed")
   setMessage("PDF uploaded successfully")
   setShow(false)
   await load()
  }catch(e){setError(e instanceof Error?e.message:"Upload failed")}
  finally{setBusy(false)}
 }

 function logout(){localStorage.clear();navigate("/login")}
 function scrollCourses(){document.getElementById("teacher-courses")?.scrollIntoView({behavior:"smooth",block:"start"})}

 return <div className="lms-shell min-h-screen text-white">
  <aside className="lms-sidebar fixed left-0 top-0 hidden h-screen w-64 border-r p-5 lg:block">
   <Brand/>
   <nav className="mt-8 space-y-2">
    <Nav onClick={()=>navigate("/teacher")} active icon={<LayoutDashboard size={18}/>} text="Dashboard"/>
    <Nav onClick={scrollCourses} icon={<BookOpen size={18}/>} text="My Courses"/>
    <Nav onClick={()=>navigate("/assignments")} icon={<ClipboardList size={18}/>} text="Assignments"/>
    <Nav onClick={()=>navigate("/marks")} icon={<Award size={18}/>} text="Student Marks"/>
    <Nav onClick={()=>navigate("/teacher/insights")} icon={<BarChart3 size={18}/>} text="Teaching Insights"/>
    <Nav onClick={()=>navigate("/search")} icon={<Search size={18}/>} text="AI Search"/>
   </nav>
   <button onClick={logout} className="lms-nav absolute bottom-6 left-5 right-5"><LogOut size={18}/>Logout</button>
  </aside>

  <main className="lg:ml-64">
   <header className="lms-topbar sticky top-0 z-10 border-b px-6 py-5 lg:px-10">
    <div className="flex items-center justify-between gap-5">
     <div><p className="text-sm text-white/40">Teacher Workspace</p><h2 className="mt-1 text-2xl font-semibold">Welcome back, {name}</h2><p className="mt-1 text-sm text-white/30">Manage courses, assessments and learning material from one place.</p></div>
     <button onClick={openCourseForm} className="lms-btn-primary hidden rounded-xl px-4 py-3 text-sm font-medium sm:inline-flex"><Plus size={17}/>New Course</button>
    </div>
     <button onClick={()=>navigate("/profile")} className="lms-profile-trigger flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5" aria-label="Open profile"><UserRound size={18}/></button>
    </div>
   </header>

   <section className="lms-grid min-h-[calc(100vh-90px)] p-6 lg:p-10">
    <div className="mx-auto max-w-7xl">
     {error&&<Msg text={error}/>}
     {message&&<Msg text={message} ok/>}

     <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Stat icon={<BookOpen size={20}/>} title="My Courses" value={stats.courses||courses.length} detail="Published courses"/>
      <Stat icon={<ClipboardList size={20}/>} title="Assessments" value={stats.assessments} detail="Assignments & tests"/>
      <Stat icon={<FileText size={20}/>} title="Course PDFs" value={stats.course_pdfs} detail="Learning resources"/>
      <Stat icon={<Sparkles size={20}/>} title="Pending Grading" value={stats.pending_grading} detail={stats.submissions+" total submissions"}/>
     </div>

     <div id="teacher-courses" className="scroll-mt-28 mt-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
       <div><p className="text-xs font-medium uppercase tracking-[.18em] text-violet-300/70">Content studio</p><h3 className="mt-2 text-2xl font-semibold">My Courses</h3><p className="mt-1 text-sm text-white/40">Build courses and publish polished PDF learning material.</p></div>
       <div className="flex gap-3">
        <button disabled={!courses.length} onClick={()=>openResourceForm()} className="lms-btn-secondary rounded-xl px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-35"><Upload size={17}/>Upload PDF</button>
        <button onClick={openCourseForm} className="lms-btn-primary rounded-xl px-4 py-3 text-sm font-medium"><Plus size={17}/>Create Course</button>
       </div>
      </div>

      {!loading&&!courses.length&&<div className="lms-empty mt-6 rounded-3xl p-10 text-center"><div className="lms-icon mx-auto flex h-14 w-14 items-center justify-center rounded-2xl"><BookOpen size={24}/></div><p className="mt-5 text-lg font-semibold">Your course studio is ready</p><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-white/40">Create your first course, then add PDF material and assessments for students.</p><button onClick={openCourseForm} className="lms-btn-primary mt-6 rounded-xl px-5 py-3 text-sm font-medium"><Plus size={17}/>Create Your First Course</button></div>}

      {loading&&<div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{[1,2,3].map(i=><div key={i} className="lms-skeleton h-56 rounded-2xl"/> )}</div>}

      <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
       {courses.map(c=><div key={c.id} className="lms-card group rounded-2xl p-6">
        <div className="flex items-start justify-between"><div className="lms-icon flex h-11 w-11 items-center justify-center rounded-xl"><BookOpen size={20}/></div><span className="rounded-full border border-violet-400/15 bg-violet-400/10 px-3 py-1 text-[11px] text-violet-200">Published</span></div>
        <h4 className="mt-6 text-lg font-semibold">{c.title}</h4>
        <p className="mt-2 min-h-12 text-sm leading-6 text-white/40">{c.description}</p>
        <div className="mt-6 flex items-center justify-between border-t border-white/8 pt-4"><span className="text-xs text-white/30">Course #{c.id}</span><button onClick={()=>openResourceForm(c.id)} className="lms-btn-secondary rounded-lg px-3 py-2 text-xs"><Upload size={14}/>Add PDF</button></div>
       </div>)}
      </div>
     </div>
    </div>
   </section>

   {show&&<div className="lms-modal fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
    <div className="lms-modal-panel lms-card w-full max-w-xl rounded-3xl bg-[#0b101a] p-6 sm:p-7">
     <div className="mb-6 flex items-start justify-between gap-5"><div><p className="text-xs uppercase tracking-[.18em] text-violet-300/70">{mode==="resource"?"Course material":"Course studio"}</p><h3 className="mt-2 text-2xl font-semibold">{mode==="resource"?"Publish Course Material":"Create New Course"}</h3></div><button aria-label="Close" onClick={()=>setShow(false)} className="lms-icon flex h-10 w-10 items-center justify-center rounded-xl text-white/60 hover:text-white"><X size={19}/></button></div>
     <form onSubmit={mode==="resource"?upload:create} className="space-y-5">
      {mode==="resource"?<><Field label="Course"><select value={resourceCourse} onChange={e=>setResourceCourse(e.target.value)} className="lms-input"><option value="" disabled>Select a course</option>{courses.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select></Field><Field label="Material Title"><input value={resourceTitle} onChange={e=>setResourceTitle(e.target.value)} required className="lms-input" placeholder="e.g. Unit 3 — Normalization Notes"/></Field><Field label="PDF File"><input type="file" accept=".pdf,application/pdf" onChange={e=>setFile(e.target.files?.[0]||null)} required className="lms-file"/></Field></>:<><Field label="Course Title"><input value={title} onChange={e=>setTitle(e.target.value)} required className="lms-input" placeholder="e.g. Database Systems"/></Field><Field label="Description"><textarea value={description} onChange={e=>setDescription(e.target.value)} required rows={5} className="lms-input resize-none" placeholder="Describe what students will learn in this course..."/></Field></>}
      <button disabled={busy} className="lms-btn-primary w-full rounded-xl py-3.5 text-sm font-semibold disabled:cursor-wait disabled:opacity-60">{busy?"Saving...":mode==="resource"?"Publish PDF Material":"Create Course"}</button>
     </form>
    </div>
   </div>}
  </main>
 </div>
}

function Brand(){return <div className="flex items-center gap-3 px-3 py-4"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-black"><BookOpen size={21}/></div><div><h1 className="font-semibold">LMS</h1><p className="text-xs text-white/40">Teacher Workspace</p></div></div>}
function Nav({onClick,active,icon,text}:{onClick:()=>void;active?:boolean;icon:React.ReactNode;text:string}){return <button onClick={onClick} className={"lms-nav "+(active?"active":"")}>{icon}{text}</button>}
function Field({label,children}:{label:string;children:React.ReactNode}){return <div><label className="mb-2 block text-sm font-medium text-white/60">{label}</label>{children}</div>}
function Stat({icon,title,value,detail}:{icon:React.ReactNode;title:string;value:number;detail:string}){return <div className="lms-stat rounded-2xl p-5"><div className="flex items-start justify-between"><div className="lms-icon flex h-10 w-10 items-center justify-center rounded-xl">{icon}</div><span className="text-xs text-white/20">LIVE</span></div><p className="mt-5 text-sm text-white/40">{title}</p><p className="mt-1 text-2xl font-semibold">{value}</p><p className="mt-1 text-xs text-white/25">{detail}</p></div>}
function Msg({text,ok=false}:{text:string;ok?:boolean}){return <div className={"mb-6 rounded-xl border px-4 py-3 text-sm "+(ok?"border-emerald-400/20 bg-emerald-400/10 text-emerald-300":"border-red-400/20 bg-red-400/10 text-red-300")}>{text}</div>}
