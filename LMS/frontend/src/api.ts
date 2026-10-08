import { API } from "./config"

export class ApiError extends Error {
  status:number
  payload:unknown
  constructor(status:number,message:string,payload:unknown=null){super(message);this.status=status;this.payload=payload}
}
function requestId(){if(typeof crypto!=="undefined"&&"randomUUID" in crypto)return crypto.randomUUID();return Math.random().toString(36).slice(2)}

export async function apiFetch(path:string,options:RequestInit={},timeoutMs=15000):Promise<Response>{
  const controller=new AbortController();const external=options.signal;const timer=window.setTimeout(()=>controller.abort(),timeoutMs)
  if(external){if(external.aborted)controller.abort();else external.addEventListener("abort",()=>controller.abort(),{once:true})}
  const headers=new Headers(options.headers);headers.set("X-Request-ID",requestId());const token=localStorage.getItem("token");if(token&&!headers.has("Authorization"))headers.set("Authorization","Bearer "+token)
  try{return await fetch(API+path,{...options,headers,signal:controller.signal})}
  catch(error){if(controller.signal.aborted)throw new ApiError(408,"Request timed out or was cancelled");throw new ApiError(0,"Unable to reach the LMS backend")}
  finally{window.clearTimeout(timer)}
}
export async function apiJson<T>(path:string,options:RequestInit={},timeoutMs=15000):Promise<T>{
  const response=await apiFetch(path,options,timeoutMs);const type=response.headers.get("content-type")||"";const payload=type.includes("application/json")?await response.json().catch(()=>null):await response.text()
  if(!response.ok){const detail=typeof payload==="object"&&payload&&"detail" in payload?(payload as {detail?:unknown}).detail:payload;const message=typeof detail==="string"?detail:typeof detail==="object"&&detail&&"message" in detail?String((detail as {message?:unknown}).message):"Request failed";throw new ApiError(response.status,message,payload)}
  return payload as T
}
export function uploadFile(path:string,file:File,fields:Record<string,string>,onProgress:(value:number)=>void,signal?:AbortSignal){
 return new Promise<unknown>((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open("POST",API+path);const token=localStorage.getItem("token");if(token)xhr.setRequestHeader("Authorization","Bearer "+token);xhr.setRequestHeader("X-Request-ID",requestId());xhr.responseType="json";xhr.upload.onprogress=e=>{if(e.lengthComputable)onProgress(Math.round(e.loaded/e.total*100))};xhr.onload=()=>{const payload=xhr.response??(()=>{try{return JSON.parse(xhr.responseText)}catch{return {}}})();if(xhr.status>=200&&xhr.status<300)resolve(payload);else reject(new ApiError(xhr.status,payload?.detail||"Upload failed",payload))};xhr.onerror=()=>reject(new ApiError(0,"Network error while uploading"));xhr.ontimeout=()=>reject(new ApiError(408,"Upload timed out"));xhr.timeout=120000;if(signal){if(signal.aborted)xhr.abort();signal.addEventListener("abort",()=>xhr.abort(),{once:true})};xhr.onabort=()=>reject(new ApiError(408,"Upload cancelled"));const form=new FormData();form.append("files",file);Object.entries(fields).forEach(([key,value])=>form.append(key,value));xhr.send(form)})
}
