# FAC meeting minutes generator

Generates Finance Advisory Committee ("FAC") meeting minutes as a Word
document and a PDF, by feeding the meeting transcript and the monthly
financial and technology documents to an OpenAI model.

The output follows the layout the FAC has used for its minutes by hand: a
centered title and meeting date, a `Logistics:` line with the start and
adjournment times, `Attendance:` and `Absent:` lines, and then the numbered
sections (approval of the last minutes, financial report, future fiscal
planning, facilities, technology, open discussion, bulletin highlights). The
financial report carries a Category / Actual / Budget / YTD table. That layout
is implemented directly in the two renderers, not read from a template file at
run time; past minutes are not kept in this repository because they contain
parishioner names and parish financial data.

## Setup

```
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Put your OpenAI API key in a file somewhere **outside** this repository, and
pass that filename with `--openai-api-keyfile`. Do not commit the key.

## Usage

```
./fac-meeting-notes.py \
    --openai-api-keyfile ~/credentials/openai-api-key.txt \
    --transcript "FAC Meeting 260610.srt" \
    --financial-highlights "Financial Highlights - May2026.pdf" \
    --financial-observations "Observations - May2026.pdf" \
    --technology-update "ECC Tech Committee June 2026.docx"
```

This writes two files into the current directory (override with `--outdir`):

* `YYYY-MM-DD FAC Meeting notes.docx`
* `YYYY-MM-DD FAC Meeting notes.pdf`

`YYYY-MM-DD` is the date of the meeting, which the model extracts from the
input documents. If it guesses wrong, or cannot find a date at all, set the
date yourself with `--date 2026-06-10`.

Run `./fac-meeting-notes.py --help` for the full list of options.

### Input documents

Each of the four inputs may be a `.pdf`, `.docx`, `.txt`, `.md`, `.srt`,
`.vtt`, `.csv`, or `.xlsx` file.

**Prefer PDF for the financial documents.** Most formats are attached to the
request as native OpenAI file inputs, and OpenAI extracts only *text* from
them; for a PDF it also sends the model an image of each page, which preserves
the layout of the financial tables. OpenAI accepts at most 50 MB of attached
files per request.

`.srt` and `.vtt` subtitle files are not a file type OpenAI accepts, so the
script flattens them locally into `[HH:MM:SS] [SPEAKER_04]: ...` lines and
sends that text inline. The timestamps are kept because the model uses them to
work out the adjournment time (they are elapsed time from the start of the
recording, not clock times), and the speaker tags are kept because the model
uses them to tell the speakers apart. A WhisperX transcript with diarization
is exactly the expected shape.

## How it works, and why

The model is asked for the *content* of the minutes as structured JSON (see
`MINUTES_SCHEMA`), and this script renders the `.docx` (python-docx) and the
`.pdf` (ReportLab) from that JSON.

OpenAI's code interpreter tool *can* write a `.docx` and a `.pdf` itself, and
that would remove both renderers from this script. Rendering locally is a
deliberate trade-off:

* The formatting is deterministic, so the minutes look the same every month
  instead of being re-derived by the model on each run.
* Fixing a layout problem is a code change, not a prompt change.
* `--from-json` re-renders both documents from a saved response, so iterating
  on formatting costs nothing and does not need the API at all.

The model supplies the content; this script supplies the form.

## Reviewing the output

The minutes are a starting point, not a finished document — read them before
sending them out. In particular:

* The model is told to never invent a time or an attendee. Where it could not
  determine something it emits a placeholder — `[START TIME]`,
  `[ADJOURNMENT TIME]`, `[ATTENDEES]`, `[ABSENTEES]` — which you must fill in
  by hand. Search the output for `[`.
* Machine transcripts mangle proper names and the speaker tags are anonymous,
  so attendance and attributions are worth a second look.
* Check the dollar figures against the financial documents.

## Debugging options

| Option | Effect |
| --- | --- |
| `--dry-run` | Read the inputs and assemble the request, but do not call OpenAI or write any documents |
| `--save-prompt FILE` | Write the assembled prompt (with attachments noted) to `FILE` |
| `--save-json FILE` | Also write the model's structured response to `FILE` |
| `--from-json FILE` | Skip OpenAI entirely and re-render the documents from a saved response |
| `--model` | Which OpenAI model to use (default: `gpt-5`) |
| `--reasoning-effort` | Reasoning effort for reasoning models (default: `medium`) |

The usual loop when changing the *formatting* is to run once with
`--save-json`, then iterate with `--from-json` against the saved file.
