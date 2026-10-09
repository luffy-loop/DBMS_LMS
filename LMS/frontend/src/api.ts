import { API } from "./config"

export class ApiError extends Error {
  status:number
  payload:unknown
  constructor(status:number,message:string,payload:unknown=null){super(message);this.name="ApiError";this.status=status;this.payload=payload}
}

function requestId(){if(typeof crypto!=="undefined"&&"randomUUID" in crypto)return crypto.randomUUID();return Math.random().toString(36).slice(2)}

export function clearSession(){
  sessionStorage.removeItem("token")
  sessionStorage.removeItem("role")
  sessionStorage.removeItem("name")
  sessionStorage.removeItem("userId")
}

function errorMessage(status:number,detail:unknown){
  if(typeof detail==="object"&&detail&&"message" in detail)return String((detail as {message?:unknown}).message)
  if(typeof detail==="string")return detail
  if(status===401)return "Your session is no longer valid. Please sign in again."
  if(status===403)return "You do not have permission to perform this action."
  if(status===408)return "The request timed out or was cancelled."
  if(status===422)return "Please check the information you entered."
  if(status===503)return "The LMS server is temporarily unavailable. Please try again."
  if(status===504)return "The request took too long. Please try again."
  if(status>=500)return "The LMS server encountered an unexpected error."
  return "Request failed"
}

export async function apiFetch(path:string,options:RequestInit={},timeoutMs=15000):Promise<Response>{
  const controller=new AbortController()
  const external=options.signal
  const timer=window.setTimeout(()=>controller.abort(),timeoutMs)
  if(external){
    if(external.aborted)controller.abort()
    else external.addEventListener("abort",()=>controller.abort(),{once:true})
  }
  const headers=new Headers(options.headers)
  headers.set("X-Request-ID",requestId())
  const token=sessionStorage.getItem("token")
  if(token&&!headers.has("Authorization"))headers.set("Authorization","Bearer "+token)
  try{
    const response=await fetch(API+path,{...options,headers,signal:controller.signal})
    if(response.status===401){clearSession();window.dispatchEvent(new Event("lms:logout"))}
    return response
  }catch(error){
    if(controller.signal.aborted)throw new ApiError(408,"The request timed out or was cancelled")
    throw new ApiError(0,"Unable to reach the LMS backend")
  }finally{window.clearTimeout(timer)}
}

export async function apiJson<T>(path:string,options:RequestInit={},timeoutMs=15000):Promise<T>{
  const response=await apiFetch(path,options,timeoutMs)
  const type=response.headers.get("content-type")||""
  const payload=type.includes("application/json")?await response.json().catch(()=>null):await response.text()
  if(!response.ok){
    const detail=typeof payload==="object"&&payload&&"detail" in payload?(payload as {detail?:unknown}).detail:payload
    throw new ApiError(response.status,errorMessage(response.status,detail),payload)
  }
  return payload as T
}

export function uploadFile(path:string,file:File,fields:Record<string,string>,onProgress:(value:number)=>void,signal?:AbortSignal){
 return new Promise<unknown>((resolve,reject)=>{
  const xhr=new XMLHttpRequest();xhr.open("POST",API+path)
  const token=sessionStorage.getItem("token");if(token)xhr.setRequestHeader("Authorization","Bearer "+token)
  xhr.setRequestHeader("X-Request-ID",requestId());xhr.responseType="json"
  xhr.upload.onprogress=e=>{if(e.lengthComputable)onProgress(Math.round(e.loaded/e.total*100))}
  xhr.onload=()=>{const payload=xhr.response??(()=>{try{return JSON.parse(xhr.responseText)}catch{return {}}})();if(xhr.status>=200&&xhr.status<300)resolve(payload);else{if(xhr.status===401){clearSession();window.dispatchEvent(new Event("lms:logout"))}reject(new ApiError(xhr.status,errorMessage(xhr.status,payload?.detail),payload))}}
  xhr.onerror=()=>reject(new ApiError(0,"Unable to reach the LMS backend while uploading"))
  xhr.ontimeout=()=>reject(new ApiError(408,"Upload timed out"));xhr.timeout=120000
  if(signal){if(signal.aborted)xhr.abort();signal.addEventListener("abort",()=>xhr.abort(),{once:true})}
  xhr.onabort=()=>reject(new ApiError(408,"Upload cancelled"))
  const form=new FormData();form.append("files",file);Object.entries(fields).forEach(([key,value])=>form.append(key,value));xhr.send(form)
 })
}
