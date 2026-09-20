import { useState } from "react"
import { BookOpen, LayoutDashboard, ClipboardList, Award, Search, LogOut, User, BrainCircuit, Sparkles, RotateCcw, CheckCircle2, XCircle } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { API } from "../config"


type Q={id:number;question:string;context:string;options:string[];answer:string;source:string}

export default function QuizLab(){
  const navigate=useNavigate()
  const [questions,setQuestions]=useState<Q[]>([])
  const [answers,setAnswers]=useState<Record<number,string>>({})
  const [score,setScore]=useState<number|null>(null)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState("")
  const role=localStorage.getItem("role")||"student"
  const name=localStorage.getItem("name")||"User"

  async function generate(){
    const token=localStorage.getItem("token")
    if(!token){navigate("/login");return}
    setLoading(true);setError("");setScore(null);setAnswers({})
    try{
      const r=await fetch(API+"/quiz/generate",{headers:{Authorization:"Bearer "+token}})
      const d=await r.json()
      if(!r.ok)throw new Error(d.detail||"Quiz generation failed")
      setQuestions(d.questions)
    }catch(e){setError(e instanceof TypeError?"Unable to reach the quiz service. Check the deployed backend URL.":e instanceof Error?e.message:"Quiz generation failed")}
    finally{setLoading(false)}
  }

  function finish(){
    let s=0
    questions.forEach(q=>{if(answers[q.id]===q.answer)s++})
    setScore(s)
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
        <Nav onClick={()=>navigate("/copilot")} icon={<BrainCircuit size={18}/>} text="Study Copilot"/>
        <Nav onClick={()=>navigate("/copilot")} icon={<BrainCircuit size={18}/>} text="AI Study Hub"/><Nav active icon={<Sparkles size={18}/>} text="Quiz Lab"/>
      </nav>
      <button onClick={logout} className="lms-nav absolute bottom-6 left-5 right-5"><LogOut size={18}/>Logout</button>
    </aside>

    <main className="lg:ml-64">
      <header className="lms-topbar sticky top-0 z-10 border-b px-6 py-5 lg:px-10"><p className="text-sm text-white/40">AI Quiz Lab</p><div className="flex items-center justify-between gap-4"><h2 className="mt-1 text-2xl font-semibold">Test what you actually know</h2><div className="hidden items-center gap-3 sm:flex"><span className="text-sm text-white/40">{name}</span><div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5"><User size={18}/></div></div></div></header>

      <section className="lms-grid min-h-[calc(100vh-90px)] p-6 lg:p-10">
        <div className="mx-auto max-w-4xl">
          <div className="lms-hero rounded-3xl p-7 lg:p-10">
            <div className="relative z-[1] flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
              <div><div className="flex items-center gap-3"><div className="lms-icon flex h-12 w-12 items-center justify-center rounded-2xl"><Sparkles size={22}/></div><div><p className="text-sm font-medium text-violet-300">Retrieval-powered assessment</p><h3 className="mt-1 text-2xl font-semibold">Generate a fresh revision quiz.</h3></div></div><p className="mt-4 max-w-2xl text-sm leading-6 text-white/45">Questions are built from the indexed material already inside your LMS, so the quiz stays connected to your courses.</p></div>
              <button onClick={generate} disabled={loading} className="lms-btn-primary shrink-0 rounded-xl px-5 py-3 text-sm">{loading?"Generating...":"Generate quiz"}<Sparkles size={16}/></button>
            </div>
          </div>

          {error&&<div className="mt-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">{error}</div>}

          {questions.length>0&&<div className="mt-7 space-y-4">
            <div className="flex items-center justify-between"><p className="text-sm text-white/45">{questions.length} questions · {Object.keys(answers).length}/{questions.length} answered</p>{score!==null&&<button onClick={generate} className="lms-btn-secondary rounded-xl px-4 py-2 text-sm"><RotateCcw size={15}/>New quiz</button>}</div>
            {questions.map((q,i)=><div key={q.id} className="lms-card rounded-3xl p-6 lg:p-7">
              <div className="flex items-start justify-between gap-4"><span className="rounded-full border border-violet-400/15 bg-violet-400/10 px-3 py-1 text-xs text-violet-300">Question {i+1}</span>{score!==null&&(answers[q.id]===q.answer?<CheckCircle2 className="text-emerald-300" size={19}/>:<XCircle className="text-red-300" size={19}/>)}</div>
              <p className="mt-5 text-sm leading-6 text-white/45">"{q.context}"</p>
              <h4 className="mt-4 text-base font-medium">{q.question}</h4>
              <div className="mt-4 grid gap-2">{q.options.map(o=><button key={o} disabled={score!==null} onClick={()=>setAnswers(a=>({...a,[q.id]:o}))} className={"rounded-xl border px-4 py-3 text-left text-sm transition "+(answers[q.id]===o?"border-violet-400/50 bg-violet-400/10 text-white":"border-white/10 bg-white/[.025] text-white/60 hover:border-white/20 hover:bg-white/[.05]")}>{o}</button>)}</div>
              {score!==null&&<p className="mt-4 text-xs text-white/40">Correct resource: <span className="text-white/70">{q.answer}</span></p>}
            </div>)}
            {score===null?<button disabled={Object.keys(answers).length!==questions.length} onClick={finish} className="lms-btn-primary w-full rounded-2xl py-4 text-sm disabled:cursor-not-allowed disabled:opacity-40">Submit quiz</button>:<div className="lms-card rounded-3xl p-8 text-center"><p className="text-sm text-white/40">Your score</p><p className="mt-2 text-5xl font-semibold">{score}/{questions.length}</p><p className="mt-3 text-sm text-white/45">{score===questions.length?"Perfect run.":"Review the highlighted answers and retry with a fresh quiz."}</p></div>}
          </div>}

          {!questions.length&&!loading&&!error&&<div className="mt-7 grid gap-4 md:grid-cols-3">{[["Fresh","Generate a different question mix each time."],["Grounded","Use the course resources already indexed by LMS."],["Instant","Submit and see your score immediately."]].map(([a,b])=><div key={a} className="lms-card rounded-2xl p-5"><p className="font-medium">{a}</p><p className="mt-2 text-sm leading-6 text-white/35">{b}</p></div>)}</div>}
        </div>
      </section>
    </main>
  </div>
}

function Nav({onClick,active,icon,text}:{onClick?:()=>void;active?:boolean;icon:React.ReactNode;text:string}){return <button onClick={onClick} className={"lms-nav "+(active?"active":"")}>{icon}{text}</button>}
