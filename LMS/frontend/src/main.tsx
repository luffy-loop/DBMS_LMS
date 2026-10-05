import { StrictMode, lazy, Suspense } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Routes, Route } from "react-router-dom"

import App from "./App"
import "./index.css"

const Login = lazy(() => import("./pages/Login"))
const Register = lazy(() => import("./pages/Register"))
const Dashboard = lazy(() => import("./pages/Dashboard"))
const Courses = lazy(() => import("./pages/Courses"))
const TeacherDashboard = lazy(() => import("./pages/TeacherDashboard"))
const Assignments = lazy(() => import("./pages/Assignments"))
const Marks = lazy(() => import("./pages/Marks"))
const Admin = lazy(() => import("./pages/Admin"))
const AISearch = lazy(() => import("./pages/AISearch"))
const StudyCopilot = lazy(() => import("./pages/StudyCopilot"))
const QuizLab = lazy(() => import("./pages/QuizLab"))
const TeacherInsights = lazy(() => import("./pages/TeacherInsights"))
const LearningPath = lazy(() => import("./pages/LearningPath"))
const Profile = lazy(() => import("./pages/Profile"))

function RouteLoading() {
  return (
    <div className="min-h-screen bg-[#070b14] flex items-center justify-center text-white/40 text-sm">
      <div className="flex items-center gap-2">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white/80" />
        <span>Loading...</span>
      </div>
    </div>
  )
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/courses" element={<Courses />} />
          <Route path="/teacher" element={<TeacherDashboard />} />
          <Route path="/assignments" element={<Assignments />} />
          <Route path="/marks" element={<Marks />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/search" element={<AISearch />} />
          <Route path="/copilot" element={<StudyCopilot />} />
          <Route path="/quiz" element={<QuizLab />} />
          <Route path="/teacher/insights" element={<TeacherInsights />} />
          <Route path="/learning-path" element={<LearningPath />} />
          <Route path="/profile" element={<Profile />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  </StrictMode>
)