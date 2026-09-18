import { useEffect,useState } from "react"
import { BookOpen,LayoutDashboard,ClipboardList,Award,Search,LogOut,Plus,X,Send,Clock,FileText,Upload,Download } from "lucide-react"
import { useNavigate } from "react-router-dom"
const API="http://127.0.0.1:8000"
type Course={id:number;title:string;description:string;teacher_id:number}
type A={id:number;title:string;description:string;course_id:number;teacher_id:number;type:string;start_time:string|null;end_time:string|null;duration_minutes:number|null;deadline:string|null;status:"upcoming"|"open"|"closed";submitted:boolean;handout:{id:string;title:string;filename:string}|null}

export default function Assignments(){
 const navigate=useNavigate(),[role,setRole]=useState(""),[courses,setCourses]=useState<Course[]>([]),[items,setItems]=useState<A[]>([]),[title,setTitle]=useState(""),[description,setDescription]=useState(""),[courseId,setCourseId]=useState(""),[type,setType]=useState("assignment"),[start,setStart]=useState(""),[end,setEnd]=useState(""),[duration,setDuration]=useState(""),[handout,setHandout]=useState<File|null>(null),[answer,setAnswer]=useState(""),[submissionFile,setSubmissionFile]=useState<File|null>(null),[selected,setSelected]=useState<number|null>(null),[show,setShow]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState("")

 useEffect(()=>{const t=localStorage.getItem("token"),r=localStorage.getItem("role")||"student";if(!t){navigate("/login");return}setRole(r);load(t,r)},[navigate])
 useEffect(()=>{const id=window.setInterval(()=>setItems(v=>[...v]),1000);return()=>window.clearInterval(id)},[])

 async function load(t:string,r:string){
  try{
   const all=await fetch(API+"/courses").then(x=>x.json())
   const cs=r==="teacher"?all.filter((c:Course)=>c.teacher_id===Number(localStorage.getItem("userId"))):await fetch(API+"/my-courses",{headers:{Authorization:"Bearer "+t}}).then(x=>x.json())
   setCourses(cs)
   if(cs[0])setCourseId(String(cs[0].id))
   const d=await Promise.all(cs.map((c:Course)=>fetch(API+"/assignments/"+c.id,{headers:{Authorization:"Bearer "+t}}).then(x=>x.ok?x.json():[])))
   setItems(d.flat())
  }catch{setError("Failed to load assessments")}
 }

 async function create(e:React.FormEvent){
  e.preventDefault()
  const t=localStorage.getItem("token");if(!t)return
  if((start&&!end)||(!start&&end)){setError("Set both start and end time");return}
  if(duration&&!start){setError("Start time is required for a duration");return}
  try{
   setError("")
   const b=new FormData()
   b.append("course_id",courseId);b.append("title",title);b.append("description",description);b.append("type",type)
   if(start)b.append("start_time",new Date(start).toISOString())
   if(end)b.append("end_time",new Date(end).toISOString())
   if(duration)b.append("duration_minutes",duration)
   if(handout)b.append("file",handout)
   const r=await fetch(API+"/assignments",{method:"POST",headers:{Authorization:"Bearer "+t},body:b})
   const d=await r.json();if(!r.ok)throw new Error(d.detail||"Creation failed")
   setMessage("Assessment created successfully");setShow(false);setTitle("");setDescription("");setStart("");setEnd("");setDuration("");setHandout(null);load(t,"teacher")
  }catch(e){setError(e instanceof Error?e.message:"Creation failed")}
 }

 async function submit(id:number){
  const t=localStorage.getItem("token");if(!t)return
  if(!answer.trim()&&!submissionFile){setError("Write an answer or upload a PDF");return}
  try{
   setError("")
   const b=new FormData();b.append("assignment_id",String(id));b.append("answer",answer)
   if(submissionFile)b.append("file",submissionFile)
   const r=await fetch(API+"/submissions",{method:"POST",headers:{Authorization:"Bearer "+t},body:b})
   const d=await r.json();if(!r.ok)throw new Error(d.detail||"Submission failed")
   setMessage("Submission successful");setSelected(null);setAnswer("");setSubmissionFile(null);load(t,"student")
  }catch(e){setError(e instanceof Error?e.message:"Submission failed")}
 }

 async function openPdf(id:string){
  const t=localStorage.getItem("token");if(!t)return navigate("/login")
  try{
   const r=await fetch(API+"/resources/"+id+"/download",{headers:{Authorization:"Bearer "+t}})
   if(!r.ok)throw new Error("Unable to open PDF")
   const blob=await r.blob();const url=URL.createObjectURL(blob);window.open(url,"_blank","noopener,noreferrer");setTimeout(()=>URL.revokeObjectURL(url),60000)
  }catch(e){setError(e instanceof Error?e.message:"Unable to open PDF")}
 }

 function fmt(v:string|null){return v?new Date(v).toLocaleString([],{dateStyle:"medium",timeStyle:"short"}):"No deadline"}
 function remaining(v:string|null){if(!v)return "";const ms=new Date(v).getTime()-Date.now();if(ms<=0)return "Time expired";const s=Math.floor(ms/1000),d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60),sec=s%60;return d?`${d}d ${h}h ${m}m`:h?`${h}h ${m}m`:m?`${m}m ${sec}s`:`${sec}s`}
 function logout(){localStorage.clear();navigate("/login")}

 return <div className="min-h-screen bg-[#070b14] text-white">
  <aside className="fixed left-0 top-0 hidden h-screen w-64 border-r border-white/10 bg-[#0b101a] p-5 lg:block"><Brand/><nav className="mt-8 space-y-2">
   <Nav onClick={()=>navigate(role==="teacher"?"/teacher":"/dashboard")} icon={<LayoutDashboard size={18}/>} text="Dashboard"/>
   <Nav onClick={()=>navigate(role==="teacher"?"/teacher":"/courses")} icon={<BookOpen size={18}/>} text="My Courses"/>
   <Nav active onClick={()=>{}} icon={<ClipboardList size={18}/>} text="Assignments"/>
   <Nav onClick={()=>navigate("/marks")} icon={<Award size={18}/>} text={role==="teacher"?"Student Marks":"Marks"}/>
   <Nav onClick={()=>navigate("/search")} icon={<Search size={18}/>} text="AI Search"/>
  </nav><button onClick={logout} className="nav absolute bottom-6 left-5 right-5"><LogOut size={18}/>Logout</button></aside>
  <main className="lg:ml-64">
   <header className="border-b border-white/10 px-6 py-5 lg:px-10"><p className="text-sm text-white/40">{role==="teacher"?"Teacher":"Student"}</p><h2 className="mt-1 text-2xl font-semibold">Assignments & Tests</h2></header>
   <section className="p-6 lg:p-10">
    <div className="flex flex-wrap justify-between gap-3"><div><h3 className="text-xl font-semibold">{role==="teacher"?"Manage Assessments":"Your Assessments"}</h3><p className="mt-1 text-sm text-white/40">Assignments, tests, handouts and PDF submissions.</p></div>{role==="teacher"&&<button onClick={()=>setShow(true)} className="flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-medium text-black"><Plus size={17}/>Create Assessment</button>}</div>
    {message&&<Msg text={message} ok/>}{error&&<Msg text={error}/>}
    {show&&<div className="mt-6 rounded-2xl border border-white/10 p-6"><div className="mb-6 flex justify-between"><h3 className="font-semibold">Create Assessment</h3><button onClick={()=>setShow(false)}><X size={19}/></button></div>
     <form onSubmit={create} className="space-y-5">
      <Field label="Course"><select value={courseId} onChange={e=>setCourseId(e.target.value)} className="input">{courses.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select></Field>
      <Field label="Type"><select value={type} onChange={e=>setType(e.target.value)} className="input"><option value="assignment">Assignment</option><option value="test">Test</option></select></Field>
      <Field label="Title"><input value={title} onChange={e=>setTitle(e.target.value)} required className="input" placeholder="e.g. Process Scheduling Assignment"/></Field>
      <Field label="Instructions"><textarea value={description} onChange={e=>setDescription(e.target.value)} required rows={4} className="input resize-none" placeholder="Add instructions for students..."/></Field>
      <div className="grid gap-4 md:grid-cols-3"><Field label="Opens"><input type="datetime-local" value={start} onChange={e=>setStart(e.target.value)} className="input"/></Field><Field label="Closes"><input type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)} className="input"/></Field><Field label="Duration (min)"><input type="number" min="1" value={duration} onChange={e=>setDuration(e.target.value)} placeholder="60" className="input"/></Field></div>
      <Field label="Assignment Handout / Question PDF"><input type="file" accept=".pdf,application/pdf" onChange={e=>setHandout(e.target.files?.[0]||null)} className="block w-full text-sm text-white/50"/></Field>
      <p className="text-xs text-white/30">Optional PDF for assignment questions, notes or instructions. Students can open it from the assessment.</p>
      <button disabled={!courseId} className="w-full rounded-xl bg-white py-3 text-sm font-medium text-black">{handout?<><Upload size={15} className="mr-2 inline"/>Create & Upload</>:"Create Assessment"}</button>
     </form>
    </div>}
    <div className="mt-8 space-y-4">{items.map(a=><div key={a.id} className="rounded-2xl border border-white/10 bg-white/[0.035] p-6">
      <div className="flex flex-col gap-4 md:flex-row md:justify-between"><div className="min-w-0"><span className="text-xs uppercase tracking-wider text-white/30">{a.type} · {courses.find(x=>x.id===a.course_id)?.title||"Course #"+a.course_id}</span><h4 className="mt-2 text-lg font-medium">{a.title}</h4><p className="mt-2 text-sm text-white/40">{a.description}</p>
       <div className="mt-4 flex flex-wrap gap-4 text-xs text-white/40"><span className="flex items-center gap-1"><Clock size={14}/>{a.start_time?"Opens "+fmt(a.start_time):"Open now"}</span><span>Deadline: {fmt(a.deadline)}</span><span>Duration: {a.duration_minutes?a.duration_minutes+" min":"No limit"}</span>{role==="student"&&a.status==="open"&&!a.submitted&&<span className="text-white/70">Time left: {remaining(a.deadline)}</span>}</div>
       {a.handout&&<button onClick={()=>openPdf(a.handout!.id)} className="mt-4 flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm hover:bg-white/5"><FileText size={15}/>{a.handout.title}<Download size={14}/></button>}
      </div>{role==="student"&&<div><span className="rounded-full bg-white/10 px-3 py-1 text-xs">{a.submitted?"submitted":a.status}</span>{a.status==="open"&&!a.submitted&&<button onClick={()=>setSelected(selected===a.id?null:a.id)} className="mt-3 flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-medium text-black"><Send size={16}/>{selected===a.id?"Close":"Submit"}</button>}</div>}</div>
      {selected===a.id&&a.status==="open"&&!a.submitted&&<div className="mt-6 border-t border-white/10 pt-6"><textarea value={answer} onChange={e=>setAnswer(e.target.value)} rows={6} className="input resize-none" placeholder="Write your answer here..."/>
       <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.02] p-4"><p className="mb-2 text-sm font-medium">Attach PDF submission <span className="text-white/30">(optional)</span></p><input type="file" accept=".pdf,application/pdf" onChange={e=>setSubmissionFile(e.target.files?.[0]||null)} className="block w-full text-sm text-white/50"/><p className="mt-2 text-xs text-white/30">Upload your solved assignment, handwritten work or supporting document.</p></div>
       <button onClick={()=>submit(a.id)} className="mt-4 rounded-xl bg-white px-6 py-3 text-sm font-medium text-black">Submit Assessment</button>
      </div>}
     </div>)}</div>
   </section>
  </main>
 </div>
}
function Brand(){return <div className="flex items-center gap-3 px-3 py-4"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-black"><BookOpen size={21}/></div><div><h1 className="font-semibold">LMS</h1><p className="text-xs text-white/40">Learning Platform</p></div></div>}
function Nav({onClick,active,icon,text}:{onClick:()=>void;active?:boolean;icon:React.ReactNode;text:string}){return <button onClick={onClick} className={"nav "+(active?"active":"")}>{icon}{text}</button>}
function Field({label,children}:{label:string;children:React.ReactNode}){return <div><label className="mb-2 block text-sm text-white/60">{label}</label>{children}</div>}
function Msg({text,ok=false}:{text:string;ok?:boolean}){return <div className={"mt-6 rounded-xl border px-4 py-3 text-sm "+(ok?"border-green-400/20 bg-green-400/10 text-green-300":"border-red-400/20 bg-red-400/10 text-red-300")}>{text}</div>}