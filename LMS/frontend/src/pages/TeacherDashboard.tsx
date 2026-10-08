import { useEffect, useMemo, useState } from "react"
import { BookOpen, Plus, Upload, X, Loader2, FileText, Image, Presentation, Table2, File, GripVertical } from "lucide-react"
import { useNavigate } from "react-router-dom"
import AppLayout from "../components/AppLayout"
import { apiJson, uploadFile, ApiError } from "../api"

type Course = { id:number; title:string; description:string; teacher_id:number }
type Overview = { courses:number; assessments:number; course_pdfs:number; submissions:number; pending_grading:number }
const ACCEPT = ".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.png,.jpg,.jpeg,.webp,.csv,.xlsx"
const MAX_FILES = 20

export default function TeacherDashboard() {
  const navigate = useNavigate()
  const [courses,setCourses] = useState<Course[]>([])
  const [overview,setOverview] = useState<Overview|null>(null)
  const [title,setTitle] = useState("")
  const [description,setDescription] = useState("")
  const [showCourse,setShowCourse] = useState(false)
  const [showUpload,setShowUpload] = useState(false)
  const [courseId,setCourseId] = useState("")
  const [files,setFiles] = useState<File[]>([])
  const [progress,setProgress] = useState<Record<string,number>>({})
  const [statuses,setStatuses] = useState<Record<string,string>>({})
  const [errors,setErrors] = useState<Record<string,string>>({})
  const [busy,setBusy] = useState(false)
  const [message,setMessage] = useState("")
  const [error,setError] = useState("")

  async function load() {
    try {
      const [courseData, overviewData] = await Promise.all([
        apiJson<Course[]>("/my-courses"),
        apiJson<Overview>("/teacher/overview"),
      ])
      setCourses(courseData)
      setOverview(overviewData)
      if (!courseId && courseData[0]) setCourseId(String(courseData[0].id))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load teaching workspace")
    }
  }

  useEffect(() => {
    if (!localStorage.getItem("token")) { navigate("/login"); return }
    if (localStorage.getItem("role") !== "teacher") { navigate("/dashboard"); return }
    load()
  }, [navigate])

  const selectedCourse = useMemo(() => courses.find(c => String(c.id) === courseId), [courses, courseId])

  async function createCourse(event:React.FormEvent) {
    event.preventDefault()
    setBusy(true); setError(""); setMessage("")
    try {
      await apiJson("/courses",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({title,description})})
      setTitle(""); setDescription(""); setShowCourse(false); setMessage("Course created successfully."); await load()
    } catch(e) { setError(e instanceof Error ? e.message : "Failed to create course") }
    finally { setBusy(false) }
  }

  function addFiles(list:FileList|null) {
    if (!list) return
    const next = Array.from(list)
    setFiles(current => {
      const merged = [...current, ...next]
      const seen = new Set<string>()
      return merged.filter(file => {
        const key = file.name + ":" + file.size + ":" + file.lastModified
        if (seen.has(key)) return false
        seen.add(key); return true
      }).slice(0, MAX_FILES)
    })
  }

  function removeFile(name:string) {
    setFiles(current => current.filter(file => file.name !== name))
    setProgress(current => { const next={...current}; delete next[name]; return next })
  }

  async function uploadAll() {
    if (!courseId || !files.length) return
    setBusy(true); setError(""); setMessage("")
    for (const file of files) {
      setStatuses(current => ({...current,[file.name]:"UPLOADING"}))
      setProgress(current => ({...current,[file.name]:0}))
      try {
        const result = await uploadFile("/courses/" + courseId + "/resources/batch", file, {titles:file.name.replace(/\.[^.]+$/,"")}, value => setProgress(current => ({...current,[file.name]:value})))
        const first = (result as {files?:Array<{id?:string;status:string;error?:string}>}).files?.[0]
        if (!first || first.status === "FAILED") throw new Error(first?.error || "Upload failed")
        setStatuses(current => ({...current,[file.name]:"PROCESSING"}))
        await waitForReady(first.id || "", file.name)
      } catch(e) {
        const message = e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Upload failed"
        setStatuses(current => ({...current,[file.name]:"FAILED"}))
        setErrors(current => ({...current,[file.name]:message}))
      }
    }
    setBusy(false)
    setMessage("Upload batch finished. Each file keeps its own success or failure state.")
    await load()
  }

  async function waitForReady(id:string, filename:string) {
    if (!id) return
    for(let attempt=0; attempt<60; attempt++) {
      try {
        const data = await apiJson<{status:string;error_message?:string|null}>("/resources/" + id + "/status",{},10000)
        setStatuses(current => ({...current,[filename]:data.status}))
        if (data.status === "READY") return
        if (data.status === "FAILED") {
          setErrors(current => ({...current,[filename]:data.error_message || "Processing failed"}))
          return
        }
      } catch {}
      await new Promise(resolve => window.setTimeout(resolve,2000))
    }
    setStatuses(current => ({...current,[filename]:"TIMEOUT"}))
    setErrors(current => ({...current,[filename]:"Processing is still running. You can leave this page and check the material status later."}))
  }

  const overall = files.length ? Math.round(files.reduce((sum,file) => sum + (progress[file.name] || 0),0) / files.length) : 0

  return <AppLayout title="Teacher Dashboard" subtitle="Teaching Workspace">
    <section className="lms-grid min-h-[calc(100vh-76px)] p-4 sm:p-6 lg:p-10">
      <div className="mx-auto max-w-7xl">
        {message && <div role="status" className="mb-5 rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-300">{message}</div>}
        {error && <div role="alert" className="mb-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">{error}</div>}

        <div className="grid gap-4 sm:grid-cols-3">
          <Stat icon={<BookOpen size={19}/>} label="My Courses" value={overview?.courses ?? courses.length}/>
          <Stat icon={<FileText size={19}/>} label="Assessments" value={overview?.assessments ?? 0}/>
          <Stat icon={<Upload size={19}/>} label="Learning Materials" value={overview?.course_pdfs ?? 0}/>
        </div>

        <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div><p className="text-sm text-violet-300">Teaching workspace</p><h2 className="mt-1 text-2xl font-semibold">Courses and learning materials</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-white/40">Upload multiple formats in one flow. Processing and indexing continue after the upload returns.</p></div>
          <div className="flex flex-wrap gap-3">
            <button onClick={() => {setShowUpload(true);setError("");setMessage("")}} disabled={!courses.length} className="lms-btn-secondary rounded-xl px-4 py-3 text-sm disabled:opacity-40"><Upload size={16}/>Upload materials</button>
            <button onClick={() => {setShowCourse(true);setError("");setMessage("")}} className="lms-btn-primary rounded-xl px-4 py-3 text-sm"><Plus size={16}/>Create course</button>
          </div>
        </div>

        <div className="mt-7 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {courses.map(course => <CourseCard key={course.id} course={course} onUpload={() => {setCourseId(String(course.id));setShowUpload(true)}}/> )}
          {!courses.length && <div className="lms-empty rounded-2xl p-8 md:col-span-2 xl:col-span-3"><p className="font-medium">No courses yet</p><p className="mt-2 text-sm text-white/40">Create a course before uploading learning materials.</p><button onClick={()=>setShowCourse(true)} className="lms-btn-primary mt-5 rounded-xl px-4 py-3 text-sm">Create your first course</button></div>}
        </div>

        {showCourse && <Modal title="Create Course" onClose={()=>setShowCourse(false)}>
          <form onSubmit={createCourse} className="space-y-5">
            <Field label="Course title"><input value={title} onChange={e=>setTitle(e.target.value)} required className="lms-input" /></Field>
            <Field label="Description"><textarea value={description} onChange={e=>setDescription(e.target.value)} required rows={5} className="lms-input resize-y"/></Field>
            <button disabled={busy} className="lms-btn-primary w-full rounded-xl py-3 text-sm disabled:opacity-50">{busy?"Creating...":"Create course"}</button>
          </form>
        </Modal>}

        {showUpload && <Modal title="Upload learning materials" onClose={()=>{if(!busy)setShowUpload(false)}}>
          <div className="space-y-5">
            <Field label="Course">
              <select value={courseId} onChange={e=>setCourseId(e.target.value)} className="lms-input">
                {courses.map(course=><option key={course.id} value={course.id}>{course.title}</option>)}
              </select>
            </Field>
            <label className="block cursor-pointer rounded-2xl border border-dashed border-white/15 bg-white/[.025] p-7 text-center hover:border-violet-400/30">
              <input type="file" multiple accept={ACCEPT} className="sr-only" onChange={e=>addFiles(e.target.files)} />
              <Upload className="mx-auto text-violet-300" size={28}/>
              <p className="mt-3 text-sm font-medium">Choose multiple files</p>
              <p className="mt-1 text-xs text-white/35">PDF, DOCX, DOC, PPTX, PPT, TXT, MD, PNG, JPG, JPEG, WEBP, CSV, XLSX · max {MAX_FILES} files · {10} MB/file</p>
            </label>
            <div className="rounded-xl border border-white/10 bg-white/[.02] p-3 text-xs text-white/45">Selected course: <span className="text-white/75">{selectedCourse?.title || "None"}</span></div>
            {files.length > 0 && <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-white/40"><span>{files.length} selected</span><span>{overall}% overall upload progress</span></div>
              <div className="h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400" style={{width:overall+"%"}}/></div>
              <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                {files.map(file => <div key={file.name} className="rounded-xl border border-white/10 bg-white/[.025] p-3">
                  <div className="flex items-start gap-3"><GripVertical size={15} className="mt-1 text-white/20"/><FileIcon name={file.name}/><div className="min-w-0 flex-1"><p className="truncate text-sm">{file.name}</p><p className="mt-1 text-[11px] text-white/30">{formatBytes(file.size)} · {statuses[file.name] || "READY"}</p></div>{!busy && <button onClick={()=>removeFile(file.name)} className="text-white/30 hover:text-white" aria-label={"Remove "+file.name}><X size={15}/></button>}</div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"><div className={"h-full " + (statuses[file.name]==="FAILED" || statuses[file.name]==="TIMEOUT" ? "bg-red-400" : "bg-violet-400")} style={{width:(progress[file.name]||0)+"%"}}/></div>
                  {errors[file.name] && <p className="mt-2 text-xs text-red-300">{errors[file.name]}</p>}
                </div>)}
              </div>
            </div>}
            <button disabled={busy || !files.length || !courseId} onClick={uploadAll} className="lms-btn-primary w-full rounded-xl py-3 text-sm disabled:opacity-40">{busy ? <><Loader2 size={16} className="animate-spin"/>Processing uploads...</> : <><Upload size={16}/>Upload all</>}</button>
          </div>
        </Modal>}
      </div>
    </section>
  </AppLayout>
}

function CourseCard({course,onUpload}:{course:Course;onUpload:()=>void}) {
  return <div className="lms-card rounded-2xl p-6"><div className="lms-icon flex h-11 w-11 items-center justify-center rounded-xl"><BookOpen size={20}/></div><h3 className="mt-5 text-lg font-medium">{course.title}</h3><p className="mt-2 line-clamp-3 text-sm leading-6 text-white/40">{course.description}</p><button onClick={onUpload} className="lms-btn-secondary mt-5 rounded-xl px-4 py-2.5 text-sm"><Upload size={15}/>Add materials</button></div>
}
function Stat({icon,label,value}:{icon:React.ReactNode;label:string;value:number}) { return <div className="lms-stat rounded-2xl p-5"><div className="lms-icon mb-4 flex h-10 w-10 items-center justify-center rounded-xl">{icon}</div><p className="text-sm text-white/40">{label}</p><p className="mt-1 text-2xl font-semibold">{value}</p></div> }
function Field({label,children}:{label:string;children:React.ReactNode}) { return <label className="block"><span className="mb-2 block text-sm text-white/60">{label}</span>{children}</label> }
function Modal({title,onClose,children}:{title:string;onClose:()=>void;children:React.ReactNode}) { return <div className="lms-modal fixed inset-0 z-50 flex justify-center p-4" role="dialog" aria-modal="true" aria-label={title}><div className="lms-modal-panel lms-card rounded-2xl p-5 sm:p-7"><div className="mb-6 flex items-center justify-between gap-4"><h2 className="text-lg font-semibold">{title}</h2><button onClick={onClose} className="lms-btn-secondary h-9 w-9 rounded-lg" aria-label="Close dialog"><X size={17}/></button></div>{children}</div></div> }
function FileIcon({name}:{name:string}) { const ext=name.split(".").pop()?.toLowerCase(); if(["png","jpg","jpeg","webp"].includes(ext||"")) return <Image size={17} className="mt-0.5 shrink-0 text-cyan-300"/>; if(["ppt","pptx"].includes(ext||"")) return <Presentation size={17} className="mt-0.5 shrink-0 text-orange-300"/>; if(["csv","xlsx"].includes(ext||"")) return <Table2 size={17} className="mt-0.5 shrink-0 text-emerald-300"/>; if(["pdf","doc","docx","txt","md"].includes(ext||"")) return <FileText size={17} className="mt-0.5 shrink-0 text-violet-300"/>; return <File size={17} className="mt-0.5 shrink-0"/> }
function formatBytes(value:number) { if(value < 1024) return value+" B"; if(value < 1024*1024) return (value/1024).toFixed(1)+" KB"; return (value/1024/1024).toFixed(1)+" MB" }
