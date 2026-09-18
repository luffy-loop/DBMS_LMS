import { BookOpen, ClipboardList, LayoutDashboard, Sparkles, UserRound } from "lucide-react"
import { useNavigate } from "react-router-dom"

export default function MobileNav({role="student",active}:{role?:string;active:string}){
 const navigate=useNavigate()
 const dashboard=role==="teacher"?"/teacher":role==="admin"?"/admin":"/dashboard"
 const items=[
  {id:"dashboard",label:"Home",path:dashboard,icon:LayoutDashboard},
  {id:"courses",label:"Courses",path:"/courses",icon:BookOpen},
  {id:"assignments",label:"Tasks",path:"/assignments",icon:ClipboardList},
  {id:"ai",label:"AI Hub",path:"/copilot",icon:Sparkles},
  {id:"profile",label:"Profile",path:"/profile",icon:UserRound}
 ]
 return <nav className="lms-mobile-nav lg:hidden">{items.map(({id,label,path,icon:Icon})=><button key={id} onClick={()=>navigate(path)} className={active===id?"active":""}><Icon size={19}/><span>{label}</span></button>)}</nav>
}
