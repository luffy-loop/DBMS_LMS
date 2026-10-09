import { useEffect, useState } from "react"
import { Bell, Check, ExternalLink } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { apiJson } from "../api"

type Notification = { id:number; title:string; message:string; read:boolean; created_at:string; href:string|null }

export default function NotificationBell() {
  const [items, setItems] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)
  const navigate = useNavigate()

  async function load() {
    try {
      const data = await apiJson<{notifications:Notification[];unread_count:number}>("/notifications?page=1&page_size=8")
      setItems(data.notifications)
      setUnread(data.unread_count)
    } catch {}
  }

  useEffect(() => {
    load()
    const id = window.setInterval(load, 30000)
    return () => window.clearInterval(id)
  }, [])

  async function read(id:number, href:string|null) {
    try {
      await apiJson("/notifications/" + id + "/read", { method:"PATCH" })
      setItems(list => list.map(item => item.id === id ? {...item, read:true} : item))
      setUnread(value => Math.max(0, value - 1))
      if (href) navigate(href)
    } catch {}
  }

  async function readAll() {
    try {
      await apiJson("/notifications/read-all", { method:"PATCH" })
      setItems(list => list.map(item => ({...item, read:true})))
      setUnread(0)
    } catch {}
  }

  return <div className="relative">
    <button onClick={() => setOpen(v => !v)} className="lms-profile-trigger relative flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5" aria-label="Notifications" aria-expanded={open}>
      <Bell size={17}/>
      {unread > 0 && <span className="absolute -right-0.5 -top-0.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-violet-500 px-1 text-[9px] font-bold">{unread > 9 ? "9+" : unread}</span>}
    </button>
    {open && <div className="absolute right-0 top-12 z-50 w-[min(92vw,360px)] rounded-2xl border border-white/10 bg-[#0b101a] p-3 shadow-2xl">
      <div className="flex items-center justify-between px-2 py-1">
        <p className="text-sm font-semibold">Notifications</p>
        {unread > 0 && <button onClick={readAll} className="text-xs text-violet-300 hover:text-white">Mark all read</button>}
      </div>
      <div className="mt-2 max-h-80 space-y-1 overflow-y-auto">
        {items.length === 0 && <p className="p-4 text-center text-xs text-white/35">You're all caught up.</p>}
        {items.map(item => <button key={item.id} onClick={() => read(item.id, item.href)} className={"flex w-full items-start gap-3 rounded-xl p-3 text-left hover:bg-white/5 " + (item.read ? "opacity-55" : "bg-violet-400/[.06]")}>
          <span className={"mt-1 h-2 w-2 shrink-0 rounded-full " + (item.read ? "bg-white/15" : "bg-violet-400")}/>
          <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{item.title}</span><span className="mt-1 block text-xs leading-5 text-white/45">{item.message}</span><span className="mt-1 block text-[10px] text-white/25">{new Date(item.created_at).toLocaleString()}</span></span>
          {item.href ? <ExternalLink size={13} className="mt-1 shrink-0 text-white/25"/> : item.read ? <Check size={13} className="mt-1 shrink-0 text-emerald-300"/> : null}
        </button>)}
      </div>
    </div>}
  </div>
}
