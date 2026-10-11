import AppLayout from "../components/AppLayout"

export default function Courses() {
  const role = sessionStorage.getItem("role") || "student"

  return (
    <AppLayout
      title="Course Library"
      subtitle={role === "teacher" ? "Teaching Workspace" : "Learning Materials"}
    >
      <section className="lms-grid min-h-[calc(100vh-76px)] p-4 sm:p-6 lg:p-10">
        <div className="mx-auto max-w-7xl">
          <div>
            <h2 className="text-xl font-semibold">
              {role === "student" ? "Available Courses" : "My Courses"}
            </h2>
            <p className="mt-1 text-sm text-white/40">
              Course cards are currently hidden.
            </p>
          </div>
        </div>
      </section>
    </AppLayout>
  )
}
