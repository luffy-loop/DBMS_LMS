import { useState } from "react"
import type { FormEvent } from "react"
import { BookOpen, LayoutDashboard, ClipboardList, Award, Search, LogOut, User, Sparkles, ArrowRight, BrainCircuit } from "lucide-react"
import { useNavigate } from "react-router-dom"

const API = "http://127.0.0.1:8000"

type Source = { title:string; type:string; course_id:number; distance:number }
type Response = { answer:string; confidence:string; sources:Source[] }

export default function StudyCopilot(){
  const navigate=useNavigate()
  const [question,setQuestion]=useState("")
  const [response,setResponse]=useState<Response|null>(null)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState("")
  const role=localStorage.getItem("role")||"student"
  const name=localStorage.getItem("name")||"User"

  async function ask(e?:FormEvent){
    e?.preventDefault()
    const token=localStorage.getItem("token")
    if(!token){navigate("/login");return}
    if(!question.trim())return
    setLoading(true);setError("");setResponse(null)
    try{
      const r=await fetch(API+"/study-copilot",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+token},body:JSON.stringify({question})})
      const d=await r.json()
      if(!r.ok)throw new Error(d.detail||"Copilot failed")
      setResponse(d)
    }catch(e){setError(e instanceof Error?e.message:"Copilot failed")}
    finally{setLoading(false)}
  }

  function logout(){localStorage.clear();navigate("/login")}

  return <div className="lms-shell min-h-screen text-white">
    <aside className="lms-sidebar fixed left-0 top-0 hidden h-screen w-64 border-r p-5 lg:block">
      <div className="flex items-center gap-3 px-3 py-4"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-black"><BookOpen size={21}/></div><div><h1 className="font-semibold">LMS</h1><p className="text-xs text-white/40">Learning Platform</p></div></div>
      <nav className="mt-8 space-y-2">
        <Nav onClick={()=>navigate(role==="teacher"?"/teacher":role==="admin"?"/admin":"/dashboard")} icon={<LayoutDashboard size={18}/>} text="Dashboard"/>
        <Nav onClick={()=>navigate("/courses")} icon={<BookOpen size={18}/>} text="My Courses"/>
        <Nav onClick={()=>navigate("/assignments")} icon={<ClipboardList size={18}/>} text="Assignments"/>
        <Nav onClick={()=>navigate("/marks")} icon={<Award size={18}/>} text="Marks"/>
        <Nav onClick={()=>navigate("/search")} icon={<Search size={18}/>} text="AI Search"/>
        <Nav active icon={<BrainCircuit size={18}/>} text="Study Copilot"/>
      </nav>
      <button onClick={logout} className="lms-nav absolute bottom-6 left-5 right-5"><LogOut size={18}/>Logout</button>
    </aside>

    <main className="lg:ml-64">
      <header className="lms-topbar sticky top-0 z-10 border-b px-6 py-5 lg:px-10"><p className="text-sm text-white/40">AI Study Copilot</p><div className="flex items-center justify-between gap-4"><h2 className="mt-1 text-2xl font-semibold">Study with your course knowledge</h2><div className="hidden items-center gap-3 sm:flex"><span className="text-sm text-white/40">{name}</span><div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5"><User size={18}/></div></div></div></header>

      <section className="lms-grid min-h-[calc(100vh-90px)] p-6 lg:p-10">
        <div className="mx-auto max-w-5xl">
          <div className="lms-hero rounded-3xl p-7 lg:p-10">
            <div className="relative z-[1]">
              <div className="flex items-start gap-4"><div className="lms-icon flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"><Sparkles size={22}/></div><div><p className="text-sm font-medium text-violet-300">Retrieval-powered learning</p><h3 className="mt-1 text-2xl font-semibold">Ask anything from your materials.</h3><p className="mt-2 max-w-2xl text-sm leading-6 text-white/45">The Copilot searches your uploaded course content and builds an answer from the most relevant passages.</p></div></div>
              <form onSubmit={ask} className="mt-8">
                <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-black/20 p-2 sm:flex-row"><input value={question} onChange={e=>setQuestion(e.target.value)} className="lms-input flex-1 border-0 bg-transparent focus:box-shadow-none" placeholder="e.g. Explain normalization and why 3NF matters"/><button disabled={loading} className="lms-btn-primary rounded-xl px-6 py-3 text-sm font-medium disabled:cursor-wait disabled:opacity-60"><Sparkles size={16}/>{loading?"Thinking...":"Ask Copilot"}</button></div>
              </form>
              <div className="mt-5 flex flex-wrap gap-2">
                {["Explain normalization","What is a primary key?","How does indexing work?"].map(q=><button key={q} onClick={()=>{setQuestion(q);setTimeout(()=>ask(),0)}} className="lms-btn-secondary rounded-full px-3 py-2 text-xs">{q}</button>)}
              </div>
            </div>
          </div>

          {error&&<div className="mt-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">{error}</div>}

          {response&&<div className="mt-7 grid gap-5 lg:grid-cols-[1fr_340px]">
            <div className="lms-card rounded-3xl p-7">
              <div className="flex items-center justify-between gap-4"><div className="flex items-center gap-2 text-violet-300"><BrainCircuit size={18}/><span className="text-sm font-medium">Copilot answer</span></div><span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/45">{response.confidence} confidence</span></div>
              <div className="mt-6 whitespace-pre-line text-[15px] leading-8 text-white/75">{response.answer}</div>
              <div className="mt-7 rounded-2xl border border-violet-400/10 bg-violet-400/[.04] p-4 text-sm text-white/45">This answer is grounded in indexed LMS materials. Open AI Search to explore the retrieved resources in more detail.</div>
              <button onClick={()=>navigate("/search")} className="lms-btn-secondary mt-5 rounded-xl px-4 py-2.5 text-sm">Explore sources <ArrowRight size={15}/></button>
            </div>
            <div className="lms-card rounded-3xl p-6">
              <p className="text-sm font-medium">Retrieved sources</p><p className="mt-1 text-xs text-white/35">{response.sources.length} relevant resource{response.sources.length===1?"":"s"} found</p>
              <div className="mt-5 space-y-3">{response.sources.map((s,i)=><div key={i} className="rounded-xl border border-white/10 bg-white/[.025] p-4"><p className="text-sm font-medium">{s.title}</p><p className="mt-1 text-xs text-white/35">{s.type} · Course {s.course_id}</p></div>)}</div>
            </div>
          </div>}

          {!response&&!loading&&!error&&<div className="mt-7 grid gap-4 md:grid-cols-3">{[["Understand","Ask for a concept explanation grounded in your notes."],["Revise","Turn difficult topics into focused revision questions."],["Discover","Find the exact course resources connected to a topic."]].map(([a,b])=><div key={a} className="lms-card rounded-2xl p-5"><p className="font-medium">{a}</p><p className="mt-2 text-sm leading-6 text-white/35">{b}</p></div>)}</div>}
        </div>
      </section>
    </main>
  </div>
}

function Nav({onClick,active,icon,text}:{onClick?:()=>void;active?:boolean;icon:React.ReactNode;text:string}){return <button onClick={onClick} className={"lms-nav "+(active?"active":"")}>{icon}{text}</button>}
