import csv
import hashlib
import io
import logging
import os
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

from bson import ObjectId
from PIL import Image

from mongodb import mongo_db
from vector_store import index_resource, clear_search_cache

logger=logging.getLogger("lms.materials")
ALLOWED={
".pdf":{"application/pdf"},
".docx":{"application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/octet-stream"},
".doc":{"application/msword","application/octet-stream"},
".pptx":{"application/vnd.openxmlformats-officedocument.presentationml.presentation","application/octet-stream"},
".ppt":{"application/vnd.ms-powerpoint","application/octet-stream"},
".txt":{"text/plain","application/octet-stream"},
".md":{"text/markdown","text/plain","application/octet-stream"},
".png":{"image/png"},
".jpg":{"image/jpeg"},
".jpeg":{"image/jpeg"},
".webp":{"image/webp"},
".csv":{"text/csv","application/csv","application/vnd.ms-excel","text/plain","application/octet-stream"},
".xlsx":{"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","application/octet-stream"},
}
MAX_EXTRACTED_CHARS=int(os.getenv("MAX_EXTRACTED_CHARS","120000"))


def safe_filename(name:str)->str:
    value=Path(name or "").name.replace("\\x00","").strip()
    if not value or value in {".",".."} or len(value)>180: raise ValueError("Invalid filename")
    return value


def validate_file(name:str,content_type:str,data:bytes)->str:
    filename=safe_filename(name);suffix=Path(filename).suffix.lower()
    if suffix not in ALLOWED: raise ValueError("Unsupported file format")
    if content_type and content_type not in ALLOWED[suffix]: raise ValueError("MIME type does not match the file format")
    if not data: raise ValueError("Empty file")
    if suffix==".pdf":
        if not data.startswith(b"%PDF-"): raise ValueError("Invalid PDF signature")
    elif suffix in {".png",".jpg",".jpeg",".webp"}:
        try:
            with Image.open(io.BytesIO(data)) as image: image.verify()
        except Exception as exc: raise ValueError("Malformed image file") from exc
    elif suffix in {".docx",".pptx",".xlsx"}:
        if not zipfile.is_zipfile(io.BytesIO(data)): raise ValueError("Malformed Office file")
        required={".docx":"word/document.xml",".pptx":"ppt/presentation.xml",".xlsx":"xl/workbook.xml"}[suffix]
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if required not in archive.namelist(): raise ValueError("Malformed Office file")
    elif suffix in {".doc",".ppt"}:
        if not data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"): raise ValueError("Invalid legacy Office file signature")
    elif suffix in {".txt",".md",".csv"}:
        if b"\x00" in data[:4096]: raise ValueError("Binary content is not valid for this text format")
    return suffix


def _bounded_join(parts, limit=MAX_EXTRACTED_CHARS):
    """Join extracted text up to a fixed bound."""
    output=[]
    size=0
    for part in parts:
        if not part:
            continue
        remaining=limit-size
        if remaining<=0:
            break
        piece=("\n" if output else "")+str(part)
        output.append(piece[:remaining])
        size+=min(len(piece),remaining)
    return "".join(output)


def extract_content(data:bytes,suffix:str)->tuple[str,dict]:
    meta={}
    if suffix==".pdf":
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data));parts=[]
        size=0
        for number,page in enumerate(reader.pages,1):
            if size>=MAX_EXTRACTED_CHARS:
                break
            text=page.extract_text() or ""
            if text.strip():
                part="[Page "+str(number)+"]\n"+text
                parts.append(part[:MAX_EXTRACTED_CHARS-size])
                size+=len(parts[-1])
        meta["page_count"]=len(reader.pages)
        return _bounded_join(parts),meta
    if suffix==".docx":
        from docx import Document
        doc=Document(io.BytesIO(data))
        def parts():
            size=0
            for paragraph in doc.paragraphs:
                value=paragraph.text.strip()
                if value:
                    yield value
                    size+=len(value)+1
                    if size>=MAX_EXTRACTED_CHARS: return
            for table in doc.tables:
                for row in table.rows:
                    value=" | ".join(cell.text.strip() for cell in row.cells)
                    if value:
                        yield value
                        size+=len(value)+1
                        if size>=MAX_EXTRACTED_CHARS: return
        return _bounded_join(parts()),meta
    if suffix==".pptx":
        from pptx import Presentation
        presentation=Presentation(io.BytesIO(data))
        def parts():
            size=0
            for number,slide in enumerate(presentation.slides,1):
                text=" ".join(shape.text.strip() for shape in slide.shapes if hasattr(shape,"text") and shape.text.strip())
                if text:
                    value="[Slide "+str(number)+"] "+text
                    yield value
                    size+=len(value)+1
                    if size>=MAX_EXTRACTED_CHARS: return
        meta["slide_count"]=len(presentation.slides)
        return _bounded_join(parts()),meta
    if suffix in {".txt",".md"}: return data.decode("utf-8",errors="replace")[:MAX_EXTRACTED_CHARS],meta
    if suffix==".csv":
        def rows():
            reader=csv.reader(io.StringIO(data.decode("utf-8",errors="replace")))
            size=0
            for row in reader:
                value=" | ".join(row)
                yield value
                size+=len(value)+1
                if size>=MAX_EXTRACTED_CHARS: return
        return _bounded_join(rows()),meta
    if suffix==".xlsx":
        from openpyxl import load_workbook
        workbook=load_workbook(io.BytesIO(data),read_only=True,data_only=True)
        def rows():
            size=0
            for sheet in workbook.worksheets:
                value="[Sheet "+sheet.title+"]"
                yield value
                size+=len(value)+1
                if size>=MAX_EXTRACTED_CHARS: return
                for row in sheet.iter_rows(values_only=True):
                    values=["" if value is None else str(value) for value in row]
                    if any(values):
                        value=" | ".join(values)
                        yield value
                        size+=len(value)+1
                        if size>=MAX_EXTRACTED_CHARS: return
        try:
            content=_bounded_join(rows())
        finally:
            workbook.close()
        return content,meta
    if suffix in {".png",".jpg",".jpeg",".webp"}:
        try:
            import pytesseract
            with Image.open(io.BytesIO(data)) as image:text=pytesseract.image_to_string(image).strip()
            meta["ocr_status"]="READY" if text else "EMPTY"
            return text[:MAX_EXTRACTED_CHARS],meta
        except Exception as exc:
            logger.warning("OCR unavailable: %s",exc);meta["ocr_status"]="UNAVAILABLE";return "",meta
    if suffix in {".doc",".ppt"}:
        command="antiword" if suffix==".doc" else "catppt";executable=shutil.which(command)
        if not executable:raise ValueError("Legacy Office format is stored safely but cannot be indexed on this deployment; convert it to DOCX or PPTX")
        process=subprocess.run([executable,"-"],input=data,capture_output=True,timeout=10,check=False)
        if process.returncode!=0:raise ValueError("Legacy Office extraction failed")
        return process.stdout.decode("utf-8",errors="replace")[:MAX_EXTRACTED_CHARS],meta
    raise ValueError("Unsupported file format")


def prepare_resource(file_id:str):
    resource=mongo_db.resources.find_one({"_id":ObjectId(file_id)})
    if not resource:return False
    mongo_db.resources.update_one({"_id":resource["_id"]},{"$set":{"processing_status":"PROCESSING","extraction_status":"PROCESSING","indexing_status":"PENDING","updated_at":datetime.utcnow()}})
    try:
        content,metadata=extract_content(resource["file"],resource["extension"])
        if not content.strip() and resource["extension"] not in {".png",".jpg",".jpeg",".webp"}:raise ValueError("No extractable text found")
        mongo_db.resources.update_one({"_id":resource["_id"]},{"$set":{"content":content,"extraction_status":"READY","processing_status":"PROCESSING","indexing_status":"PROCESSING","updated_at":datetime.utcnow(),**metadata}})
        index_resource({"id":"resource-"+str(resource["_id"]),"title":resource.get("title") or resource.get("filename","Learning material"),"content":content,"type":"resource","course_id":resource["course_id"]})
        mongo_db.resources.update_one({"_id":resource["_id"]},{"$set":{"processing_status":"READY","indexing_status":"READY","updated_at":datetime.utcnow()}})
        clear_search_cache()
        return True
    except Exception as exc:
        logger.exception("Material processing failed for %s",file_id)
        mongo_db.resources.update_one({"_id":resource["_id"]},{"$set":{"processing_status":"FAILED","extraction_status":"FAILED","indexing_status":"FAILED","error_message":str(exc)[:1000],"updated_at":datetime.utcnow()}})
        return False


def duplicate_hash(course_id:int,sha256:str):
    return mongo_db.resources.find_one({"course_id":course_id,"sha256":sha256,"processing_status":{"$ne":"FAILED"}},{"_id":1,"filename":1})


def build_metadata(file,data:bytes,course_id:int,teacher_id:int,title:str):
    filename=safe_filename(file.filename or "learning-material")
    suffix=validate_file(filename,file.content_type or "",data)
    return {"course_id":course_id,"teacher_id":teacher_id,"title":(title or Path(filename).stem).strip()[:200] or Path(filename).stem,"filename":filename,"content_type":file.content_type or "application/octet-stream","extension":suffix,"size":len(data),"sha256":hashlib.sha256(data).hexdigest(),"content":"","processing_status":"UPLOADED","extraction_status":"PENDING","indexing_status":"PENDING","created_at":datetime.utcnow(),"updated_at":datetime.utcnow(),"file":data}
