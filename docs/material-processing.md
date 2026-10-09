# Learning Material Processing

## Supported uploads

The teacher material pipeline accepts:

- PDF
- DOCX
- DOC (stored safely; indexing requires antiword on the deployment)
- PPTX
- PPT (stored safely; indexing requires catppt on the deployment)
- TXT
- MD
- PNG
- JPG/JPEG
- WEBP
- CSV
- XLSX

Every file is checked for extension, MIME type, size, safe filename, and format-specific signature/structure before storage. Duplicate SHA-256 content is rejected within the same course.

## Processing lifecycle

1. UPLOADED — bytes are safely stored in MongoDB.
2. PROCESSING — extraction/indexing is running in a background task.
3. READY — extracted content is indexed and searchable.
4. FAILED — the material remains visible with an error message.

The upload endpoint does not wait for extraction or embedding. The frontend polls the persisted status and can continue navigating while processing happens.

PDF page numbers, PPTX slide numbers, XLSX sheet names, file size, MIME type and OCR status are retained where available.

Images use optional Tesseract OCR. If the OCR binary is unavailable, the image is stored safely but its processing status explains that OCR is unavailable. The system does not claim visual understanding beyond the implemented OCR path.

## Retry

Failed processing can be retried by re-uploading the same content after the underlying problem is fixed. Search/indexing uses only resources whose processing status is READY.

## Resource security

Students can access resources only for enrolled courses. Teachers can access only their own courses. Admins retain administrative access.
