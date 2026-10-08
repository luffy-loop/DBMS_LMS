import { useEffect, useRef, useState } from "react"
import { ArrowRight, BrainCircuit, Ban, Loader2, Sparkles } from "lucide-react"
import { useNavigate } from "react-router-dom"
import AppLayout from "../components/AppLayout"
import { apiJson, ApiError } from "../api"

type Source={title:string;type:string;course_id:number;distance:number}
type Response={answer:string;confidence:string;sources:Source[];mode?:string;metrics?:Record<string,number>}

export default function StudyCopilot(){
  const navigate=useNavigate()
  const [question,setQuestion]=useState("")
  const [response,setResponse]=useState<Response|null>(null)
  const [state,setState]=useState<"IDLE"|"SEARCHING"|"COMPLETED"|"FAILED"|"CANCELLED">("IDLE")
  const [error,setError]=useState("")
  const controller=useRef<AbortController|null>(null)

  useEffect(()=>()=>controller.current?.abort(),[])

  async function ask(e?:React.FormEvent){
    e?.preventDefault()
    if(!question.trim())return
    controller.current?.abort()
    const next=new AbortController()
    controller.current=next
    setState("SEARCHING");setError("");setResponse(null)
    try{
      const data=await apiJson<Response>("/study-copilot",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:question.trim()}),signal:next.signal},22000)
      setResponse(data);setState("COMPLETED")
    }catch(e){
      if(next.signal.aborted){setState("CANCELLED");return}
      setState("FAILED")
      setError(e instanceof ApiError && e.status===504?"This is taking longer than expected. Retry the question.":e instanceof Error?e.message:"Study Copilot failed")
    }finally{if(controller.current===next)controller.current=null}
  }

  function cancel(){controller.current?.abort();setState("CANCELLED")}

  return <AppLayout title="Study with your course knowledge" subtitle="AI Study Copilot">
    <section className="lms-grid min-h-[calc(100vh-76px)] p-4 sm:p-6 lg:p-10">
      <div className="mx-auto max-w-5xl">
        <div className="lms-hero rounded-3xl p-6 sm:p-8 lg:p-10">
          <div className="flex items-start gap-4"><div className="lms-icon flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"><Sparkles size={22}/></div><div><p className="text-sm font-medium text-violet-300">Retrieval-powered learning</p><h2 className="mt-1 text-2xl font-semibold">Ask anything from your authorized materials.</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-white/45">The answer is built from course content you are allowed to access, with a bounded context and a finite request timeout.</p></div></div>
          <form onSubmit={ask} className="mt-8">
            <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-black/20 p-2 sm:flex-row"><input value={question} onChange={e=>setQuestion(e.target.value)} className="lms-input flex-1 border-0 bg-transparent" placeholder="e.g. Explain normalization and why 3NF matters" aria-label="Study question"/>{state==="SEARCHING"?<button type="button" onClick={cancel} className="lms-btn-secondary rounded-xl px-6 py-3 text-sm"><Ban size={16}/>Cancel</button>:<button className="lms-btn-primary rounded-xl px-6 py-3 text-sm"><Sparkles size={16}/>Ask Copilot</button>}</div>
          </form>
          <div className="mt-5 flex flex-wrap gap-2">{["Explain normalization","What is a primary key?","How does indexing work?"].map(q=><button type="button" key={q} onClick={()=>{setQuestion(q);window.setTimeout(()=>ask(),0)}} className="lms-btn-secondary rounded-full px-3 py-2 text-xs">{q}</button>)}</div>
        </div>

        {state==="SEARCHING"&&<div role="status" aria-live="polite" className="mt-5 rounded-2xl border border-white/10 bg-white/[.03] p-4 text-sm text-white/55"><span className="inline-flex items-center gap-2"><Loader2 size={16} className="animate-spin text-violet-300"/>Searching your course materials and building an answer...</span></div>}
        {error&&<div role="alert" className="mt-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">{error}<button onClick={()=>ask()} className="ml-3 underline">Retry</button></div>}
        {state==="CANCELLED"&&<div role="status" className="mt-5 rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-200">Request cancelled. You can ask again.</div>}

        {response&&<div className="mt-7 grid gap-5 lg:grid-cols-[1fr_340px]">
          <div className="lms-card rounded-3xl p-6 sm:p-7"><div className="flex items-center justify-between gap-4"><div className="flex items-center gap-2 text-violet-300"><BrainCircuit size={18}/><span className="text-sm font-medium">Copilot answer</span></div><span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/45">{response.confidence} confidence</span></div><div className="mt-6 max-w-none whitespace-pre-line text-[15px] leading-8 text-white/75">{response.answer}</div><div className="mt-7 rounded-2xl border border-violet-400/10 bg-violet-400/[.04] p-4 text-sm text-white/45">{response.sources.length?"This answer is grounded in authorized LMS materials.":"No matching course resource was found."}</div>{response.sources.length>0&&<button onClick={()=>navigate("/search")} className="lms-btn-secondary mt-5 rounded-xl px-4 py-2.5 text-sm">Explore sources <ArrowRight size={15}/></button>}</div>
          <div className="lms-card rounded-3xl p-6"><p className="text-sm font-medium">Retrieved sources</p><p className="mt-1 text-xs text-white/35">{response.sources.length} relevant resource{response.sources.length===1?"":"s"}</p><div className="mt-5 space-y-3">{response.sources.map((s,i)=><div key={i} className="rounded-xl border border-white/10 bg-white/[.025] p-4"><p className="text-sm font-medium">{s.title}</p><p className="mt-1 text-xs text-white/35">{s.type} · Course {s.course_id}</p></div>)}</div>{response.metrics&&<div className="mt-5 border-t border-white/10 pt-4 text-[11px] text-white/30">Search {response.metrics.vector_search_ms ?? 0}ms · embedding {response.metrics.embedding_ms ?? 0}ms · total {response.metrics.total_ms ?? 0}ms</div>}</div>
        </div>}
      </div>
    </section>
  </AppLayout>
}
