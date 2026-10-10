import {useEffect,useState} from "react"
import {Award,RefreshCw,FileDown,Eye,CheckCircle2,AlertTriangle,Clock,Save,Send,X} from "lucide-react"
import {useNavigate} from "react-router-dom"
import AppLayout from "../components/AppLayout"
import {apiJson,apiFetch} from "../api"

type Assignment={id:number;title:string;type:string;course_id:number}
type Submission={id:number;assignment_id:number;assignment_title?:string;student_id:number;student_name?:string;marks:number|null;marks_published?:boolean;marks_status?:string;review_status?:string;teacher_review_note?:string|null;max_marks?:number;answer?:string;file_id?:string|null;file_name?:string|null;submitted_at?:string|null;percentage?:number|null}
type ReportQuestion={question_id:number;question:string;reference_answer?:string|null;max_marks:number;student_answer?:string|null;awarded_marks?:number|null;feedback?:string|null;matched_concepts:string[];missing_concepts:string[];review_status:string;evaluation_status?:string|null}
type ReportStudent={student_id:number;student_name:string;student_email:string;section?:string;submission_id:number|null;answer:string|null;file_id:string|null;file_name:string|null;submission_status:string;submitted_at:string|null;grading_status:string;review_status:string;marks_status:string;saved_marks:number|null;suggested_marks:number|null;total_marks:number|null;max_marks:number;percentage:number|null;needs_review:boolean;questions:ReportQuestion[]}
type Report={assignment:{id:number;title:string;course_id:number};enrolled_students:number;submitted_students:number;not_submitted_students:number;awaiting_grading:number;ai_evaluated:number;needs_review:number;teacher_reviewed:number;published:number;evaluation_failures:number;low_score_threshold_percent:number;students:ReportStudent[]}
type AdminRow=ReportStudent&{course_id:number;course_title:string;assessment_id:number;assessment_title:string}
type AdminOverview={courses:Array<{id:number;title:string}>;sections:string[];available_assessments:Assignment[];assessments:Array<{assessment_id:number;assessment_title:string;course_id:number;course_title:string;enrolled_students:number;submitted_students:number;not_submitted_students:number;awaiting_grading:number;ai_evaluated:number;needs_review:number;teacher_reviewed:number;published:number;evaluation_failures:number}>;students:AdminRow[];counts:Record<string,number>}
type EvaluationQuestion={question_id:number;question_text:string;question_type:string;max_marks:number;awarded_marks:number;teacher_override_marks:number|null;teacher_review_note:string|null;review_status:string;evaluator_confidence:number|null;student_answer:string|null;reference_answer:string|null;evaluation_status:string;rubric_evaluation?:{feedback?:string;summary?:string;matched_concepts?:string[];missing_concepts?:string[];criteria?:Array<{criterion_text:string;max_marks:number;awarded_marks:number;covered:boolean}>}|null}
type Evaluation={submission_id:number;assignment_id:number;student_id:number;total_marks:number|null;max_marks:number;marks_published?:boolean;submission_answer?:string;teacher_review_note?:string|null;questions:EvaluationQuestion[]}
const filters=[["all","All students"],["awaiting_grading","Awaiting grading"],["ai_evaluated","AI evaluated"],["needs_review","Needs review"],["teacher_reviewed","Teacher reviewed"],["awaiting_publication","Awaiting publication"],["published","Published"],["not_submitted","Not submitted"]]
export default function Marks(){
 const navigate=useNavigate()
 const role=sessionStorage.getItem("role")||"student"
 const [items,setItems]=useState<Submission[]>([])
 const [adminOverview,setAdminOverview]=useState<AdminOverview|null>(null)
 const [adminCourse,setAdminCourse]=useState("")
 const [adminSection,setAdminSection]=useState("")
 const [adminAssessment,setAdminAssessment]=useState("")
 const [adminStatus,setAdminStatus]=useState("")
 const [adminRefresh,setAdminRefresh]=useState(0)
 const [assignments,setAssignments]=useState<Assignment[]>([])
 const [assignmentId,setAssignmentId]=useState("")
 const [sectionFilter,setSectionFilter]=useState("")
 const [report,setReport]=useState<Report|null>(null)
 const [filter,setFilter]=useState("all")
 const [search,setSearch]=useState("")
 const [error,setError]=useState("")
 const [message,setMessage]=useState("")
 const [loading,setLoading]=useState(false)
 const [saving,setSaving]=useState<number|null>(null)
 const [gradeValues,setGradeValues]=useState<Record<number,string>>({})
 const [evaluation,setEvaluation]=useState<Evaluation|null>(null)
 const [questionScores,setQuestionScores]=useState<Record<number,string>>({})
 const [questionNotes,setQuestionNotes]=useState<Record<number,string>>({})
 const [reviewSaving,setReviewSaving]=useState(false)
 const [publishing,setPublishing]=useState(false)
 const [correcting,setCorrecting]=useState<number|null>(null)

 async function load(){
  setLoading(true)
  try{
   if(role==="teacher"){
    const data=await apiJson<Assignment[]>("/my-assignments")
    setAssignments(data)
    const requested=new URLSearchParams(window.location.search).get("assignment_id");setAssignmentId(current=>current||(requested&&data.some(item=>String(item.id)===requested)?requested:String(data[0]?.id||"")))
   }else if(role==="admin"){
    return
   }else{
    setItems(await apiJson<Submission[]>("/my-marks"))
   }
   setError("")
  }catch(e){setError(e instanceof Error?e.message:"Unable to load marks")}
  finally{setLoading(false)}
 }
 useEffect(()=>{if(!sessionStorage.getItem("token")){navigate("/login");return}if(role!=="admin")load()},[navigate,role])
 useEffect(()=>{
  if(role!=="admin")return
  let active=true
  setLoading(true)
  const params=new URLSearchParams()
  if(adminCourse)params.set("course_id",adminCourse)
  if(adminSection)params.set("section",adminSection)
  if(adminAssessment)params.set("assignment_id",adminAssessment)
  if(adminStatus)params.set("status",adminStatus)
  apiJson<AdminOverview>("/admin/marks-overview?"+params.toString()).then(data=>{if(active){setAdminOverview(data);setError("")}}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Unable to load administrator marks overview")}).finally(()=>{if(active)setLoading(false)})
  return()=>{active=false}
 },[role,adminCourse,adminSection,adminAssessment,adminStatus,adminRefresh])
 useEffect(()=>{
  if(role!=="teacher"||!assignmentId)return
  let active=true
  setLoading(true)
  const params=new URLSearchParams()
  if(sectionFilter)params.set("section",sectionFilter)
  apiJson<Report>("/teacher/assignments/"+assignmentId+"/report"+(params.toString()?"?"+params.toString():"")).then(data=>{if(active){setReport(data);setError("")}}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Unable to load class report")}).finally(()=>{if(active)setLoading(false)})
  return()=>{active=false}
 },[role,assignmentId,sectionFilter])

 async function download(id:number,fileName?:string){
  try{
   const r=await apiFetch("/submissions/"+id+"/download",{},30000)
   if(!r.ok)throw new Error("Unable to download submission")
   const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement("a")
   a.href=url;a.download=fileName||items.find(x=>x.id===id)?.file_name||"submission.pdf";a.click();URL.revokeObjectURL(url)
  }catch(e){setError(e instanceof Error?e.message:"Unable to download submission")}
 }
 async function downloadCsv(){
  if(!assignmentId)return
  try{
   const params=new URLSearchParams({response_format:"csv"})
   if(sectionFilter)params.set("section",sectionFilter)
   const r=await apiFetch("/teacher/assignments/"+assignmentId+"/report?"+params.toString(),{},30000)
   if(!r.ok)throw new Error("Unable to export the assessment report")
   const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement("a")
   a.href=url;a.download="assessment-"+assignmentId+(sectionFilter?"-section-"+sectionFilter:"")+"-marks.csv";a.click();URL.revokeObjectURL(url)
  }catch(e){setError(e instanceof Error?e.message:"Unable to export report")}
 }
 async function correctWithAI(id:number){
  if(correcting===id)return
  setCorrecting(id);setError("");setMessage("AI correction is running. This can take longer on a cold backend; the original submission and published marks are preserved.")
  try{
   const result=await apiJson<{suggested_marks:number|null;max_marks:number;review_required:boolean;evaluation_failures:number;message:string}>("/submissions/"+id+"/correct-with-ai",{method:"POST"},120000)
   await openEvaluation(id)
   setMessage(result.suggested_marks===null
    ? result.message+" No reliable score was produced; inspect the evaluation details and review manually."
    : result.message+" Suggested marks: "+result.suggested_marks+"/"+result.max_marks+"."+(result.review_required?" Teacher review is required.":""))
   void refreshReport().catch(()=>{})
  }catch(e){
   const reason=e instanceof Error?e.message:"AI correction failed"
   try{await openEvaluation(id)}catch{}
   setError(reason+" The original submission is preserved. Open answer & review for the recorded failure reason, then retry or grade manually.")
   setMessage("")
  }finally{setCorrecting(null)}
 }
 async function openEvaluation(id:number){
  setError("");setMessage("")
  try{
   const data=await apiJson<Evaluation>("/submissions/"+id+"/evaluation")
   setEvaluation(data)
   setQuestionScores(Object.fromEntries(data.questions.map(q=>[q.question_id,String(q.teacher_override_marks??(q.evaluation_status==="evaluation_failed"||q.evaluation_status==="pending"?"":q.awarded_marks??""))])))
   setQuestionNotes(Object.fromEntries(data.questions.map(q=>[q.question_id,q.teacher_review_note||""])))
  }catch(e){setError(e instanceof Error?e.message:"Unable to load evaluation")}
 }
 async function saveManualGrade(id:number,maximum:number){
  const raw=gradeValues[id]
  if(raw===undefined||raw.trim()===""){setError("Enter the final marks before saving.");return}
  const value=Number(raw)
  if(!Number.isFinite(value)||value<0||value>maximum){setError("Marks must be between 0 and "+maximum+".");return}
  setSaving(id);setError("");setMessage("")
  try{
   await apiJson("/submissions/"+id+"/marks?marks="+encodeURIComponent(String(value)),{method:"PUT"})
   setMessage("Marks saved privately. Publish the result when review is complete.")
   await refreshReport()
  }catch(e){setError(e instanceof Error?e.message:"Unable to save marks")}
  finally{setSaving(null)}
 }
 async function saveReview(){
  if(!evaluation)return
  setReviewSaving(true);setError("");setMessage("")
  try{
   const reviews=evaluation.questions.map(q=>{
    const raw=questionScores[q.question_id]
    const item:{question_id:number;override_marks?:number;review_note:string}={question_id:q.question_id,review_note:questionNotes[q.question_id]||""}
    if(raw!==undefined&&raw.trim()!==""){
     const score=Number(raw)
     if(!Number.isFinite(score)||score<0||score>q.max_marks)throw new Error("Marks for question "+q.question_id+" must be between 0 and "+q.max_marks+".")
     item.override_marks=score
    }
    return item
   })
   await apiJson("/submissions/"+evaluation.submission_id+"/review",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reviews})})
   setMessage("Teacher review saved. Publish the result when ready.")
   await refreshReport()
   await openEvaluation(evaluation.submission_id)
  }catch(e){setError(e instanceof Error?e.message:"Unable to save teacher review")}
  finally{setReviewSaving(false)}
 }
 async function publish(id:number){
  setPublishing(true);setError("");setMessage("")
  try{
   await apiJson("/submissions/"+id+"/publish",{method:"POST"})
   setMessage("Marks published successfully.")
   await refreshReport()
   if(evaluation?.submission_id===id)await openEvaluation(id)
   else await load()
  }catch(e){setError(e instanceof Error?e.message:"Unable to publish marks")}
  finally{setPublishing(false)}
 }
 async function refreshReport(){
  if(role==="teacher"&&assignmentId){
   const params=new URLSearchParams()
   if(sectionFilter)params.set("section",sectionFilter)
   const data=await apiJson<Report>("/teacher/assignments/"+assignmentId+"/report"+(params.toString()?"?"+params.toString():""))
   setReport(data)
  }else await load()
 }
 const filtered=report?.students.filter(student=>{
  const status=student.review_status||student.grading_status
  return (filter==="all"||status===filter)&&((student.student_name+" "+student.student_email+" "+student.student_id).toLowerCase().includes(search.toLowerCase()))
 })||[]

 return <AppLayout title={role==="teacher"?"Assessment grading":role==="admin"?"Administrator marks overview":"Marks"} subtitle="Academic performance and review">
  <section className="lms-grid min-h-[calc(100vh-76px)] p-4 sm:p-6 lg:p-10"><div className="mx-auto max-w-7xl">
   {error&&<div role="alert" className="mb-5 rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">{error}</div>}
   {message&&<div role="status" className="mb-5 rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-300">{message}</div>}
   <div className="flex flex-wrap items-center justify-between gap-4"><div><h2 className="text-xl font-semibold">{role==="teacher"?"Class-wide grading":role==="admin"?"Section-wise marks overview":"My results"}</h2><p className="mt-1 text-sm text-white/40">{loading?"Loading assessment data…":role==="teacher"?"Review every enrolled student, including students who have not submitted.":role==="admin"?(adminOverview?.students.length||0)+" matching student records":items.length+" record"+(items.length===1?"":"s")}</p></div><button onClick={()=>role==="teacher"?refreshReport():role==="admin"?setAdminRefresh(current=>current+1):load()} className="lms-btn-secondary rounded-xl px-3 py-2 text-sm"><RefreshCw size={15}/>Refresh</button></div>

   {role==="admin"?<>
    <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
     {[["Enrolled",adminOverview?.counts.enrolled],["Submitted",adminOverview?.counts.submitted],["Not submitted",adminOverview?.counts.not_submitted],["Awaiting grading",adminOverview?.counts.awaiting_grading],["AI evaluated",adminOverview?.counts.ai_evaluated],["Needs review",adminOverview?.counts.needs_review],["Teacher reviewed",adminOverview?.counts.teacher_reviewed],["Published",adminOverview?.counts.published],["Evaluation failures",adminOverview?.counts.evaluation_failures]].map(([label,value])=><div key={label} className="lms-card rounded-xl p-4"><p className="text-xs text-white/45">{label}</p><p className="mt-1 text-2xl font-semibold">{value??0}</p></div>)}
    </div>
    <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
     <label><span className="mb-2 block text-sm text-white/60">Course</span><select value={adminCourse} onChange={e=>{setAdminCourse(e.target.value);setAdminAssessment("")}} className="lms-input"><option value="">All courses</option>{(adminOverview?.courses||[]).map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
     <label><span className="mb-2 block text-sm text-white/60">Section</span><select value={adminSection} onChange={e=>setAdminSection(e.target.value)} className="lms-input"><option value="">All sections</option>{(adminOverview?.sections||[]).map(item=><option key={item} value={item}>{item}</option>)}</select></label>
     <label><span className="mb-2 block text-sm text-white/60">Assessment</span><select value={adminAssessment} onChange={e=>setAdminAssessment(e.target.value)} className="lms-input"><option value="">All assessments</option>{(adminOverview?.available_assessments||[]).filter(item=>!adminCourse||String(item.course_id)===adminCourse).map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
     <label><span className="mb-2 block text-sm text-white/60">Grading status</span><select value={adminStatus} onChange={e=>setAdminStatus(e.target.value)} className="lms-input"><option value="">All statuses</option>{filters.filter(([value])=>value!=="all").map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
    </div>
    <div className="mt-5 overflow-x-auto rounded-2xl border border-white/10"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-white/5 text-xs text-white/45"><tr>{["Course","Section","Assessment","Roll Number","Student","Submission","Marks","Max Marks","Grading Status"].map(h=><th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead><tbody>{(adminOverview?.students||[]).map(row=><tr key={row.assessment_id+"-"+row.student_id} className="border-t border-white/10"><td className="px-4 py-3">{row.course_title}</td><td className="px-4 py-3">{row.section}</td><td className="px-4 py-3">{row.assessment_title}</td><td className="px-4 py-3">{row.student_email}</td><td className="px-4 py-3">{row.student_name}</td><td className="px-4 py-3 capitalize">{row.submission_status.replaceAll("_"," ")}</td><td className="px-4 py-3">{row.saved_marks===null?"Not graded":row.saved_marks}</td><td className="px-4 py-3">{row.max_marks}</td><td className="px-4 py-3"><Status value={row.grading_status}/></td></tr>)}</tbody></table>{!adminOverview?.students.length&&<div className="p-8 text-center text-sm text-white/40">No students match these filters.</div>}</div>
   </>:null}
   {role==="teacher"?<>
    <div className="mt-6 flex flex-wrap items-end gap-3"><label className="min-w-[260px] flex-1"><span className="mb-2 block text-sm text-white/60">Assessment</span><select value={assignmentId} onChange={e=>{setAssignmentId(e.target.value);setSectionFilter("");setFilter("all");setEvaluation(null)}} className="lms-input">{assignments.map(a=><option key={a.id} value={a.id}>{a.title}</option>)}</select></label><label className="min-w-[180px]"><span className="mb-2 block text-sm text-white/60">Section</span><select value={sectionFilter} onChange={e=>{setSectionFilter(e.target.value);setFilter("all")}} className="lms-input"><option value="">All sections</option>{Array.from(new Set((report?.students||[]).map(student=>student.section||"Unassigned"))).map(section=><option key={section} value={section}>{section}</option>)}</select></label><button onClick={downloadCsv} disabled={!assignmentId} className="lms-btn-secondary rounded-xl px-4 py-3 text-sm disabled:opacity-40"><FileDown size={16}/>Export CSV</button></div>
    {report&&<><div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[
      ["Enrolled",report.enrolled_students],["Submitted",report.submitted_students],["Not submitted",report.not_submitted_students],["Awaiting grading",report.awaiting_grading],["AI evaluated",report.ai_evaluated],["Needs review",report.needs_review],["Teacher reviewed",report.teacher_reviewed],["Published",report.published],["Evaluation failures",report.evaluation_failures]
     ].map(([label,value])=><div key={label} className="lms-card rounded-xl p-4"><p className="text-xs text-white/45">{label}</p><p className="mt-1 text-2xl font-semibold">{value}</p></div>)}</div>
     <div className="mt-6 flex flex-wrap gap-2">{filters.map(([value,label])=><button key={value} onClick={()=>setFilter(value)} className={"rounded-full border px-3 py-2 text-xs "+(filter===value?"border-violet-300/40 bg-violet-300/10 text-violet-100":"border-white/10 text-white/55 hover:bg-white/5")}>{label}</button>)}</div>
     <input aria-label="Search students" value={search} onChange={e=>setSearch(e.target.value)} className="lms-input mt-3" placeholder="Search student name, roll number, or ID"/>
     <div className="mt-4 space-y-3">{filtered.map(student=><article key={student.student_id} className="lms-card rounded-2xl p-4 sm:p-5"><div className="flex flex-wrap items-start gap-3"><div className="lms-icon flex h-10 w-10 items-center justify-center rounded-xl"><Award size={18}/></div><div className="min-w-0 flex-1"><p className="font-medium">{student.student_name} <span className="text-xs text-white/40">#{student.student_id}</span></p><p className="mt-1 text-xs text-white/40">{student.student_email}{student.section?" · Section "+student.section:""}</p>{student.submitted_at&&<p className="mt-1 text-xs text-white/35">Submitted {new Date(student.submitted_at).toLocaleString()}</p>}<div className="mt-2 flex flex-wrap gap-2"><Status value={student.review_status}/>{student.needs_review&&<span className="inline-flex items-center gap-1 rounded-full bg-amber-400/10 px-2 py-1 text-xs text-amber-200"><AlertTriangle size={12}/>Below {report.low_score_threshold_percent}% or flagged</span>}</div></div><div className="min-w-[150px] text-right">{student.review_status==="published"?<><p className="text-lg font-semibold">{student.total_marks}/{student.max_marks}</p><p className="text-xs text-emerald-200">{student.percentage}% published</p></>:student.saved_marks!==null?<><p className="text-lg font-semibold">{student.saved_marks}/{student.max_marks}</p><p className="text-xs text-white/45">Saved, unpublished</p></>:student.questions.length>0&&student.questions.every(q=>q.evaluation_status==="evaluation_failed"||q.evaluation_status==="pending")?<><p className="text-sm font-semibold text-amber-200">No score generated</p><p className="text-xs text-white/45">Evaluation failed · manual review</p></>:student.suggested_marks!==null?<><p className="text-lg font-semibold">{student.suggested_marks}/{student.max_marks}</p><p className="text-xs text-white/45">AI suggestion</p></>:<p className="text-sm text-white/40">No marks yet</p>}</div></div>
       {student.submission_id&&<div className="mt-4 flex flex-wrap items-end gap-2 border-t border-white/10 pt-4">{student.answer&&<p className="w-full whitespace-pre-wrap text-sm text-white/60">{student.answer}</p>}{student.file_id&&<button onClick={()=>download(student.submission_id!,student.file_name||undefined)} className="lms-btn-secondary rounded-xl px-3 py-2 text-sm"><FileDown size={15}/>Download {student.file_name||"PDF"}</button>}<button onClick={()=>correctWithAI(student.submission_id!)} disabled={correcting===student.submission_id} className="lms-btn-primary rounded-xl px-3 py-2 text-sm disabled:opacity-40">{correcting===student.submission_id?"Correcting...":"Correct with AI"}</button>{student.questions.length>0?<button onClick={()=>openEvaluation(student.submission_id!)} className="lms-btn-secondary rounded-xl px-3 py-2 text-sm"><Eye size={15}/>Open answer & review</button>:<><label className="w-32"><span className="mb-1 block text-xs text-white/45">Final marks / {student.max_marks}</span><input type="number" min="0" max={student.max_marks} step="0.01" value={gradeValues[student.submission_id]??(student.saved_marks===null?"":String(student.saved_marks))} onChange={e=>setGradeValues(v=>({...v,[student.submission_id!]:e.target.value}))} className="lms-input"/></label><button onClick={()=>saveManualGrade(student.submission_id!,student.max_marks)} disabled={saving===student.submission_id} className="lms-btn-secondary rounded-xl px-3 py-2 text-sm"><Save size={15}/>{saving===student.submission_id?"Saving...":"Save marks"}</button></>}{student.saved_marks!==null&&<button onClick={()=>publish(student.submission_id!)} disabled={publishing||student.review_status==="needs_review"} className="lms-btn-primary rounded-xl px-3 py-2 text-sm disabled:opacity-40"><Send size={15}/>{publishing?"Publishing":"Publish marks"}</button>}</div>}
     </article>)}{!filtered.length&&<div className="lms-empty rounded-2xl p-8 text-center text-sm text-white/40">No students match this filter.</div>}</div>
    </>}
   </>:<div className="mt-6 space-y-3">{items.map(item=><article key={item.id} className="lms-card rounded-2xl p-5"><div className="flex flex-wrap items-start gap-4"><div className="lms-icon flex h-10 w-10 items-center justify-center rounded-xl"><Award size={18}/></div><div className="min-w-0 flex-1"><p className="font-medium">{item.assignment_title||"Assessment #"+item.assignment_id}</p>{role==="admin"&&<p className="mt-1 text-xs text-white/40">{item.student_name||"Student #"+item.student_id}</p>}{item.submitted_at&&<p className="mt-1 text-xs text-white/35">Submitted {new Date(item.submitted_at).toLocaleString()}</p>}<p className="mt-2 text-sm text-white/60">{item.marks_published?"Published":item.marks_status==="awaiting_publication"?"Teacher review is complete; final marks are not published yet.":"Submitted — awaiting grading or teacher review."}</p>{item.marks_published&&item.teacher_review_note&&<p className="mt-2 text-sm text-white/55">{item.teacher_review_note}</p>}{item.file_id&&<button onClick={()=>download(item.id)} className="lms-btn-secondary mt-3 rounded-lg px-3 py-2 text-xs">Download {item.file_name||"PDF submission"}</button>}</div><div className="text-right">{item.marks_published&&item.marks!==null?<><p className="text-lg font-semibold">{item.marks}{item.max_marks?"/"+item.max_marks:""}</p>{item.percentage!==undefined&&item.percentage!==null&&<p className="text-xs text-white/40">{item.percentage}%</p>}</>:<span className="text-sm text-white/40">{item.marks_status==="awaiting_publication"?"Awaiting publication":"Pending"}</span>}</div></div></article>)}{!items.length&&<div className="lms-empty rounded-2xl p-10 text-center text-sm text-white/40">No academic records yet.</div>}</div>}

   {evaluation&&role==="teacher"&&<div className="lms-modal fixed inset-0 z-50 flex justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="evaluation-title"><div className="lms-modal-panel lms-card rounded-3xl p-5 sm:p-7"><div className="flex items-start justify-between gap-4"><div><p className="text-xs text-violet-300">Submission #{evaluation.submission_id}</p><h3 id="evaluation-title" className="mt-1 text-xl font-semibold">Answer and grading review</h3><p className="mt-1 text-sm text-white/45">Marks remain private until you publish.</p></div><button onClick={()=>setEvaluation(null)} className="lms-btn-secondary h-9 w-9 rounded-lg" aria-label="Close review"><X size={17}/></button></div>
    {evaluation.submission_answer&&<div className="mt-5 rounded-xl border border-white/10 p-4"><p className="text-xs text-white/45">Original submission</p><p className="mt-2 whitespace-pre-wrap text-sm">{evaluation.submission_answer}</p></div>}
    <div className="mt-4 rounded-xl border border-violet-300/20 bg-violet-300/[.04] p-4">
     <p className="text-xs text-violet-200">AI scoring summary</p>
     <p className="mt-1 text-lg font-semibold">{evaluation.questions.some(q=>q.evaluation_status==="evaluated"||q.evaluation_status==="evaluated_with_review"||q.evaluation_status==="correct"||q.evaluation_status==="incorrect")?evaluation.questions.filter(q=>q.evaluation_status!=="evaluation_failed"&&q.evaluation_status!=="pending").reduce((sum,q)=>sum+(q.teacher_override_marks??q.awarded_marks??0),0).toFixed(2)+" / "+evaluation.questions.filter(q=>q.evaluation_status!=="evaluation_failed"&&q.evaluation_status!=="pending").reduce((sum,q)=>sum+q.max_marks,0):"No reliable score generated"}</p>
     <p className="mt-1 text-xs text-white/50">{evaluation.questions.filter(q=>q.evaluation_status==="evaluation_failed"||q.evaluation_status==="pending").length} question(s) need re-evaluation or manual review. Failed evaluations are not shown as zero marks.</p>
    </div>
    <div className="mt-4 space-y-4">{evaluation.questions.map(q=><div key={q.question_id} className="rounded-2xl border border-white/10 p-4"><div className="flex flex-wrap justify-between gap-2"><p className="font-medium">{q.question_text}</p><span className="text-xs text-white/45">Max {q.max_marks}</span></div><p className="mt-3 text-xs text-white/45">Student answer</p><p className="mt-1 whitespace-pre-wrap text-sm text-white/80">{q.student_answer||"No text answer"}</p><p className="mt-3 text-xs text-white/45">Reference answer</p><p className="mt-1 whitespace-pre-wrap text-sm text-white/65">{q.reference_answer||"No reference answer configured"}</p>{q.rubric_evaluation&&<><p className="mt-3 text-xs text-white/45">AI explanation</p><p className="mt-1 text-sm text-white/65">{q.rubric_evaluation.feedback||q.rubric_evaluation.summary||"No explanation was recorded."}</p><div className="mt-2 flex flex-wrap gap-1">{(q.rubric_evaluation.matched_concepts||[]).map(term=><span key={term} className="rounded-full bg-emerald-400/10 px-2 py-1 text-xs text-emerald-200">Matched: {term}</span>)}{(q.rubric_evaluation.missing_concepts||[]).map(term=><span key={term} className="rounded-full bg-amber-400/10 px-2 py-1 text-xs text-amber-200">Missing: {term}</span>)}</div></>}<div className="mt-4 grid gap-3 sm:grid-cols-2"><label><span className="mb-1 block text-xs text-white/45">Teacher-confirmed marks</span><input type="number" min="0" max={q.max_marks} step="0.01" value={questionScores[q.question_id]??""} onChange={e=>setQuestionScores(v=>({...v,[q.question_id]:e.target.value}))} className="lms-input"/></label><label><span className="mb-1 block text-xs text-white/45">Teacher note</span><input value={questionNotes[q.question_id]??""} onChange={e=>setQuestionNotes(v=>({...v,[q.question_id]:e.target.value}))} className="lms-input" placeholder="Optional feedback or support note"/></label></div><p className="mt-2 text-xs text-white/40">Evaluation status: {q.evaluation_status} · Review status: {q.review_status}</p></div>)}</div>
    <div className="mt-5 flex flex-wrap justify-end gap-2"><button onClick={()=>setEvaluation(null)} className="lms-btn-secondary rounded-xl px-4 py-2 text-sm">Close</button><button onClick={saveReview} disabled={reviewSaving} className="lms-btn-secondary rounded-xl px-4 py-2 text-sm"><Save size={15}/>{reviewSaving?"Saving review...":"Save teacher review"}</button>{evaluation.total_marks!==null&&<button onClick={()=>publish(evaluation.submission_id)} disabled={publishing||evaluation.questions.some(q=>q.review_status!=="reviewed"&&q.review_status!=="published")} className="lms-btn-primary rounded-xl px-4 py-2 text-sm disabled:opacity-40"><Send size={15}/>{publishing?"Publishing...":"Publish marks"}</button>}</div>
   </div></div>}
  </div></section>
 </AppLayout>
}
function Status({value}:{value:string}){
 const label=value.replaceAll("_"," ")
 const icon=value==="needs_review"?<AlertTriangle size={12}/>:value==="published"?<CheckCircle2 size={12}/>:value==="not_submitted"?<Clock size={12}/>:null
 const style=value==="needs_review"?"bg-amber-400/10 text-amber-200":value==="published"?"bg-emerald-400/10 text-emerald-200":value==="not_submitted"?"bg-white/5 text-white/45":"bg-sky-400/10 text-sky-200"
 return <span className={"inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs capitalize "+style}>{icon}{label}</span>
}
