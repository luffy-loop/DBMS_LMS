import { useState } from "react"
import type { FormEvent } from "react"
import { BookOpen, LayoutDashboard, ClipboardList, Award, Search, LogOut, User, Sparkles, BrainCircuit, FileText, CheckCircle2, RotateCcw } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { API } from "../config"

type Source={title:string;type:string;course_id:number;distance?:number}
type Response={answer:string;confidence:string;mode:string;sources:Source[]}
type Notes={topic:string;summary:string;bullets:string[];key_terms:string[];exam_tip:string;mode:string;sources:Source[]}
type Q={id:number;question:string;context:string;options:string[];answer:string;source:string}

export default function StudyCopilot(){
 const navigate=useNavigate()
 const role=localStorage.getItem("role")||"student",name=localStorage.getItem("name")||"User"
 const [tab,setTab]=useState<"ask"|"notes"|"quiz">("ask")
 const [question,setQuestion]=useState(""),[response,setResponse]=useState<Response|null>(null)
 const [topic,setTopic]=useState(""),[notes,setNotes]=useState<Notes|null>(null)
 const [questions,setQuestions]=useState<Q[]>([]),[answers,setAnswers]=useState<Record<number,string>>({}),[score,setScore]=useState<number|null>(null)
 const [loading,setLoading]=useState(false),[error,setError]=useState("")

 async function ask(e?:FormEvent){e?.preventDefault();return askQuestion(question)}
 async function askQuestion(value:string){
  const next=value.trim();if(!next)return
  const token=localStorage.getItem("token");if(!token){navigate("/login");return}
  setLoading(true);setError("");setResponse(null)
  try{const r=await fetch(API+"/study-copilot",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+token},body:JSON.stringify({question:next})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"AI answer failed");setResponse(d)}catch(e){setError(e instanceof Error?e.message:"AI answer failed")}finally{setLoading(false)}
 }
 async function makeNotes(e?:FormEvent){e?.preventDefault();return makeNotesFor(topic)}
 async function makeNotesFor(value:string){
  const next=value.trim();if(!next)return
  const token=localStorage.getItem("token");if(!token){navigate("/login");return}
  setLoading(true);setError("");setNotes(null)
  try{const r=await fetch(API+"/study-notes",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+token},body:JSON.stringify({topic:next})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Quick notes failed");setNotes(d)}catch(e){setError(e instanceof Error?e.message:"Quick notes failed")}finally{setLoading(false)}
 }
 async function generateQuiz(){
  const token=localStorage.getItem("token");if(!token){navigate("/login");return}
  setLoading(true);setError("");setScore(null);setAnswers({})
  try{const r=await fetch(API+"/quiz/generate",{headers:{Authorization:"Bearer "+token}});const d=await r.json();if(!r.ok)throw new Error(d.detail||"Quiz generation failed");setQuestions(d.questions);setTab("quiz")}catch(e){setError(e instanceof Error?e.message:"Quiz generation failed")}finally{setLoading(false)}
 }
 function finish(){let s=0;questions.forEach(q=>{if(answers[q.id]===q.answer)s++});setScore(s)}
 function logout(){localStorage.clear();navigate("/login")}
 const quickQuestions=["What is a primary key?","Explain normalization","What is overfitting?"]
 const quickNotes=["Primary key","Normalization","ACID properties"]
 return <div className="lms-shell min-h-screen text-white">
  <aside className="lms-sidebar fixed left-0 top-0 hidden h-screen w-64 border-r p-5 lg:block">
   <div className="flex items-center gap-3 px-3 py-4"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-black"><BookOpen size={21}/></div><div><h1 className="font-semibold">LMS</h1><p className="text-xs text-white/40">Learning Platform</p></div></div>
   <nav className="mt-8 space-y-2">
    <Nav onClick={()=>navigate(role==="teacher"?"/teacher":role==="admin"?"/admin":"/dashboard")} icon={<LayoutDashboard size={18}/>} text="Dashboard"/>
    <Nav onClick={()=>navigate("/courses")} icon={<BookOpen size={18}/>} text="My Courses"/>
    <Nav onClick={()=>navigate("/assignments")} icon={<ClipboardList size={18}/>} text="Assignments"/>
    <Nav onClick={()=>navigate("/marks")} icon={<Award size={18}/>} text="Marks"/>
    <Nav onClick={()=>navigate("/search")} icon={<Search size={18}/>} text="AI Search"/>
    <Nav active icon={<BrainCircuit size={18}/>} text="AI Study"/>
    <Nav onClick={()=>navigate("/quiz")} icon={<Sparkles size={18}/>} text="Quiz Lab"/>
   </nav>
   <button onClick={logout} className="lms-nav absolute bottom-6 left-5 right-5"><LogOut size={18}/>Logout</button>
  </aside>
  <main className="lg:ml-64">
   <header className="lms-topbar sticky top-0 z-10 border-b px-6 py-5 lg:px-10"><div className="flex items-center justify-between gap-4"><div><p className="text-sm text-violet-300">AI Study Hub</p><h2 className="mt-1 text-2xl font-semibold">Ask, revise and test yourself</h2><p className="mt-1 text-sm text-white/40">Course-grounded answers plus fast study help for everyday questions.</p></div><div className="hidden items-center gap-3 sm:flex"><span className="text-sm text-white/40">{name}</span><div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5"><User size={18}/></div></div></div></header>
   <section className="lms-grid min-h-[calc(100vh-90px)] p-6 lg:p-10"><div className="mx-auto max-w-6xl">
    <div className="lms-hero rounded-3xl p-6 lg:p-8"><div className="relative z-[1] flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between"><div><div className="flex items-center gap-3"><div className="lms-icon flex h-12 w-12 items-center justify-center rounded-2xl"><BrainCircuit size={23}/></div><div><p className="text-sm font-medium text-violet-300">Your AI learning workspace</p><h3 className="mt-1 text-2xl font-semibold">What do you want to do?</h3></div></div><p className="mt-3 max-w-2xl text-sm leading-6 text-white/45">Ask a basic concept question, turn a topic into short notes, or generate a fresh revision quiz.</p></div><button onClick={()=>navigate("/quiz")} className="lms-btn-secondary rounded-xl px-4 py-3 text-sm"><Sparkles size={16}/>Full Quiz Lab</button></div>
     <div className="mt-7 grid gap-2 rounded-2xl border border-white/10 bg-black/20 p-2 sm:grid-cols-3">{[["ask","Ask AI",BrainCircuit],["notes","Quick Notes",FileText],["quiz","Quiz",Sparkles]].map(([id,label,Icon])=><button key={String(id)} onClick={()=>setTab(id as "ask"|"notes"|"quiz")} className={"flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm transition "+(tab===id?"bg-white text-black shadow-lg":"text-white/45 hover:bg-white/5 hover:text-white")}><Icon size={16}/>{String(label)}</button>)}</div>
    </div>
    {error&&<div className="mt-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">{error}</div>}
    {tab==="ask"&&<div className="mt-7 grid gap-5 lg:grid-cols-[1fr_320px]">
      <div className="lms-card rounded-3xl p-6 lg:p-8"><p className="text-sm text-white/40">Ask a question</p><form onSubmit={ask} className="mt-4"><div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-black/20 p-2 sm:flex-row"><input value={question} onChange={e=>setQuestion(e.target.value)} className="lms-input flex-1 border-0 bg-transparent" placeholder="e.g. What is a primary key?"/><button disabled={loading} className="lms-btn-primary rounded-xl px-6 py-3 text-sm">{loading?"Thinking...":"Ask AI"}<Sparkles size={16}/></button></div></form><div className="mt-5 flex flex-wrap gap-2">{quickQuestions.map(q=><button key={q} onClick={()=>{setQuestion(q);askQuestion(q)}} className="lms-btn-secondary rounded-full px-3 py-2 text-xs">{q}</button>)}</div>{response&&<div className="mt-7 rounded-2xl border border-violet-400/15 bg-violet-400/[.045] p-6"><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2 text-violet-300"><CheckCircle2 size={17}/><span className="text-sm font-medium">Answer</span></div><span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/40">{response.mode}</span></div><p className="mt-5 whitespace-pre-line text-[15px] leading-8 text-white/80">{response.answer}</p>{response.sources.length>0&&<div className="mt-6 flex flex-wrap gap-2">{response.sources.map((s,i)=><span key={i} className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/40">{s.title}</span>)}</div>}</div>}</div>
      <div className="space-y-4"><div className="lms-card rounded-3xl p-6"><p className="text-sm font-medium">Good for</p>{[["Concepts","What is a primary key?"],["Explanations","Why is 3NF useful?"],["Revision","Explain TCP vs UDP"]].map(([a,b])=><button key={a} onClick={()=>{setQuestion(b);askQuestion(b)}} className="mt-4 w-full rounded-xl border border-white/10 bg-white/[.025] p-4 text-left hover:border-violet-400/20"><p className="text-xs text-violet-300">{a}</p><p className="mt-1 text-sm text-white/60">{b}</p></button>)}</div></div>
    </div>}
    {tab==="notes"&&<div className="mt-7 grid gap-5 lg:grid-cols-[.9fr_1.1fr]"><div className="lms-card rounded-3xl p-6 lg:p-8"><div className="lms-icon flex h-11 w-11 items-center justify-center rounded-xl"><FileText size={20}/></div><h3 className="mt-5 text-xl font-semibold">Quick revision notes</h3><p className="mt-2 text-sm leading-6 text-white/40">Enter any topic. The assistant first checks your course material and can also explain common core concepts.</p><form onSubmit={makeNotes} className="mt-6 space-y-3"><input value={topic} onChange={e=>setTopic(e.target.value)} className="lms-input" placeholder="e.g. normalization"/><button disabled={loading} className="lms-btn-primary w-full rounded-xl py-3 text-sm">{loading?"Making notes...":"Make short notes"}<FileText size={16}/></button></form><div className="mt-5 flex flex-wrap gap-2">{quickNotes.map(q=><button key={q} onClick={()=>{setTopic(q);makeNotesFor(q)}} className="lms-btn-secondary rounded-full px-3 py-2 text-xs">{q}</button>)}</div></div>{notes?<div className="lms-card rounded-3xl p-6 lg:p-8"><div className="flex items-center justify-between"><div><p className="text-xs uppercase tracking-[.18em] text-violet-300">Quick notes</p><h3 className="mt-2 text-2xl font-semibold">{notes.topic}</h3></div><FileText className="text-violet-300" size={24}/></div><p className="mt-6 text-sm leading-7 text-white/70">{notes.summary}</p><div className="mt-6 space-y-3">{notes.bullets.map((b,i)=><div key={i} className="flex gap-3 rounded-xl border border-white/10 bg-white/[.025] p-4"><span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-400/10 text-xs text-violet-300">{i+1}</span><p className="text-sm leading-6 text-white/60">{b}</p></div>)}</div><div className="mt-6 flex flex-wrap gap-2">{notes.key_terms.map(t=><span key={t} className="rounded-full bg-cyan-400/10 px-3 py-1.5 text-xs text-cyan-200">{t}</span>)}</div><div className="mt-6 rounded-2xl border border-amber-300/10 bg-amber-300/[.04] p-4"><p className="text-xs font-medium uppercase tracking-wider text-amber-200">Exam tip</p><p className="mt-2 text-sm leading-6 text-white/55">{notes.exam_tip}</p></div></div>:<div className="lms-card flex min-h-[360px] items-center justify-center rounded-3xl p-8 text-center text-white/30"><div><FileText className="mx-auto mb-4" size={34}/><p>Choose a topic to build a compact revision sheet.</p></div></div>}</div>}
    {tab==="quiz"&&<div className="mt-7">{!questions.length?<div className="lms-card rounded-3xl p-8 text-center"><Sparkles className="mx-auto text-violet-300" size={36}/><h3 className="mt-4 text-xl font-semibold">AI Revision Quiz</h3><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-white/40">Generate concept-based questions from your enrolled learning content and core study knowledge.</p><button onClick={generateQuiz} disabled={loading} className="lms-btn-primary mt-6 rounded-xl px-6 py-3 text-sm">{loading?"Generating...":"Generate quiz"}<Sparkles size={16}/></button></div>:<div className="space-y-4"><div className="flex items-center justify-between"><p className="text-sm text-white/40">{questions.length} questions · {Object.keys(answers).length}/{questions.length} answered</p>{score!==null&&<button onClick={generateQuiz} className="lms-btn-secondary rounded-xl px-4 py-2 text-sm"><RotateCcw size={15}/>New quiz</button>}</div>{questions.map((q,i)=><div key={q.id} className="lms-card rounded-3xl p-6"><div className="flex items-start justify-between"><span className="rounded-full bg-violet-400/10 px-3 py-1 text-xs text-violet-300">Question {i+1}</span>{score!==null&&<CheckCircle2 className={answers[q.id]===q.answer?"text-emerald-300":"text-red-300"} size={19}/>}</div><p className="mt-5 text-sm leading-7 text-white/65">{q.context}</p><div className="mt-4 grid gap-2 sm:grid-cols-2">{q.options.map(o=><button key={o} disabled={score!==null} onClick={()=>setAnswers(a=>({...a,[q.id]:o}))} className={"rounded-xl border px-4 py-3 text-left text-sm transition "+(answers[q.id]===o?"border-violet-400/50 bg-violet-400/10 text-white":"border-white/10 bg-white/[.025] text-white/55 hover:bg-white/[.05]")}>{o}</button>)}</div>{score!==null&&<p className="mt-4 text-xs text-white/40">Answer: <span className="text-white/70">{q.answer}</span></p>}</div>)}{score===null?<button disabled={Object.keys(answers).length!==questions.length} onClick={finish} className="lms-btn-primary w-full rounded-2xl py-4 text-sm disabled:opacity-40">Submit quiz</button>:<div className="lms-card rounded-3xl p-8 text-center"><p className="text-sm text-white/40">Your score</p><p className="mt-2 text-5xl font-semibold">{score}/{questions.length}</p><p className="mt-3 text-sm text-white/45">{score===questions.length?"Perfect run.":"Review the answers and try another quiz."}</p></div>}</div>}</div>}
   </div></section>
  </main>
 </div>
}
function Nav({onClick,active,icon,text}:{onClick?:()=>void;active?:boolean;icon:React.ReactNode;text:string}){return <button onClick={onClick} className={"lms-nav "+(active?"active":"")}>{icon}{text}</button>}
