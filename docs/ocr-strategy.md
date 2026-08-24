# RegLens OCR Strategy

RegLens currently treats scanned or image-only PDFs as unsupported for automatic
ingestion. This is intentional: a compliance RAG system should not silently
index uncertain OCR output without a clear dependency, confidence, and audit
policy.

## Current Contract

- `PdfCorpusLoader` extracts text with `pypdf`.
- If no page contains extractable text, ingestion returns
  `PDF did not contain extractable text`.
- `/admin/ingest` records the job as failed with `corpus_load_error`.
- No source, section, chunk, vector, or retrieval index state is persisted for
  scanned PDFs that produce no extractable text.
- Default install and default verification must not require OCR packages,
  system OCR binaries, model downloads, or network calls.

## Recommended Future OCR Path

OCR should be optional and explicit. A future implementation should add a
separate OCR extra or runtime setting rather than changing default PDF
ingestion behavior.

Recommended acceptance requirements:

- Add an opt-in setting such as `REGLENS_ENABLE_PDF_OCR=false` by default.
- Add an optional dependency group such as `ocr`, separate from `pdf`.
- Use local-only OCR tooling; do not call remote OCR APIs in default or local
  tests.
- Preserve page numbers, source checksum, raw storage URI, corpus version, and
  extraction method for every OCR-derived section.
- Mark OCR-derived sections with metadata such as
  `extraction_method = "ocr"` and OCR confidence when available.
- Return warnings when confidence is low or page text could not be recovered.
- Keep default tests deterministic; OCR tests must skip cleanly when optional
  dependencies or system binaries are unavailable.
- Never mix OCR output into answers without normal citation and quote
  verification.

## Deferred Decision

No OCR implementation is active yet. The product remains safer by failing
closed on scanned PDFs until the OCR dependency and confidence policy are
chosen explicitly.
