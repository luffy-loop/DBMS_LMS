import fs from "node:fs"
import path from "node:path"

const root = process.cwd()
const read = (file) => fs.readFileSync(path.join(root, file), "utf8")

const config = read("src/config.ts")
const layout = read("src/components/AppLayout.tsx")
const copilot = read("src/pages/StudyCopilot.tsx")
const api = read("src/api.ts")
const login = read("src/pages/Login.tsx")
const routes = read("src/main.tsx")
const assignments = read("src/pages/Assignments.tsx")
const admin = read("src/pages/Admin.tsx")

const checks = [
  [config.includes("https://dbms-lms-hwvp.onrender.com"), "production API URL"],
  [layout.includes("Logout"), "logout option"],
  [layout.includes("Open account menu"), "account menu"],
  [copilot.includes("Ask anything. Clear your doubts."), "general AI heading"],
  [copilot.includes("No course context"), "optional course context"],
  [copilot.includes('course_id:courseId?Number(courseId):null'), "optional course request"],
  [api.includes("sessionStorage.getItem") && !api.includes("localStorage"), "per-tab API token storage"],
  [login.includes("sessionStorage.setItem") && !login.includes("localStorage"), "per-tab login storage"],
  [routes.includes('"/auth/session"') && routes.includes('roles={["admin"]}'), "server-synced role-aware routes"],
  [layout.includes("User Management") && layout.includes("System Health") && layout.includes("Audit Logs"), "admin navigation"],
  [admin.includes('"/admin/users"') && admin.includes('method:"PATCH"') && admin.includes('method:"POST"'), "admin user management"],
  [assignments.includes("Upload answer PDF") && assignments.includes('form.append("answers_json"'), "text and PDF assignment submission"],
]

const failed = checks.filter(([ok]) => !ok)
if (failed.length) {
  console.error("Frontend product contract failed:")
  for (const [, label] of failed) console.error(" - " + label)
  process.exit(1)
}
console.log("Frontend product contract passed.")
