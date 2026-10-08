import { useEffect, useState } from "react"
import { CheckCircle2, XCircle, Sparkles, Loader2, Ban, Send, Plus, Trash2 } from "lucide-react"
import AppLayout from "../components/AppLayout"
import { apiJson, ApiError } from "../api"
import { useNavigate } from "react-router-dom"

type Course={id:number;title:string;description:string}
type Question={id:number;question:string;context:string;options:string[];answer:string;source:string;max_marks:number;explanation?:string}
type JobResult={title:string;course_id:number;questions:Question[];metrics?:Record<string,number>}
type Job={job_id:string;status:string;result:JobResult|null;error?:{message?:string}|string|null}

export default function QuizLab() {
  const navigate=useNavigate()
  const role=localStorage.getItem("role")||"student"
  const [courses,setCourses]=useState<Course[]>([])
  const [courseId,setCourseId]=useState("")
  const [jobId,setJobId]=useState("")
  const [status,setStatus]=useState("IDLE")
  const [result,setResult]=useState<JobResult|null>(null)
  const [questions,setQuestions]=useState<Question[]>([])
  const [error,setError]=useState("")
  const [title,setTitle]=useState("Course Revision Quiz")
  const [description,setDescription]=useState("AI-generated quiz reviewed and published by the teacher.")
  const [startTime,setStartTime]=useState("")
  const [endTime,setEndTime]=useState("")
  const [duration,setDuration]=useState("")
  const [publishing,setPublishing]=useState(false)

  useEffect(() => {
    if(!localStorage.getItem("token")) { navigate("/login"); return }
    apiJson<Course[]>("/my-courses").then(data=>{setCourses(data);if(data[0])setCourseId(String(data[0].id))}).catch(()=>setError("Unable to load your courses"))
  },[navigate])

  useEffect(() => {
    if(!jobId || ["COMPLETED","FAILED","CANCELLED"].includes(status)) return
    const timer=window.setInterval(async()=>{
      try {
        const job=await apiJson<Job>("/quiz/jobs/"+jobId,{},10000)
        setStatus(job.status)
        if(job.result){setResult(job.result);setQuestions(job.result.questions)}
        if(job.status==="FAILED") setError(typeof job.error==="string"?job.error:job.error?.message||"Quiz generation failed")
      } catch(e) {
        if(e instanceof ApiError && e.status===404) setError("Quiz job is no longer available. Please start again.")
      }
    },1200)
    return()=>window.clearInterval(timer)
  },[jobId,status])

  async function generate() {
    if(!courseId) {setError("Select a course first");return}
    setError("");setResult(null);setQuestions([]);setStatus("QUEUED")
    try {
      const job=await apiJson<{job_id:string;status:string}>("/quiz/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({course_id:Number(courseId),question_count:5})},10000)
      setJobId(job.job_id);setStatus(job.status)
    } catch(e) {
      setStatus("FAILED");setError(e instanceof Error?e.message:"Unable to start quiz generation")
    }
  }

  async function cancel() {
    if(!jobId)return
    try { const job=await apiJson<Job>("/quiz/jobs/"+jobId+"/cancel",{method:"POST"});setStatus(job.status) } catch(e){setError(e instanceof Error?e.message:"Unable to cancel")}
  }

  function editQuestion(index:number,key:keyof Question,value:string|string[]) {
    setQuestions(list=>list.map((q,i)=>i===index?{...q,[key]:value}:q))
  }
  function removeQuestion(index:number) { setQuestions(list=>list.filter((_,i)=>i!==index)) }
  function addQuestion() { setQuestions(list=>[...list,{id:Date.now(),question:"New question",context:"Add course-grounded context before publishing.",options:["Option A","Option B","Option C","Option D"],answer:"Option A",source:"Teacher edited",max_marks:1}]) }

  async function publish() {
    if(!jobId || !questions.length || !courseId)return
    setPublishing(true);setError("")
    try {
      await apiJson("/quiz/jobs/"+jobId+"/assignment",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
        course_id:Number(courseId),title,description,start_time:startTime||null,end_time:endTime||null,duration_minutes:duration?Number(duration):null,
        questions:questions.map(q=>({id:q.id,question:q.question,options:q.options,answer:q.answer,max_marks:q.max_marks,explanation:q.explanation||""}))
      })},15000)
      setStatus("PUBLISHED")
    } catch(e) { setError(e instanceof Error?e.message:"Assignment publishing failed") }
    finally { setPublishing(false) }
  }

  const running=["QUEUED","RETRIEVING","GENERATING"].includes(status)
  const statusText={QUEUED:"Queued — your request is saved.",RETRIEVING:"Retrieving authorized course material...",GENERATING:"Generating and validating grounded questions...",COMPLETED:"Quiz ready for review.",FAILED:"Generation failed.",CANCELLED:"Generation cancelled.",PUBLISHED:"Assignment published."}[status]||"Ready"

  return <AppLayout title="AI Quiz Lab" subtitle="Assessment Studio">
    <section className="lms-grid min-h-[calc(100vh-76px)] p-4 sm:p-6 lg:p-10">
      <div className="mx-auto max-w-5xl">
        <div className="lms-hero rounded-3xl p-6 sm:p-8 lg:p-10">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div><p className="text-sm font-medium text-violet-300">Grounded assessment generation</p><h2 className="mt-1 text-2xl font-semibold">Generate, review, then publish.</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-white/45">Generation is a persisted job, so the browser never waits on one long request. Teachers must review the questions before publishing.</p></div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <select value={courseId} onChange={e=>setCourseId(e.target.value)} className="lms-input min-w-56"><option value="">Select course</option>{courses.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select>
              {running ? <button onClick={cancel} className="lms-btn-secondary rounded-xl px-5 py-3 text-sm"><Ban size={16}/>Cancel</button> : <button onClick={generate} disabled={!courseId || publishing} className="lms-btn-primary rounded-xl px-5 py-3 text-sm disabled:opacity-40"><Sparkles size={16}/>{status==="FAILED"?"Retry generation":"Generate quiz"}</button>}
            </div>
          </div>
        </div>

        {status!=="IDLE" && <div role="status" aria-live="polite" className="mt-5 rounded-2xl border border-white/10 bg-white/[.03] p-4">
          <div className="flex items-center gap-3">{running?<Loader2 className="animate-spin text-violet-300" size={18}/>:status==="COMPLETED"?<CheckCircle2 className="text-emerald-300" size={18}/>:status==="FAILED"?<XCircle className="text-red-300" size={18}/>:<Sparkles size={18} className="text-white/50"/>}<span className="text-sm">{statusText}</span></div>
        </div>}
        {error&&<div role="alert" className="mt-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">{error}</div>}

        {result && questions.length>0 && <div className="mt-7 space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm text-white/40">{questions.length} questions</p><h3 className="text-xl font-semibold">{result.title}</h3></div>{role==="teacher"&&<button onClick={addQuestion} className="lms-btn-secondary rounded-xl px-4 py-2.5 text-sm"><Plus size={15}/>Add question</button>}</div>
          {questions.map((q,index)=><div key={q.id} className="lms-card rounded-2xl p-5 sm:p-6">
            <div className="flex items-start gap-3"><span className="rounded-full border border-violet-400/15 bg-violet-400/10 px-3 py-1 text-xs text-violet-300">Question {index+1}</span>{role==="teacher"&&<button onClick={()=>removeQuestion(index)} className="ml-auto text-white/30 hover:text-red-300" aria-label={"Remove question "+(index+1)}><Trash2 size={16}/></button>}</div>
            {role==="teacher" ? <input value={q.question} onChange={e=>editQuestion(index,"question",e.target.value)} className="lms-input mt-4"/> : <h4 className="mt-4 font-medium">{q.question}</h4>}
            <p className="mt-4 rounded-xl border border-white/5 bg-white/[.02] p-4 text-sm leading-6 text-white/55">{q.context}</p>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">{q.options.map((option,optionIndex)=><div key={optionIndex} className="flex items-center gap-2"><input value={option} onChange={e=>{const next=[...q.options];next[optionIndex]=e.target.value;editQuestion(index,"options",next)}} className="lms-input" aria-label={"Question "+(index+1)+" option "+(optionIndex+1)}/>{role==="teacher"&&<button onClick={()=>editQuestion(index,"answer",option)} className={"rounded-lg px-2 py-2 text-xs " + (q.answer===option?"bg-emerald-400/15 text-emerald-300":"text-white/30 hover:text-white")} aria-label={"Set option "+(optionIndex+1)+" as correct"}>✓</button>}</div>)}</div>
            <p className="mt-3 text-xs text-white/30">Grounded source: {q.source}</p>
          </div>)}

          {role==="teacher" && status!=="PUBLISHED" && <div className="lms-card rounded-3xl p-6 sm:p-7">
            <div className="flex items-center gap-3"><Send size={18} className="text-violet-300"/><div><h3 className="font-semibold">Publish as assignment</h3><p className="text-xs text-white/35">Review is complete only when you explicitly publish.</p></div></div>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <Field label="Title"><input value={title} onChange={e=>setTitle(e.target.value)} className="lms-input"/></Field>
              <Field label="Duration (minutes)"><input type="number" min="1" value={duration} onChange={e=>setDuration(e.target.value)} className="lms-input"/></Field>
              <Field label="Description"><textarea value={description} onChange={e=>setDescription(e.target.value)} rows={3} className="lms-input sm:col-span-2"/></Field>
              <Field label="Start date/time"><input type="datetime-local" value={startTime} onChange={e=>setStartTime(e.target.value)} className="lms-input"/></Field>
              <Field label="Due date/time"><input type="datetime-local" value={endTime} onChange={e=>setEndTime(e.target.value)} className="lms-input"/></Field>
            </div>
            <button onClick={publish} disabled={publishing || !questions.length} className="lms-btn-primary mt-5 w-full rounded-xl py-3 text-sm disabled:opacity-40">{publishing?<><Loader2 size={16} className="animate-spin"/>Publishing...</>:<><Send size={16}/>Publish assignment to enrolled students</>}</button>
          </div>}
          {status==="PUBLISHED"&&<div role="status" className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-5 text-sm text-emerald-300">Assignment published. Enrolled students were notified automatically.</div>}
        </div>}
      </div>
    </section>
  </AppLayout>
}

function Field({label,children}:{label:string;children:React.ReactNode}) { return <label className="block"><span className="mb-2 block text-sm text-white/60">{label}</span>{children}</label> }
