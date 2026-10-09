import { useEffect, useRef, useState } from "react"
import { Search, Sparkles, Loader2, Ban } from "lucide-react"
import AppLayout from "../components/AppLayout"
import { apiJson, ApiError } from "../api"

type Result={title:string;content:string;type:string;course_id:number;distance:number}
type Data={results:Result[];metrics?:Record<string,number>}

export default function AISearch(){
  const [query,setQuery]=useState("")
  const [data,setData]=useState<Data>({results:[]})
  const [state,setState]=useState<"IDLE"|"SEARCHING"|"COMPLETED"|"FAILED"|"CANCELLED">("IDLE")
  const [error,setError]=useState("")
  const controller=useRef<AbortController|null>(null)

  useEffect(()=>()=>controller.current?.abort(),[])

  async function search(event?:React.FormEvent){
    event?.preventDefault()
    if(!query.trim())return
    controller.current?.abort()
    const next=new AbortController()
    controller.current=next
    setState("SEARCHING");setError("");setData({results:[]})
    try{
      const result=await apiJson<Data>("/ai-search?q="+encodeURIComponent(query.trim()),{signal:next.signal},17000)
      setData(result);setState("COMPLETED")
    }catch(e){
      if(next.signal.aborted){setState("CANCELLED");return}
      setState("FAILED");setError(e instanceof ApiError&&e.status===504?"Search timed out. Retry with a narrower query.":e instanceof Error?e.message:"Search failed")
    }finally{if(controller.current===next)controller.current=null}
  }

  return <AppLayout title="Find learning material" subtitle="AI Search">
    <section className="lms-grid min-h-[calc(100vh-76px)] p-4 sm:p-6 lg:p-10">
      <div className="mx-auto max-w-5xl">
        <div className="lms-hero rounded-3xl p-6 sm:p-8">
          <div className="flex items-center gap-3"><div className="lms-icon flex h-11 w-11 items-center justify-center rounded-xl"><Sparkles size={20}/></div><div><h2 className="font-semibold">Semantic Search</h2><p className="text-sm text-white/40">Search only the learning material you are authorized to access.</p></div></div>
          <form onSubmit={search} className="mt-6 flex flex-col gap-3 sm:flex-row"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="e.g. explain database normalization" className="lms-input flex-1" aria-label="Search learning material"/>{state==="SEARCHING"?<button type="button" onClick={()=>{controller.current?.abort();setState("CANCELLED")}} className="lms-btn-secondary rounded-xl px-6 py-3 text-sm"><Ban size={16}/>Cancel</button>:<button className="lms-btn-primary rounded-xl px-6 py-3 text-sm"><Search size={17}/>Search</button>}</form>
        </div>
        {state==="SEARCHING"&&<div role="status" aria-live="polite" className="mt-5 rounded-2xl border border-white/10 bg-white/[.03] p-4 text-sm text-white/50"><span className="inline-flex items-center gap-2"><Loader2 size={16} className="animate-spin text-violet-300"/>Searching course material and ranking relevant passages...</span></div>}
        {error&&<div role="alert" className="mt-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">{error}<button onClick={()=>search()} className="ml-3 underline">Retry</button></div>}
        {state==="CANCELLED"&&<div role="status" className="mt-5 rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-200">Search cancelled.</div>}
        {data.results.length>0&&<div className="mt-7 space-y-4"><div className="flex items-center justify-between"><p className="text-sm text-white/40">Relevant results</p>{data.metrics&&<span className="text-[11px] text-white/25">total {data.metrics.total_ms ?? 0}ms · vector {data.metrics.vector_search_ms ?? 0}ms</span>}</div>{data.results.map((r,i)=><article key={r.title+"-"+r.course_id+"-"+i} className="lms-card rounded-2xl p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><span className="text-xs uppercase tracking-wider text-white/30">{r.type}</span><h3 className="mt-2 text-lg font-medium">{r.title}</h3></div><span className="rounded-full bg-white/10 px-3 py-1 text-xs text-white/50">Course {r.course_id}</span></div><p className="mt-3 text-sm leading-6 text-white/55">{r.content}</p></article>)}</div>}
        {state==="COMPLETED"&&data.results.length===0&&<div className="mt-7 rounded-2xl border border-white/10 bg-white/[.03] p-10 text-center text-white/40"><Search className="mx-auto mb-4" size={34}/><p>No relevant authorized material was found.</p></div>}
      </div>
    </section>
  </AppLayout>
}
