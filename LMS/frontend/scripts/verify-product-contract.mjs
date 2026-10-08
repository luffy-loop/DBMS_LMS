import fs from "node:fs"
import path from "node:path"

const root = process.cwd()
const read = (file) => fs.readFileSync(path.join(root, file), "utf8")

const config = read("src/config.ts")
const layout = read("src/components/AppLayout.tsx")
const copilot = read("src/pages/StudyCopilot.tsx")

const checks = [
  [config.includes("https://dbms-lms-hwvp.onrender.com"), "production API URL"],
  [layout.includes("Logout"), "logout option"],
  [layout.includes("Open account menu"), "account menu"],
  [copilot.includes("Ask anything. Clear your doubts."), "general AI heading"],
  [copilot.includes("No course context"), "optional course context"],
  [copilot.includes('course_id:courseId?Number(courseId):null'), "optional course request"],
]

const failed = checks.filter(([ok]) => !ok)
if (failed.length) {
  console.error("Frontend product contract failed:")
  for (const [, label] of failed) console.error(" - " + label)
  process.exit(1)
}
console.log("Frontend product contract passed.")
