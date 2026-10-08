import { useEffect, useState } from "react"
import { BookOpen, Check, Download, FileText, Image, Presentation, Table2, File, RefreshCw } from "lucide-react"
import { useNavigate } from "react-router-dom"
import AppLayout from "../components/AppLayout"
import { apiJson, ApiError } from "../api"

type Course={id:number;title:string;description:string;teacher_id:number}
type Resource={id:string;title:string;filename:string;content_type:string;size:number;processing_status:string;extraction_status:string;indexing_status:string;error_message?:string|null;page_count?:number;slide_count?:number;ocr_status?:string}

export default function Courses(){
 const navigate=useNavigate()
 const role=localStorage.getItem("role")||"student"
 const [courses,setCourses]=useState<Course[]>([])
 const [mine,setMine]=useState<Course[]>([])
 const [res,setRes]=useState<Record<number,Resource[]>>({})
 const [error,setError]=useState("")
 const [loading,setLoading]=useState(true)

 async function load(){
  setLoading(true);setError("")
  try{
   const all=await apiJson<Course[]>("/courses?page=1&page_size=100")
   setCourses(all)
   const own=role==="student"?await apiJson<Course[]>("/my-courses"):all.filter(c=>c.teacher_id===Number(localStorage.getItem("userId")))
   setMine(own)
   const data=await apiJson<Record<number,Resource[]>>("/my-course-resources")
   setRes(data)
  }catch(e){setError(e instanceof Error?e.message:"Failed to load courses")}
  finally{setLoading(false)}
 }
 useEffect(()=>{if(!localStorage.getItem("token")){navigate("/login");return}load()},[navigate])

 async function enroll(id:number){
  try{await apiJson("/enroll",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({course_id:id})});await load()}catch(e){setError(e instanceof Error?e.message:"Enrollment failed")}
 }
 async function openResource(id:string){
  try{
   const {response}=await import("../api").then(m=>m.apiFetch("/resources/"+id+"/download",{},30000))
   const blob=await response.blob();const url=URL.createObjectURL(blob);window.open(url,"_blank","noopener,noreferrer");window.setTimeout(()=>URL.revokeObjectURL(url),60000)
  }catch(e){setError(e instanceof ApiError?e.message:"Unable to open material")}
 }

 return <AppLayout title="Course Library" subtitle={role==="teacher"?"Teaching Workspace":"Learning Materials"}>
  <section className="lms-grid min-h-[calc(100vh-76px)] p-4 sm:p-6 lg:p-10">
   <div className="mx-auto max-w-7xl">
    {error&&<div role="alert" className="mb-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">{error}<button onClick={load} className="ml-3 underline">Retry</button></div>}
    <div className="flex items-end justify-between gap-4"><div><h2 className="text-xl font-semibold">{role==="student"?"Available Courses":"My Courses"}</h2><p className="mt-1 text-sm text-white/40">Access searchable course materials and processing status.</p></div><button onClick={load} className="lms-btn-secondary rounded-xl px-3 py-2 text-sm"><RefreshCw size={15}/>Refresh</button></div>
    {loading?<div className="mt-8 lms-empty rounded-2xl p-10 text-center text-sm text-white/40">Loading courses...</div>:<div className="mt-7 grid gap-5 md:grid-cols-2 xl:grid-cols-3">{courses.map(course=>{const enrolled=mine.some(c=>c.id===course.id);const materials=res[course.id]||[];return <article key={course.id} className="lms-card rounded-2xl p-6"><div className="flex items-start justify-between"><div className="lms-icon flex h-11 w-11 items-center justify-center rounded-xl"><BookOpen size={20}/></div>{role==="student"&&enrolled&&<span className="flex items-center gap-1 rounded-full bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300"><Check size={13}/>Enrolled</span>}</div><h3 className="mt-5 text-lg font-medium">{course.title}</h3><p className="mt-2 text-sm leading-6 text-white/40">{course.description}</p>{role==="student"&&!enrolled?<button onClick={()=>enroll(course.id)} className="lms-btn-primary mt-6 w-full rounded-xl py-3 text-sm">Enroll now</button>:enrolled&&<div className="mt-6 border-t border-white/10 pt-5"><p className="text-sm font-medium">Learning materials</p><div className="mt-3 space-y-2">{materials.length?materials.map(resource=><div key={resource.id} className="rounded-xl border border-white/10 bg-white/[.02] p-3"><div className="flex items-center gap-3"><MaterialIcon type={resource.content_type}/><div className="min-w-0 flex-1"><p className="truncate text-sm">{resource.title}</p><p className="mt-1 text-[11px] text-white/30">{formatBytes(resource.size)} · {resource.processing_status}</p></div>{resource.processing_status==="READY"&&<button onClick={()=>openResource(resource.id)} className="lms-btn-secondary rounded-lg p-2" aria-label={"Open "+resource.title}><Download size={14}/></button>}</div>{resource.processing_status==="FAILED"&&<p className="mt-2 text-xs text-red-300">{resource.error_message||"Processing failed"}</p>}</div>):<p className="mt-2 text-xs text-white/30">No materials uploaded yet.</p>}</div></div>}</article>})}</div>}
   </div>
  </section>
 </AppLayout>
}
function MaterialIcon({type}:{type:string}){if(type.startsWith("image/"))return <Image size={17} className="shrink-0 text-cyan-300"/>;if(type.includes("presentation"))return <Presentation size={17} className="shrink-0 text-orange-300"/>;if(type.includes("spreadsheet")||type.includes("csv"))return <Table2 size={17} className="shrink-0 text-emerald-300"/>;if(type.includes("pdf")||type.includes("word")||type.includes("text"))return <FileText size={17} className="shrink-0 text-violet-300"/>;return <File size={17} className="shrink-0"/>}
function formatBytes(value:number){if(value<1024)return value+" B";if(value<1024*1024)return(value/1024).toFixed(1)+" KB";return(value/1024/1024).toFixed(1)+" MB"}
