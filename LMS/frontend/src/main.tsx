import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Routes, Route } from "react-router-dom"

import App from "./App"
import Login from "./pages/Login"
import Register from "./pages/Register"
import Dashboard from "./pages/Dashboard"
import "./index.css"
import Courses from "./pages/Courses"
import TeacherDashboard from "./pages/TeacherDashboard"
import Assignments from "./pages/Assignments"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/courses" element={<Courses />} />
        <Route path="/teacher" element={<TeacherDashboard />} />
        <Route path="/assignments" element={<Assignments />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>
)