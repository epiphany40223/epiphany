# Music Score Indexer

This script traverses a Google Drive folder hierarchy, identifies musical score PDFs, extracts score metadata and lyrics using the OpenAI API, and generates a consolidated Markdown index.

## Setup

1.  **Google Drive API Credentials**:
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project.
    *   Enable the **Google Drive API**.
    *   Configure the **OAuth consent screen**.
    *   Go to **Credentials**, click **Create Credentials** -> **OAuth client ID**.
    *   Select **Desktop app**.
    *   Download the JSON file and rename it to `client_id.json` in this directory.

2.  **OpenAI API Key**:
    *   Go to the [OpenAI Dashboard](https://platform.openai.com/).
    *   Create a new API key.
    *   Create a `.env` file in this directory and add:
        ```
        OPENAI_API_KEY=your_api_key_here
        ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the script by providing the URL of the root Google Drive folder:

```bash
./index_scores.py --google-drive-root-url "https://drive.google.com/drive/folders/your-folder-id"
```

### Options

*   `--google-drive-root-url`: The root-level Google Drive URL to start indexing.
*   `--output`: Specify the name of the output Markdown file (default: `music_index.md`).
*   `--failures-output`: Specify the name of the batch failure report Markdown file (default: `failures.md`).
*   `--google-drive-cache`: JSON file to store/load Google Drive discovery results (default: `google-drive-cache.json`).
*   `--google-drive-skip-folders NAMES`: Comma-delimited case-insensitive Google Drive folder names to skip (default: `old`).
*   `--skip-discovery`: Skip GDrive discovery and load from cache instead.
*   `--skip-analysis`: Perform discovery and save to cache, but skip OpenAI analysis.
*   `--submit-analysis-batch`: Submit PDFs that do not already have fresh cached analysis, an active batch submission, or a terminal batch answer.
*   `--collect-analysis-batch`: Check recorded OpenAI batches, collect terminal batch results, update the local analysis cache, and generate Markdown.
*   `--limit N`: Maximum number of PDF files to analyze after discovery.
*   `--analysis-batch-size N`: Maximum number of PDF files to submit in one OpenAI analysis batch (default: `500`).
*   `--retry-analysis-error-codes CODES`: Comma-delimited OpenAI error codes or incomplete-response reasons to retry, such as `context_length_exceeded` or `content_filter`.
*   `--allow-concurrent-analysis-batches`: Allow a new batch to be submitted while previous batches are still uncollected.
*   `--state-dir`: Directory to store individual analysis results (default: `analysis-results/`).
*   `--model`: OpenAI model to use (default: `gpt-5.4-mini`).
*   `--pdf-detail`: PDF rendering detail sent to OpenAI, either `low` or `high` (default: `high`).

### Batch analysis workflow

For large libraries, use the OpenAI Batch API instead of keeping the script running for synchronous analysis:

```bash
./index_scores.py --google-drive-root-url "https://drive.google.com/drive/folders/your-folder-id" --submit-analysis-batch
```

This discovers PDFs, skips any PDF with a fresh local analysis cache, skips any PDF already recorded as submitted to an active batch, skips any PDF that already has a terminal non-retryable batch answer, uploads the next batch of remaining PDFs to OpenAI, and submits one batch.

The current implementation submits one OpenAI batch per `--submit-analysis-batch` invocation. By default, that batch is capped at 500 PDFs by `--analysis-batch-size` to avoid overwhelming request-per-minute limits. `--limit N` still applies before batch selection, so it can be used to restrict the candidate set for a run. To test-submit only a few outstanding PDFs, prefer `--analysis-batch-size N` without `--limit`; otherwise `--limit` may select already-cached PDFs before batch candidate filtering runs.

By default, the script will not submit a new batch while previous batches are uncollected. Run `--collect-analysis-batch` before submitting the next batch. Use `--allow-concurrent-analysis-batches` only if you intentionally want overlapping OpenAI batches.

Batch state is stored in `analysis-results/openai-analysis-batches.json`; batch input JSONL files are stored under `analysis-results/batch-inputs/`.

If you run the same `--submit-analysis-batch` command again with no Google Drive changes, it should report that no PDFs need submission.

Later, collect completed results and generate Markdown:

```bash
./index_scores.py --google-drive-root-url "https://drive.google.com/drive/folders/your-folder-id" --collect-analysis-batch
```

Collecting stores each result in the same per-PDF cache used by synchronous analysis. PDFs that are determined not to be musical scores, or that return a terminal request-level error, are cached too, so they are not submitted again unless the Drive file changes.

Collection also writes a current batch failure report to `failures.md` by default. Use `--failures-output` to choose a different filename. The report includes failure counts, PDF names and links, Drive file IDs, batch/request IDs, local-time timestamps, status values, lyric request mode, and the OpenAI error payload when one is available. If a later batch supersedes an older failure for the same Drive file, only the current result is reported, but the report also shows the failed-response history and error counts for that PDF.

`--collect-analysis-batch` does not download partial results while a batch is still running. It waits until the whole OpenAI batch reaches a terminal status such as `completed`, `failed`, `expired`, or `cancelled`, then downloads and processes the batch output/error files.

### Re-run behavior

The script avoids duplicate OpenAI work using local state:

*   PDFs already processed by the synchronous path are skipped when their per-PDF analysis cache is fresh relative to the Google Drive `modifiedTime`.
*   PDFs already submitted to a still-active batch are skipped.
*   PDFs with terminal non-retryable batch outcomes are skipped when the Drive file has not changed. Terminal outcomes include successful score analysis, not-a-score answers, and permanent request errors such as context-window failures.
*   Retryable outcomes such as rate-limit failures, content-filter-incomplete responses, missing output text, and model-output parsing failures do not block resubmission.
*   Context-window failures such as `context_length_exceeded` are treated as permanent for the same model and PDF detail level because retrying the identical request is expected to fail again. They become eligible again if you intentionally change the analysis strategy, such as using a different `--model` or `--pdf-detail`.
*   When changing model or PDF detail only for a known failure class, use `--retry-analysis-error-codes` so the script does not treat every previous success from the old model/detail as stale. For example, `--submit-analysis-batch --model gpt-5.4 --retry-analysis-error-codes context_length_exceeded` retries only unchanged PDFs whose prior error code was `context_length_exceeded`. The same filter also applies to synchronous analysis mode; non-matching PDFs keep using their existing source-fresh cached analysis for Markdown generation instead of being reanalyzed with the new model.
*   `file_above_max_size` is a file transfer limit rather than a model context limit; using a larger model is not expected to fix it.
*   The first analysis attempt asks for verbatim lyrics when they can be returned. If OpenAI returns an incomplete response with `content_filter`, collection records that error and the next batch submission for that same unchanged PDF switches to a summary-only lyric prompt.
*   Batch state keeps `file_error_history` for each PDF, including the countable error key, error message, status, batch/request IDs, lyric request mode, timestamps, and the exact stored error payload for each failed response.
*   If Google Drive reports a newer `modifiedTime` for a PDF, that PDF becomes eligible for analysis again.

## How it works

1.  **Traversal**: The script recursively visits all subfolders starting from the provided root URL. Discovery results are cached in `google-drive-cache.json`.
2.  **Identification**: It identifies all PDF files.
3.  **Incremental refresh**: Later discovery runs use the Google Drive Changes API to update the cache when possible, falling back to a full traversal if the stored change token is missing or expired.
4.  **Analysis**: Each PDF is uploaded to OpenAI to extract the song title, lyrics, arrangement details, and metadata using the specified model (e.g., `gpt-5.4-mini`). The script asks for verbatim lyrics first; when verbatim lyrics are unavailable or cannot be returned, it asks for a non-verbatim lyric summary and labels it as a summary in the Markdown output. Verbatim lyrics are requested with line and stanza breaks, and the generated Markdown preserves lyric line breaks while leaving blank lines between stanzas. In batch mode, a PDF that previously returned a `content_filter` incomplete response is retried with a summary-only lyric prompt. Analysis can run synchronously or through the two-step batch workflow.
5.  **De-duplication**: Songs are grouped by title. Multiple PDFs for the same song are listed as arrangements.
6.  **Caching**: Discovered files, batch submissions, and analysis results are cached locally. Stored timestamps are UTC and labeled with `_utc`; user-facing log messages display local time.
7.  **Markdown Generation**: A consolidated Markdown file is created, sorted alphabetically by song title.
