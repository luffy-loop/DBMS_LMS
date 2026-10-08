import { useEffect, useRef, useState } from "react"
import { ArrowRight, BrainCircuit, Ban, Loader2, Sparkles, BookOpen } from "lucide-react"
import { useNavigate } from "react-router-dom"
import AppLayout from "../components/AppLayout"
import { apiJson, ApiError } from "../api"

type Course={id:number;title:string}
type Source={title:string;type:string;course_id:number;distance:number}
type Response={answer:string;confidence:string;sources:Source[];mode?:string;metrics?:Record<string,number>}
type UiState="IDLE"|"SEARCHING"|"COMPLETED"|"FAILED"|"CANCELLED"

export default function StudyCopilot(){
  const navigate=useNavigate()
  const [question,setQuestion]=useState("")
  const [courseId,setCourseId]=useState("")
  const [courses,setCourses]=useState<Course[]>([])
  const [response,setResponse]=useState<Response|null>(null)
  const [state,setState]=useState<UiState>("IDLE")
  const [error,setError]=useState("")
  const controller=useRef<AbortController|null>(null)

  useEffect(()=>{
    if(!localStorage.getItem("token")){navigate("/login");return}
    apiJson<Course[]>("/my-courses",{},10000).then(setCourses).catch(()=>setCourses([]))
    return()=>controller.current?.abort()
  },[navigate])

  function messageFor(errorValue:unknown){
    if(errorValue instanceof ApiError){
      if(errorValue.status===503)return "The LMS server is temporarily unavailable. Please try again."
      if(errorValue.status===504)return "The AI request took too long. Please retry."
      if(errorValue.status===401)return "Your session has expired. Please sign in again."
      if(errorValue.status===403)return "You don't have access to that course."
      if(errorValue.status===422)return "Please enter a valid question."
      if(errorValue.status===408)return "The request timed out or was cancelled."
      return errorValue.message
    }
    return errorValue instanceof Error?errorValue.message:"The study assistant could not answer right now."
  }

  async function ask(value?:string){
    const q=(value??question).trim()
    if(!q){setError("Please enter a question.");return}
    controller.current?.abort()
    const next=new AbortController()
    controller.current=next
    setQuestion(q);setState("SEARCHING");setError("");setResponse(null)
    try{
      const data=await apiJson<Response>("/study-copilot",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q,course_id:courseId?Number(courseId):null}),signal:next.signal},16000)
      setResponse(data);setState("COMPLETED")
    }catch(e){
      if(next.signal.aborted){setState("CANCELLED");return}
      setState("FAILED");setError(messageFor(e))
    }finally{if(controller.current===next)controller.current=null}
  }

  function cancel(){controller.current?.abort();setState("CANCELLED")}
  const quick=["Explain normalization simply","What is recursion?","Help me understand pointers in C","What is PID control?"]

  return <AppLayout title="Ask anything" subtitle="AI Study Assistant">
    <section className="lms-grid min-h-[calc(100vh-76px)] p-4 sm:p-6 lg:p-10">
      <div className="mx-auto max-w-5xl">
        <div className="lms-hero rounded-3xl p-6 sm:p-8 lg:p-10">
          <div className="flex items-start gap-4"><div className="lms-icon flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"><Sparkles size={22}/></div><div><p className="text-sm font-medium text-violet-300">General study assistant</p><h2 className="mt-1 text-2xl font-semibold">Ask anything. Clear your doubts.</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-white/45">Ask concepts, coding questions, exam doubts or step-by-step problems. Course material is optional context, not a requirement.</p></div></div>
          <form onSubmit={e=>{e.preventDefault();ask()}} className="mt-8">
            <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-black/20 p-2">
              <div className="flex flex-col gap-3 sm:flex-row"><input value={question} onChange={e=>setQuestion(e.target.value)} className="lms-input flex-1 border-0 bg-transparent" placeholder="Ask anything..." aria-label="AI question"/>{state==="SEARCHING"?<button type="button" onClick={cancel} className="lms-btn-secondary rounded-xl px-6 py-3 text-sm"><Ban size={16}/>Cancel</button>:<button type="submit" className="lms-btn-primary rounded-xl px-6 py-3 text-sm"><Sparkles size={16}/>Ask AI</button>}</div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center"><div className="flex min-w-0 flex-1 items-center gap-2 text-xs text-white/35"><BookOpen size={15}/><span>Optional course context</span></div><select value={courseId} onChange={e=>setCourseId(e.target.value)} className="lms-input sm:max-w-xs"><option value="">No course context</option>{courses.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select></div>
            </div>
          </form>
          <div className="mt-5 flex flex-wrap gap-2">{quick.map(q=><button type="button" key={q} onClick={()=>ask(q)} className="lms-btn-secondary rounded-full px-3 py-2 text-xs">{q}</button>)}</div>
        </div>

        {state==="SEARCHING"&&<div role="status" aria-live="polite" className="mt-5 rounded-2xl border border-white/10 bg-white/[.03] p-4 text-sm text-white/55"><span className="inline-flex items-center gap-2"><Loader2 size={16} className="animate-spin text-violet-300"/>Thinking through your question...</span></div>}
        {error&&<div role="alert" className="mt-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">{error}<button onClick={()=>ask()} className="ml-3 underline">Retry</button></div>}
        {state==="CANCELLED"&&<div role="status" className="mt-5 rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-200">Request cancelled. You can ask again.</div>}

        {response&&<div className="mt-7 grid gap-5 lg:grid-cols-[1fr_340px]">
          <div className="lms-card rounded-3xl p-6 sm:p-7"><div className="flex items-center justify-between gap-4"><div className="flex items-center gap-2 text-violet-300"><BrainCircuit size={18}/><span className="text-sm font-medium">AI answer</span></div><span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/45">{response.confidence} confidence</span></div><div className="mt-6 max-w-none whitespace-pre-line text-[15px] leading-8 text-white/75">{response.answer}</div><div className="mt-7 rounded-2xl border border-violet-400/10 bg-violet-400/[.04] p-4 text-sm text-white/45">{response.mode==="course materials"?"This answer uses your selected course context.":response.sources.length?"This answer uses general study knowledge, with optional course context.":"General study answer."}</div>{response.sources.length>0&&<button onClick={()=>navigate("/search")} className="lms-btn-secondary mt-5 rounded-xl px-4 py-2.5 text-sm">Explore sources <ArrowRight size={15}/></button>}</div>
          {response.sources.length>0&&<div className="lms-card rounded-3xl p-6"><p className="text-sm font-medium">Context used</p><p className="mt-1 text-xs text-white/35">{response.sources.length} source{response.sources.length===1?"":"s"}</p><div className="mt-5 space-y-3">{response.sources.map((s,i)=><div key={i} className="rounded-xl border border-white/10 bg-white/[.025] p-4"><p className="text-sm font-medium">{s.title}</p><p className="mt-1 text-xs text-white/35">{s.type}{s.course_id?" · Course "+s.course_id:""}</p></div>)}</div>{response.metrics&&<div className="mt-5 border-t border-white/10 pt-4 text-[11px] text-white/30">Search {response.metrics.vector_search_ms??0}ms · total {response.metrics.total_ms??0}ms</div>}</div>}
        </div>}
      </div>
    </section>
  </AppLayout>
}
