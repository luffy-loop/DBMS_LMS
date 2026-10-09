import {StrictMode,lazy,Suspense,useEffect,useState} from "react"
import {createRoot} from "react-dom/client"
import {BrowserRouter,Routes,Route,useLocation,useNavigate,Link} from "react-router-dom"
import {apiJson,clearSession} from "./api"
import App from "./App"
import "./index.css"
const Login=lazy(()=>import("./pages/Login"))
const Register=lazy(()=>import("./pages/Register"))
const Dashboard=lazy(()=>import("./pages/Dashboard"))
const Courses=lazy(()=>import("./pages/Courses"))
const TeacherDashboard=lazy(()=>import("./pages/TeacherDashboard"))
const Assignments=lazy(()=>import("./pages/Assignments"))
const Marks=lazy(()=>import("./pages/Marks"))
const Admin=lazy(()=>import("./pages/Admin"))
const AISearch=lazy(()=>import("./pages/AISearch"))
const StudyCopilot=lazy(()=>import("./pages/StudyCopilot"))
const QuizLab=lazy(()=>import("./pages/QuizLab"))
const TeacherInsights=lazy(()=>import("./pages/TeacherInsights"))
const LearningPath=lazy(()=>import("./pages/LearningPath"))
const Profile=lazy(()=>import("./pages/Profile"))
type Role="student"|"teacher"|"admin"
type Session={id:number;name:string;role:Role}
function RouteLoading(){return <div className="min-h-screen bg-[#070b14] flex items-center justify-center text-white/40 text-sm"><span>Loading...</span></div>}
function AccessDenied(){const role=sessionStorage.getItem("role");const home=role==="admin"?"/admin":role==="teacher"?"/teacher":"/dashboard";return <div className="min-h-screen bg-[#070b14] p-6 text-white flex items-center justify-center"><div className="max-w-md rounded-3xl border border-white/10 bg-white/[.03] p-8"><h1 className="text-xl font-semibold">Access denied</h1><p className="mt-3 text-sm text-white/50">Your current account does not have permission to open this page.</p><Link to={home} className="lms-btn-primary mt-6 inline-flex rounded-xl px-5 py-3 text-sm">Return to your workspace</Link></div></div>}
function Protected({children,roles}:{children:React.ReactNode;roles?:Role[]}){const location=useLocation(),navigate=useNavigate();const [session,setSession]=useState<Session|null>(null);const [failed,setFailed]=useState(false);useEffect(()=>{let active=true;if(!sessionStorage.getItem("token")){navigate("/login",{replace:true,state:{from:location.pathname}});return}apiJson<Session>("/auth/session",{},10000).then(s=>{if(!active)return;sessionStorage.setItem("role",s.role);sessionStorage.setItem("name",s.name);sessionStorage.setItem("userId",String(s.id));setSession(s)}).catch(()=>{if(!active)return;clearSession();setFailed(true);navigate("/login",{replace:true})});return()=>{active=false}},[location.pathname,navigate]);if(failed||!session)return <RouteLoading/>;if(roles&&!roles.includes(session.role))return <AccessDenied/>;return <>{children}</>}
function AppRoutes(){return <Suspense fallback={<RouteLoading/>}><Routes>
<Route path="/" element={<App/>}/><Route path="/login" element={<Login/>}/><Route path="/register" element={<Register/>}/>
<Route path="/dashboard" element={<Protected roles={["student"]}><Dashboard/></Protected>}/>
<Route path="/teacher" element={<Protected roles={["teacher"]}><TeacherDashboard/></Protected>}/>
<Route path="/admin" element={<Protected roles={["admin"]}><Admin/></Protected>}/>
<Route path="/admin/overview" element={<Protected roles={["admin"]}><Admin/></Protected>}/>
<Route path="/admin/users" element={<Protected roles={["admin"]}><Admin/></Protected>}/>
<Route path="/admin/system-health" element={<Protected roles={["admin"]}><Admin/></Protected>}/>
<Route path="/admin/audit-logs" element={<Protected roles={["admin"]}><Admin/></Protected>}/>
<Route path="/courses" element={<Protected><Courses/></Protected>}/>
<Route path="/assignments" element={<Protected><Assignments/></Protected>}/>
<Route path="/marks" element={<Protected><Marks/></Protected>}/>
<Route path="/search" element={<Protected><AISearch/></Protected>}/>
<Route path="/copilot" element={<Protected><StudyCopilot/></Protected>}/>
<Route path="/quiz" element={<Protected><QuizLab/></Protected>}/>
<Route path="/teacher/insights" element={<Protected roles={["teacher"]}><TeacherInsights/></Protected>}/>
<Route path="/learning-path" element={<Protected roles={["student"]}><LearningPath/></Protected>}/>
<Route path="/profile" element={<Protected><Profile/></Protected>}/>
<Route path="*" element={<AccessDenied/>}/>
</Routes></Suspense>}
createRoot(document.getElementById("root")!).render(<StrictMode><BrowserRouter><AppRoutes/></BrowserRouter></StrictMode>)
