#!/usr/bin/env python3

import os
import sys
import re
import json
import io
import time
import uuid
import unicodedata
from datetime import datetime, timezone
from dotenv import load_dotenv

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    # If not found, look for it in the parent directory as well
    parent_moddir = os.path.join(os.path.dirname(os.getcwd()), 'ecc-python-modules')
    if os.path.exists(parent_moddir):
        moddir = parent_moddir
    else:
        print("ERROR: Could not find the ecc-python-modules directory.")
        print("ERROR: Please make a ecc-python-modules sym link and run again.")
        exit(1)

# On MS Windows, git checks out sym links as a file with a single-line
# string containing the name of the file that the sym link points to.
if os.path.isfile(moddir):
    with open(moddir) as fp:
        symlink_dir = fp.readlines()
    moddir = os.path.join(os.getcwd(), symlink_dir[0].strip())

sys.path.insert(0, moddir)

import ECC
import Google
import GoogleAuth
from oauth2client import tools
from google.api_core import retry
from openai import OpenAI
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# Globals
args = None
log = None

# Default for CLI arguments
gapp_id='client_id.json'
guser_cred_file = 'user-credentials.json'
verbose = True
debug = False
logfile = "log.txt"

DISCOVERY_CACHE_VERSION = 2
DRIVE_FILE_FIELDS = "id, name, mimeType, webViewLink, parents, modifiedTime, driveId, trashed"
BATCH_STATE_VERSION = 1
BATCH_STATE_FILENAME = "openai-analysis-batches.json"
BATCH_INPUT_DIRNAME = "batch-inputs"
BATCH_ENDPOINT = "/v1/responses"
BATCH_COMPLETION_WINDOW = "24h"
BATCH_SKIP_FILE_STATUSES = {
    "submitted",
    "completed",
    "not_score",
    "permanent_error",
}
BATCH_TERMINAL_STATUSES = {
    "completed",
    "failed",
    "expired",
    "cancelled",
}
FAILURE_REPORT_STATUSES = {
    "permanent_error",
    "retryable_error",
    "failed",
    "expired",
    "cancelled",
    "stale",
}
LYRICS_MODE_VERBATIM_FIRST = "verbatim_first"
LYRICS_MODE_SUMMARY_ONLY = "summary_only"

SCORE_ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "is_score": {
            "type": "boolean",
            "description": "True only when the PDF is a musical score or sheet music for a song."
        },
        "song_title": {
            "type": ["string", "null"],
            "description": "Primary title of the song, or null if the PDF is not a score or no title is found."
        },
        "lyrics": {
            "type": ["string", "null"],
            "description": "Verbatim lyrics from the PDF when they are available and can be returned, otherwise null. Preserve lyric line breaks with newline characters and separate verses/stanzas with blank lines."
        },
        "lyrics_summary": {
            "type": ["string", "null"],
            "description": "A brief non-verbatim summary of the lyrics when verbatim lyrics are not available or cannot be returned, otherwise null."
        },
        "lyrics_type": {
            "type": ["string", "null"],
            "enum": ["verbatim", "summary", "none", None],
            "description": "Set to verbatim when lyrics contains verbatim lyrics, summary when lyrics_summary contains a non-verbatim fallback, none when no lyrics are present, or null when the PDF is not a score."
        },
        "arrangement_description": {
            "type": ["string", "null"],
            "description": "Specific arrangement such as Piano/Vocal/Guitar, Flute solo, or SATB Choir."
        },
        "composer": {
            "type": ["string", "null"],
            "description": "Composer or songwriter name when found."
        },
        "publication_date": {
            "type": ["string", "null"],
            "description": "Year or date when found."
        },
        "publisher": {
            "type": ["string", "null"],
            "description": "Publisher name when found."
        },
        "musician_notes": {
            "type": ["string", "null"],
            "description": "Specific notes, instructions, or performance markings for the musician."
        },
    },
    "required": [
        "is_score",
        "song_title",
        "lyrics",
        "lyrics_summary",
        "lyrics_type",
        "arrangement_description",
        "composer",
        "publication_date",
        "publisher",
        "musician_notes",
    ],
}

SCORE_ANALYSIS_PROMPT = """Analyze this PDF.

First, determine if it is a musical score or sheet music for a song.
If it is not a musical score, set is_score to false and set every other field to null.
If it is a musical score, extract the song title, arrangement, composer/songwriter,
publication date, publisher, and musician-facing notes.
For lyrics, first try to return the complete verbatim lyrics visible in the PDF:
- If verbatim lyrics are available and can be returned, put them in lyrics,
  set lyrics_type to "verbatim", and set lyrics_summary to null. Preserve the
  lyric line order. Use newline characters between lyric lines and a blank line
  between verses, stanzas, refrains, or sections when those breaks appear in the
  PDF or can be clearly inferred from the layout. Do not collapse lyrics into
  one paragraph. Do not add section labels unless they are visible in the PDF.
- If verbatim lyrics are not available or cannot be returned for any reason, but
  lyrics are present, set lyrics to null, put a brief non-verbatim summary in
  lyrics_summary, and set lyrics_type to "summary".
- If no lyrics are present, set lyrics and lyrics_summary to null, and set
  lyrics_type to "none".
Return only data supported by the PDF. Use null for missing fields.
"""

SCORE_ANALYSIS_SUMMARY_ONLY_PROMPT = """Analyze this PDF.

First, determine if it is a musical score or sheet music for a song.
If it is not a musical score, set is_score to false and set every other field to null.
If it is a musical score, extract the song title, arrangement, composer/songwriter,
publication date, publisher, and musician-facing notes.
For lyrics, do not return verbatim lyric text:
- If lyrics are present, set lyrics to null, put a brief non-verbatim summary in
  lyrics_summary, and set lyrics_type to "summary".
- If no lyrics are present, set lyrics and lyrics_summary to null, and set
  lyrics_type to "none".
Return only data supported by the PDF. Use null for missing fields.
"""

def parse_timestamp(timestamp):
    if isinstance(timestamp, datetime):
        dt = timestamp
    else:
        text = timestamp.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        dt = datetime.fromisoformat(text)

    # Backward compatibility: old analysis caches used naive local timestamps.
    if dt.tzinfo is None:
        dt = dt.astimezone()

    return dt.astimezone(timezone.utc)

def utc_timestamp(timestamp=None):
    if timestamp is None:
        dt = datetime.now(timezone.utc)
    else:
        dt = parse_timestamp(timestamp)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def local_timestamp(timestamp):
    local_dt = parse_timestamp(timestamp).astimezone()
    return f"{local_dt.isoformat(timespec='seconds')} ({local_dt.tzname()})"

def local_timestamp_or_unknown(timestamp):
    if not timestamp:
        return "unknown"
    try:
        return local_timestamp(timestamp)
    except Exception:
        return str(timestamp)

def normalize_analysis_timestamp(data):
    changed = False
    cached_at = data.get('cached_at_utc') or data.get('cached_at')
    if cached_at:
        normalized = utc_timestamp(cached_at)
        if data.get('cached_at_utc') != normalized:
            data['cached_at_utc'] = normalized
            changed = True
    if 'cached_at' in data:
        del data['cached_at']
        changed = True
    return changed

def get_pdf_modified_time_utc(pdf):
    modified_time = pdf.get('modified_time_utc')
    if not modified_time:
        return None
    return utc_timestamp(modified_time)

def normalize_cli_option_names(parser):
    for action in parser._actions:
        new_option_strings = []
        changed = False

        for option_string in action.option_strings:
            new_option_string = option_string.replace("_", "-")
            new_option_strings.append(new_option_string)
            if new_option_string != option_string:
                parser._option_string_actions.pop(option_string, None)
                changed = True

        if changed:
            action.option_strings = new_option_strings
            for option_string in new_option_strings:
                parser._option_string_actions[option_string] = action

def setup_cli_args():
    normalize_cli_option_names(tools.argparser)

    tools.argparser.add_argument('-h', '--help',
                                 action='help',
                                 help='Show this help message and exit')
    tools.argparser.add_argument('--google-drive-root-url', help='The root-level Google Drive URL to start indexing')
    tools.argparser.add_argument('--output', default='music_index.md', help='Output markdown file name')
    tools.argparser.add_argument('--failures-output',
                                 default='failures.md',
                                 help='Output markdown file for batch analysis failures')
    tools.argparser.add_argument('--google-drive-cache',
                                 default='google-drive-cache.json',
                                 help='JSON file to store/load Google Drive discovery results')
    tools.argparser.add_argument('--google-drive-skip-folders',
                                 default='old',
                                 metavar='NAMES',
                                 help='Comma-delimited case-insensitive Google Drive folder names to skip (default: old)')
    tools.argparser.add_argument('--skip-discovery', action='store_true', help='Skip GDrive discovery and load from cache instead')
    tools.argparser.add_argument('--skip-analysis', action='store_true', help='Perform discovery and save to cache, but skip analysis')
    analysis_mode = tools.argparser.add_mutually_exclusive_group()
    analysis_mode.add_argument('--submit-analysis-batch',
                               action='store_true',
                               help='Submit unanalyzed PDFs to the OpenAI Batch API and exit')
    analysis_mode.add_argument('--collect-analysis-batch',
                               action='store_true',
                               help='Collect completed OpenAI batch results and generate markdown')
    tools.argparser.add_argument('--limit', type=int, help='Maximum number of PDF files to analyze after discovery')
    tools.argparser.add_argument('--analysis-batch-size',
                                 type=int,
                                 default=500,
                                 help='Maximum number of PDF files to submit in one OpenAI analysis batch')
    tools.argparser.add_argument('--retry-analysis-error-codes',
                                 metavar='CODES',
                                 help='Comma-delimited OpenAI error codes/reasons to retry, e.g. context_length_exceeded')
    tools.argparser.add_argument('--allow-concurrent-analysis-batches',
                                 action='store_true',
                                 help='Allow submitting a new OpenAI analysis batch while previous batches are uncollected')
    tools.argparser.add_argument('--state-dir', default='analysis-results', help='Directory to store/load individual analysis results')
    tools.argparser.add_argument('--model', default='gpt-5.4-mini', help='OpenAI model to use for analysis')
    tools.argparser.add_argument('--pdf-detail',
                                 choices=['low', 'high'],
                                 default='high',
                                 help='PDF rendering detail to send to OpenAI')

    global gapp_id
    tools.argparser.add_argument('--app-id',
                                 default=gapp_id,
                                 help='Filename containing Google application credentials')
    global guser_cred_file
    tools.argparser.add_argument('--user-credentials',
                                 default=guser_cred_file,
                                 help='Filename containing Google user credentials')

    global verbose
    tools.argparser.add_argument('--verbose',
                                 action='store_true',
                                 default=verbose,
                                 help='If enabled, emit extra status messages during run')
    global debug
    tools.argparser.add_argument('--debug',
                                 action='store_true',
                                 default=debug,
                                 help='If enabled, emit even more extra status messages during run')
    global logfile
    tools.argparser.add_argument('--logfile',
                                 default=logfile,
                                 help='Store verbose/debug logging to the specified file')

    global args
    args = tools.argparser.parse_args()

    if args.skip_analysis and (args.submit_analysis_batch or args.collect_analysis_batch):
        tools.argparser.error("--skip-analysis cannot be combined with batch analysis modes")
    if args.analysis_batch_size <= 0:
        tools.argparser.error("--analysis-batch-size must be greater than 0")

    # --debug also implies --verbose
    if args.debug:
        args.verbose = True
    args.google_drive_skip_folders = parse_comma_delimited_values(args.google_drive_skip_folders)
    args.retry_analysis_error_codes = parse_comma_delimited_values(args.retry_analysis_error_codes)

    return args

def parse_comma_delimited_values(text):
    if not text:
        return set()
    return {
        value.strip().casefold()
        for value in text.split(',')
        if value.strip()
    }

def extract_folder_id(url):
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    return url

def format_folder_for_log(folder_id, folder_name=None):
    if folder_name:
        return f"{folder_name} ({folder_id})"
    return folder_id

def should_skip_drive_folder(file):
    folder_name = file.get('name')
    return bool(folder_name and folder_name.casefold() in args.google_drive_skip_folders)

@retry.Retry(predicate=Google.retry_errors)
def list_files_in_folder(service, folder_id, folder_name=None):
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        files = []
        page_token = None
        folder_label = format_folder_for_log(folder_id, folder_name)

        while True:
            httpref = service.files().list(
                q=query,
                fields=f"nextPageToken, files({DRIVE_FILE_FIELDS})",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            )
            log.debug(f"Executing Google API call: Listing files in folder {folder_label}")
            results = Google.call_api(httpref, log)
            if not results:
                return files

            files.extend(results.get('files', []))
            page_token = results.get('nextPageToken')
            if not page_token:
                return files
    except Exception as e:
        log.warning(f"Could not list files in folder {format_folder_for_log(folder_id, folder_name)}: {e}")
        return []

@retry.Retry(predicate=Google.retry_errors)
def get_file_metadata(service, file_id):
    httpref = service.files().get(
        fileId=file_id,
        fields=DRIVE_FILE_FIELDS,
        supportsAllDrives=True
    )
    return Google.call_api(httpref, log)

@retry.Retry(predicate=Google.retry_errors)
def get_start_page_token(service, drive_id=None):
    kwargs = {'supportsAllDrives': True}
    if drive_id:
        kwargs['driveId'] = drive_id

    httpref = service.changes().getStartPageToken(**kwargs)
    results = Google.call_api(httpref, log)
    return results.get('startPageToken') if results else None

def normalize_drive_file(file):
    item = {
        'id': file['id'],
        'name': file.get('name'),
        'mimeType': file.get('mimeType'),
        'webViewLink': file.get('webViewLink'),
        'parents': file.get('parents', []),
        'driveId': file.get('driveId'),
        'trashed': file.get('trashed', False),
    }

    if file.get('modifiedTime'):
        item['modified_time_utc'] = utc_timestamp(file['modifiedTime'])

    return {key: value for key, value in item.items() if value is not None}

def create_google_drive_cache(root_id, root_url=None):
    return {
        'schema_version': DISCOVERY_CACHE_VERSION,
        'root_id': root_id,
        'root_url': root_url,
        'drive_id': None,
        'change_page_token': None,
        'generated_at_utc': utc_timestamp(),
        'updated_at_utc': utc_timestamp(),
        'folders': {},
        'pdfs': {},
    }

def cache_contains_parent(cache, file):
    return any(parent in cache['folders'] for parent in file.get('parents', []))

def add_folder_to_cache(cache, file):
    cache['folders'][file['id']] = normalize_drive_file(file)
    if file['id'] == cache['root_id']:
        cache['drive_id'] = file.get('driveId')

def add_pdf_to_cache(cache, file):
    pdf = normalize_drive_file(file)
    parent_id = pdf.get('parents', [cache['root_id']])[0]
    pdf['parentFolderLink'] = f"https://drive.google.com/drive/folders/{parent_id}"
    cache['pdfs'][pdf['id']] = pdf

def remove_folder_subtree_from_cache(cache, folder_id):
    removed_folders = {folder_id}

    changed = True
    while changed:
        changed = False
        for cached_folder_id, folder in list(cache['folders'].items()):
            if cached_folder_id in removed_folders:
                continue
            if any(parent in removed_folders for parent in folder.get('parents', [])):
                removed_folders.add(cached_folder_id)
                changed = True

    for cached_folder_id in removed_folders:
        if cached_folder_id != cache['root_id']:
            cache['folders'].pop(cached_folder_id, None)

    for pdf_id, pdf in list(cache['pdfs'].items()):
        if any(parent in removed_folders for parent in pdf.get('parents', [])):
            cache['pdfs'].pop(pdf_id, None)

def prune_cache_to_root(cache):
    reachable = {cache['root_id']}
    changed = True

    while changed:
        changed = False
        for folder_id, folder in cache['folders'].items():
            if folder_id in reachable:
                continue
            if any(parent in reachable for parent in folder.get('parents', [])):
                reachable.add(folder_id)
                changed = True

    for folder_id in list(cache['folders'].keys()):
        if folder_id not in reachable:
            cache['folders'].pop(folder_id, None)

    for pdf_id, pdf in list(cache['pdfs'].items()):
        if not any(parent in reachable for parent in pdf.get('parents', [])):
            cache['pdfs'].pop(pdf_id, None)

def scan_folder_tree(service, folder_id, cache, folder_name=None):
    files = list_files_in_folder(service, folder_id, folder_name)
    for file in files:
        if file.get('mimeType') == Google.mime_types['folder']:
            if should_skip_drive_folder(file):
                log.info(f"Skipping Google Drive folder {format_folder_for_log(file['id'], file.get('name'))}")
                remove_folder_subtree_from_cache(cache, file['id'])
                continue
            add_folder_to_cache(cache, file)
            scan_folder_tree(service, file['id'], cache, file.get('name'))
        elif file.get('mimeType') == Google.mime_types['pdf']:
            add_pdf_to_cache(cache, file)

def full_drive_discovery(service, root_id, root_url=None):
    log.info(f"Performing full Google Drive discovery from folder ID: {root_id}...")
    cache = create_google_drive_cache(root_id, root_url)

    root = get_file_metadata(service, root_id)
    if not root:
        raise RuntimeError(f"Could not read root folder metadata for {root_id}")
    add_folder_to_cache(cache, root)

    scan_folder_tree(service, root_id, cache, root.get('name'))
    cache['change_page_token'] = get_start_page_token(service, cache.get('drive_id'))
    cache['updated_at_utc'] = utc_timestamp()
    return cache

def remove_changed_item_from_cache(cache, file_id):
    if file_id in cache['folders']:
        remove_folder_subtree_from_cache(cache, file_id)
    cache['pdfs'].pop(file_id, None)

def apply_file_change_to_cache(service, cache, file):
    file_id = file['id']

    if file.get('trashed'):
        remove_changed_item_from_cache(cache, file_id)
        return

    mime_type = file.get('mimeType')

    if mime_type == Google.mime_types['folder']:
        if should_skip_drive_folder(file):
            log.info(f"Skipping Google Drive folder {format_folder_for_log(file_id, file.get('name'))}")
            remove_folder_subtree_from_cache(cache, file_id)
            return

        was_tracked = file_id in cache['folders']
        is_root = file_id == cache['root_id']
        is_in_tree = is_root or cache_contains_parent(cache, file)

        if is_in_tree:
            add_folder_to_cache(cache, file)
            if not was_tracked:
                scan_folder_tree(service, file_id, cache, file.get('name'))
        elif was_tracked:
            remove_folder_subtree_from_cache(cache, file_id)
        return

    if mime_type == Google.mime_types['pdf']:
        if cache_contains_parent(cache, file):
            add_pdf_to_cache(cache, file)
        else:
            cache['pdfs'].pop(file_id, None)
        return

    cache['pdfs'].pop(file_id, None)

def list_drive_changes_page(service, page_token, drive_id=None):
    kwargs = {
        'pageToken': page_token,
        'fields': f"newStartPageToken,nextPageToken,changes(fileId,removed,file({DRIVE_FILE_FIELDS}))",
        'pageSize': 1000,
        'spaces': 'drive',
        'supportsAllDrives': True,
        'includeItemsFromAllDrives': True,
    }
    if drive_id:
        kwargs['driveId'] = drive_id

    httpref = service.changes().list(**kwargs)
    return Google.call_api(httpref, log)

def refresh_google_drive_cache(service, cache):
    page_token = cache.get('change_page_token')
    if not page_token:
        log.info("Google Drive cache has no change token; full discovery is required.")
        return None

    changes_seen = 0
    log.info("Refreshing Google Drive cache from Drive change log...")

    while page_token:
        try:
            results = list_drive_changes_page(service, page_token, cache.get('drive_id'))
        except HttpError as e:
            if e.resp.status == 410:
                log.info("Google Drive change token expired; full discovery is required.")
                return None
            raise

        if not results:
            return None

        for change in results.get('changes', []):
            changes_seen += 1
            file_id = change.get('fileId')
            if not file_id:
                continue

            if change.get('removed'):
                remove_changed_item_from_cache(cache, file_id)
                continue

            file = change.get('file')
            if file:
                apply_file_change_to_cache(service, cache, file)
            else:
                remove_changed_item_from_cache(cache, file_id)

        page_token = results.get('nextPageToken')
        if results.get('newStartPageToken'):
            cache['change_page_token'] = results['newStartPageToken']

    prune_cache_to_root(cache)
    cache['updated_at_utc'] = utc_timestamp()
    log.info(f"Applied {changes_seen} Google Drive changes from change log.")
    return cache

def get_found_pdfs_from_cache(cache):
    return list(cache.get('pdfs', {}).values())

def sort_pdfs_for_analysis(pdfs):
    return sorted(
        pdfs,
        key=lambda pdf: ((pdf.get('name') or '').casefold(), pdf.get('id') or '')
    )

@retry.Retry(predicate=Google.retry_errors)
def download_file(service, file_id, file_name):
    try:
        httpref = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, httpref)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        fh.seek(0)

        local_path = f"/tmp/{file_id}.pdf"
        with open(local_path, "wb") as f:
            f.write(fh.read())
        return local_path
    except Exception as e:
        log.error(f"Error downloading file {file_id} ({file_name}): {e}")
        return None

def build_openai_response_body(openai_file_id, lyrics_mode=LYRICS_MODE_VERBATIM_FIRST):
    if lyrics_mode == LYRICS_MODE_SUMMARY_ONLY:
        prompt = SCORE_ANALYSIS_SUMMARY_ONLY_PROMPT
    else:
        prompt = SCORE_ANALYSIS_PROMPT

    return {
        "model": args.model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": openai_file_id,
                        "detail": args.pdf_detail,
                    },
                    {"type": "input_text", "text": prompt},
                ]
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "score_analysis",
                "description": "Analysis result for a possible musical score PDF.",
                "schema": SCORE_ANALYSIS_SCHEMA,
                "strict": True,
            }
        },
    }

def extract_response_output_text(response_body):
    if not isinstance(response_body, dict):
        return None

    output_text = response_body.get("output_text")
    if isinstance(output_text, str):
        return output_text

    parts = []
    for output in response_body.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") in ("output_text", "text"):
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)

    if parts:
        return "\n".join(parts)
    return None

def get_openai_file_text(client, file_id):
    response = client.files.content(file_id)
    text = getattr(response, "text", None)
    if callable(text):
        return text()
    if isinstance(text, str):
        return text

    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content.decode("utf-8")
    if isinstance(content, str):
        return content

    return str(response)

def analyze_pdf(client, file_path):
    if not file_path:
        return None

    # Rate limiting retry logic
    max_retries = 10
    retry_delay = 30

    for attempt in range(max_retries):
        openai_file = None
        try:
            log.info(f"Uploading {file_path} to OpenAI...")
            with open(file_path, "rb") as f:
                openai_file = client.files.create(
                    file=f,
                    purpose="user_data"
                )

            response = client.responses.create(**build_openai_response_body(openai_file.id))

            # Extract JSON from response
            data = json.loads(response.output_text)
            return data

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit_exceeded" in err_str:
                log.warning(f"OpenAI API rate limit exceeded. Retrying in {retry_delay}s... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 1.5
                continue
            else:
                log.error(f"Error analyzing PDF with OpenAI: {e}")
                return None
        finally:
            if openai_file:
                try:
                    client.files.delete(openai_file.id)
                except Exception as e:
                    log.warning(f"Could not delete OpenAI file {openai_file.id}: {e}")

    log.error(f"Failed to analyze {file_path} after {max_retries} attempts due to rate limiting.")
    return None

def get_lyrics_type(data):
    lyrics_type = data.get('lyrics_type')
    if lyrics_type in ('verbatim', 'summary', 'none'):
        return lyrics_type
    if data.get('lyrics'):
        return 'verbatim'
    if data.get('lyrics_summary'):
        return 'summary'
    return 'none'

def sanitize_markdown_text(value):
    if value is None:
        return ""
    text = str(value)
    return "".join(
        char
        for char in text
        if char in ("\n", "\r", "\t") or not unicodedata.category(char).startswith("C")
    )

def normalize_multiline_text(text):
    return sanitize_markdown_text(text).replace("\r\n", "\n").replace("\r", "\n").strip()

def split_text_stanzas(text):
    stanzas = []
    current_stanza = []

    for line in normalize_multiline_text(text).split("\n"):
        stripped = line.strip()
        if not stripped:
            if current_stanza:
                stanzas.append(current_stanza)
                current_stanza = []
            continue
        current_stanza.append(stripped)

    if current_stanza:
        stanzas.append(current_stanza)

    return stanzas

def format_markdown_lyrics(lyrics):
    stanzas = split_text_stanzas(lyrics)
    if not stanzas:
        return ""

    formatted_stanzas = []
    for stanza in stanzas:
        # Two trailing spaces force Markdown renderers to keep each lyric line
        # as a visible line break while blank lines separate stanzas.
        formatted_stanzas.append("\n".join(f"{line}  " for line in stanza))

    return "\n\n".join(formatted_stanzas)

def generate_markdown(songs, output_file):
    sorted_titles = sorted(songs.keys())

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Musician Score Index\n\n")
        for title in sorted_titles:
            song = songs[title]
            f.write(f"## {one_line_markdown_text(title)}\n\n")

            if song.get('lyrics'):
                heading = "Lyrics" if song.get('lyrics_type') == 'verbatim' else "Lyric Summary"
                f.write(f"### {heading}\n")
                if song.get('lyrics_type') == 'verbatim':
                    f.write(f"{format_markdown_lyrics(song['lyrics'])}\n\n")
                else:
                    f.write(f"{normalize_multiline_text(song['lyrics'])}\n\n")
            elif song.get('lyrics_summary'):
                f.write("### Lyric Summary\n")
                f.write(f"{normalize_multiline_text(song['lyrics_summary'])}\n\n")

            f.write("### Metadata\n")
            f.write(f"- **Composer:** {one_line_markdown_text(song.get('composer'))}\n")
            f.write(f"- **Date:** {one_line_markdown_text(song.get('publication_date'))}\n")
            f.write(f"- **Publisher:** {one_line_markdown_text(song.get('publisher'))}\n\n")

            if song.get('musician_notes'):
                f.write("### Musician Notes\n")
                f.write(f"{normalize_multiline_text(song['musician_notes'])}\n\n")

            f.write("### Arrangements & Variations\n")
            folder_groups = {}
            for arr in song['arrangements']:
                # Extract folder ID from link
                match = re.search(r'folders/([a-zA-Z0-9_-]+)', arr['folder_link'])
                folder_id = match.group(1) if match else arr['folder_link']
                if folder_id not in folder_groups:
                    folder_groups[folder_id] = []
                folder_groups[folder_id].append(arr)

            for folder_id, arrs in folder_groups.items():
                if len(arrs) > 1:
                    f.write(f"- **Folder:** {markdown_link('Link to Folder', arrs[0]['folder_link'])}\n")
                    for arr in arrs:
                        f.write(f"  - {one_line_markdown_text(arr['description'])}: {markdown_link('PDF Link', arr['file_link'])}\n")
                else:
                    arr = arrs[0]
                    f.write(
                        f"- {one_line_markdown_text(arr['description'])}: "
                        f"{markdown_link('PDF Link', arr['file_link'])} "
                        f"(in {markdown_link('folder', arr['folder_link'])})\n"
                    )
            f.write("\n---\n\n")

def one_line_markdown_text(value):
    if value is None:
        return "Unknown"
    text = sanitize_markdown_text(value).replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()
    return text or "Unknown"

def markdown_link(label, url):
    if not url:
        return "Unknown"
    return f"[{one_line_markdown_text(label)}]({sanitize_markdown_url(url)})"

def markdown_json(value):
    if value is None:
        return "None"
    return sanitize_markdown_text(json.dumps(value, indent=2, sort_keys=True, default=str))

def markdown_table_text(value):
    text = one_line_markdown_text(value)
    return text.replace("|", "\\|")

def sanitize_markdown_url(url):
    return sanitize_markdown_text(url).strip().replace(" ", "%20")

def lyrics_mode_or_default(record):
    return record.get('lyrics_mode') or LYRICS_MODE_VERBATIM_FIRST

def get_file_error_history(batch_state, drive_file_id):
    history = batch_state.get('file_error_history', {}).get(drive_file_id, [])
    return sorted(
        history,
        key=lambda entry: (
            entry.get('completed_at_utc') or '',
            entry.get('submitted_at_utc') or '',
            entry.get('custom_id') or '',
        )
    )

def count_file_error_history(history):
    counts = {}
    for entry in history:
        key = entry.get('error_key') or analysis_error_key(entry.get('error'))
        counts[key] = counts.get(key, 0) + 1
    return counts

def format_error_counts(counts):
    if not counts:
        return "None"
    return ", ".join(f"{key}: {counts[key]}" for key in sorted(counts))

def collect_failure_records(batch_state):
    failures = []
    current_files = batch_state.get('files', {})
    for batch_id, batch_record in sorted(batch_state.get('batches', {}).items()):
        for request in batch_record.get('requests', {}).values():
            status = request.get('status')
            if status not in FAILURE_REPORT_STATUSES:
                continue
            current_record = current_files.get(request.get('drive_file_id'))
            if current_record and current_record.get('custom_id') != request.get('custom_id'):
                continue

            record = dict(request)
            record['batch_id'] = request.get('batch_id') or batch_id
            record['batch_status'] = batch_record.get('status')
            record['batch_submitted_at_utc'] = batch_record.get('submitted_at_utc')
            record['batch_collected_at_utc'] = batch_record.get('collected_at_utc')
            record['request_counts'] = batch_record.get('request_counts')
            failures.append(record)

    return sorted(
        failures,
        key=lambda record: (
            record.get('status') or '',
            (record.get('pdf_name') or '').casefold(),
            record.get('drive_file_id') or '',
        )
    )

def generate_failures_markdown(batch_state, output_file):
    failures = collect_failure_records(batch_state)
    failed_drive_file_ids = {
        failure.get('drive_file_id')
        for failure in failures
        if failure.get('drive_file_id')
    }
    failed_song_names = {
        os.path.splitext(failure.get('pdf_name') or '')[0].strip()
        for failure in failures
        if failure.get('pdf_name')
    }
    status_counts = {}
    for failure in failures:
        status = failure.get('status') or 'unknown'
        status_counts[status] = status_counts.get(status, 0) + 1

    log.info(f"Generating batch failure report: {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# OpenAI Batch Analysis Failures\n\n")
        f.write(f"Generated: {local_timestamp(utc_timestamp())}\n\n")
        f.write(f"Total failures: {len(failures)}\n\n")
        f.write(f"Total affected PDFs: {len(failed_drive_file_ids)}\n\n")
        f.write(f"Total affected song/PDF names: {len(failed_song_names)}\n\n")

        if status_counts:
            f.write("## Summary\n\n")
            for status in sorted(status_counts):
                f.write(f"- **{status}:** {status_counts[status]}\n")
            f.write("\n")

        if not failures:
            f.write("No batch analysis failures are recorded in local state.\n")
            return

        f.write("## Details\n\n")
        for index, failure in enumerate(failures, start=1):
            pdf_name = one_line_markdown_text(failure.get('pdf_name'))
            drive_file_id = one_line_markdown_text(failure.get('drive_file_id'))
            f.write(f"### {index}. {pdf_name}\n\n")
            f.write(f"- **Status:** {one_line_markdown_text(failure.get('status'))}\n")
            f.write(f"- **Batch ID:** `{one_line_markdown_text(failure.get('batch_id'))}`\n")
            f.write(f"- **Batch status:** {one_line_markdown_text(failure.get('batch_status'))}\n")
            f.write(f"- **Custom ID:** `{one_line_markdown_text(failure.get('custom_id'))}`\n")
            f.write(f"- **Drive file ID:** `{drive_file_id}`\n")
            f.write(f"- **PDF:** {markdown_link(pdf_name, failure.get('file_link'))}\n")
            f.write(f"- **Folder:** {markdown_link('Folder', failure.get('folder_link'))}\n")
            f.write(f"- **Model:** {one_line_markdown_text(failure.get('model'))}\n")
            f.write(f"- **PDF detail:** {one_line_markdown_text(failure.get('pdf_detail'))}\n")
            f.write(f"- **Lyrics mode:** {one_line_markdown_text(lyrics_mode_or_default(failure))}\n")
            f.write(f"- **Drive modified:** {local_timestamp_or_unknown(failure.get('drive_modified_time_utc'))}\n")
            f.write(f"- **Submitted:** {local_timestamp_or_unknown(failure.get('submitted_at_utc'))}\n")
            f.write(f"- **Completed:** {local_timestamp_or_unknown(failure.get('completed_at_utc'))}\n")
            f.write(f"- **Batch collected:** {local_timestamp_or_unknown(failure.get('batch_collected_at_utc'))}\n")
            if failure.get('request_counts'):
                f.write(f"- **Batch request counts:** `{one_line_markdown_text(failure.get('request_counts'))}`\n")
            error_history = get_file_error_history(batch_state, failure.get('drive_file_id'))
            error_counts = count_file_error_history(error_history)
            f.write(f"- **Failed response count for this PDF:** {len(error_history)}\n")
            f.write(f"- **Failed response counts:** {one_line_markdown_text(format_error_counts(error_counts))}\n")
            f.write("\n")
            if error_history:
                f.write("#### Failed Response History\n\n")
                f.write("| # | Completed | Status | Lyrics mode | Error | Message | Batch ID | Custom ID |\n")
                f.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
                for history_index, entry in enumerate(error_history, start=1):
                    error_key = entry.get('error_key') or analysis_error_key(entry.get('error'))
                    message = entry.get('message') or error_message(entry.get('error'))
                    f.write(
                        f"| {history_index} "
                        f"| {markdown_table_text(local_timestamp_or_unknown(entry.get('completed_at_utc')))} "
                        f"| {markdown_table_text(entry.get('status'))} "
                        f"| {markdown_table_text(lyrics_mode_or_default(entry))} "
                        f"| {markdown_table_text(error_key)} "
                        f"| {markdown_table_text(message)} "
                        f"| `{markdown_table_text(entry.get('batch_id'))}` "
                        f"| `{markdown_table_text(entry.get('custom_id'))}` |\n"
                    )
                f.write("\n")
            f.write("#### Current Error Payload\n\n")
            f.write("```json\n")
            f.write(markdown_json(failure.get('error')))
            f.write("\n```\n\n")

def add_analysis_to_songs(songs, pdf, data):
    if not data or data.get("is_score") is False:
        return False

    title = (data.get('song_title') or pdf['name']).strip()
    norm_title = title.title()
    lyrics_type = get_lyrics_type(data)

    if norm_title not in songs:
        songs[norm_title] = {
            'lyrics': data.get('lyrics'),
            'lyrics_summary': data.get('lyrics_summary'),
            'lyrics_type': lyrics_type,
            'composer': data.get('composer'),
            'publication_date': data.get('publication_date'),
            'publisher': data.get('publisher'),
            'musician_notes': data.get('musician_notes'),
            'arrangements': []
        }

    if data.get('lyrics') and songs[norm_title].get('lyrics_type') != 'verbatim':
        songs[norm_title]['lyrics'] = data.get('lyrics')
        songs[norm_title]['lyrics_summary'] = None
        songs[norm_title]['lyrics_type'] = 'verbatim'
    elif (
        not songs[norm_title].get('lyrics')
        and not songs[norm_title].get('lyrics_summary')
        and data.get('lyrics_summary')
    ):
        songs[norm_title]['lyrics_summary'] = data.get('lyrics_summary')
        songs[norm_title]['lyrics_type'] = 'summary'

    songs[norm_title]['arrangements'].append({
        'description': data.get('arrangement_description') or pdf['name'],
        'file_link': pdf['webViewLink'],
        'folder_link': pdf['parentFolderLink']
    })
    return True

def save_google_drive_cache(cache, cache_file):
    cache['schema_version'] = DISCOVERY_CACHE_VERSION
    cache['updated_at_utc'] = utc_timestamp()
    log.info(
        f"Saving Google Drive cache to {cache_file} "
        f"({len(cache.get('folders', {}))} folders, {len(cache.get('pdfs', {}))} PDFs)..."
    )

    cache_dir = os.path.dirname(os.path.abspath(cache_file))
    os.makedirs(cache_dir, exist_ok=True)
    tmp_cache_file = f"{cache_file}.tmp"
    with open(tmp_cache_file, 'w') as f:
        json.dump(cache, f, indent=2, sort_keys=True)
    os.replace(tmp_cache_file, cache_file)

def load_google_drive_cache(cache_file):
    log.info(f"Loading Google Drive cache from {cache_file}...")
    with open(cache_file, 'r') as f:
        cache = json.load(f)

    if not isinstance(cache, dict):
        raise ValueError("Google Drive cache must be a JSON object")
    if cache.get('schema_version') != DISCOVERY_CACHE_VERSION:
        raise ValueError(
            f"Unsupported Google Drive cache schema version: {cache.get('schema_version')}"
        )
    return cache

def get_cached_analysis(file_id, state_dir):
    cache_path = os.path.join(state_dir, f"{file_id}.json")
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            data = json.load(f)
        if normalize_analysis_timestamp(data):
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
        return data
    return None

def get_error_object(error):
    if not isinstance(error, dict):
        return {}
    body = error.get('body')
    if isinstance(body, dict) and isinstance(body.get('error'), dict):
        return body['error']
    return error

def error_code(error):
    obj = get_error_object(error)
    return obj.get('code') if isinstance(obj, dict) else None

def error_message(error):
    obj = get_error_object(error)
    if isinstance(obj, dict):
        return obj.get('message') or obj.get('details')
    return str(error) if error is not None else None

def error_status_code(error):
    if isinstance(error, dict):
        return error.get('status_code')
    return None

def incomplete_response_reason(error):
    details = error.get('incomplete_details') if isinstance(error, dict) else None
    return details.get('reason') if isinstance(details, dict) else None

def is_content_filter_incomplete_error(error):
    return incomplete_response_reason(error) == 'content_filter'

def is_retryable_incomplete_response(error):
    return incomplete_response_reason(error) in ('content_filter', 'max_output_tokens')

def analysis_error_key(error):
    reason = incomplete_response_reason(error)
    if reason:
        return f"incomplete:{reason}"

    code = error_code(error)
    if code:
        return f"openai:{code}"

    message = error_message(error) or ''
    if 'Could not parse model JSON output' in message:
        return 'local:parse_error'
    if 'No output text found' in message:
        return 'local:missing_output_text'

    status_code = error_status_code(error)
    if status_code:
        return f"http:{status_code}"

    return 'unknown'

def analysis_error_summary(error):
    return {
        'error_key': analysis_error_key(error),
        'status_code': error_status_code(error),
        'error_code': error_code(error),
        'incomplete_reason': incomplete_response_reason(error),
        'message': error_message(error),
    }

def analysis_error_filter_values(error):
    values = {analysis_error_key(error).casefold()}

    code = error_code(error)
    if code:
        values.add(str(code).casefold())

    reason = incomplete_response_reason(error)
    if reason:
        values.add(str(reason).casefold())

    status_code = error_status_code(error)
    if status_code is not None:
        values.add(str(status_code).casefold())

    return values

def error_matches_retry_filter(error):
    if not args.retry_analysis_error_codes:
        return True
    if not error:
        return False
    return bool(args.retry_analysis_error_codes & analysis_error_filter_values(error))

def is_retryable_analysis_error(error):
    code = error_code(error)
    message = error_message(error) or ''
    status_code = error_status_code(error)

    if is_retryable_incomplete_response(error):
        return True
    if status_code == 429 or code == 'rate_limit_exceeded':
        return True
    if code in ('server_error', 'temporarily_unavailable'):
        return True
    if 'Could not parse model JSON output' in message:
        return True
    if 'No output text found' in message:
        return True
    return False

def cached_analysis_blocks_resubmission(cached_data):
    analysis_status = cached_data.get('analysis_status')
    analysis_error = cached_data.get('analysis_error')

    if analysis_status in ('failed', 'retryable_error'):
        return False
    if analysis_error and is_retryable_analysis_error(analysis_error):
        return False
    return True

def is_cached_analysis_fresh(cached_data, pdf, match_analysis_strategy=True):
    if not cached_data:
        return False
    if not cached_analysis_blocks_resubmission(cached_data):
        return False

    if match_analysis_strategy:
        cached_model = cached_data.get('analysis_model')
        if cached_model and cached_model != args.model:
            return False

        cached_pdf_detail = cached_data.get('pdf_detail')
        if cached_pdf_detail and cached_pdf_detail != args.pdf_detail:
            return False

    drive_mod_time_utc = get_pdf_modified_time_utc(pdf)
    if not drive_mod_time_utc:
        raise ValueError("PDF metadata does not include modified_time_utc")

    source_mod_time_utc = cached_data.get('source_modified_time_utc')
    if source_mod_time_utc:
        return utc_timestamp(source_mod_time_utc) == drive_mod_time_utc

    cached_at_utc = cached_data.get('cached_at_utc')
    if not cached_at_utc:
        return False

    return parse_timestamp(cached_at_utc) >= parse_timestamp(drive_mod_time_utc)

def cached_analysis_reanalysis_reason(cached_data, pdf):
    if not cached_data:
        return "No cached analysis found."

    analysis_status = cached_data.get('analysis_status')
    analysis_error = cached_data.get('analysis_error')
    if analysis_status in ('failed', 'retryable_error'):
        return f"Cached analysis status is {analysis_status}."
    if analysis_error and is_retryable_analysis_error(analysis_error):
        return f"Cached analysis error is retryable ({analysis_error_key(analysis_error)})."

    cached_model = cached_data.get('analysis_model')
    if cached_model and cached_model != args.model:
        return f"Cached analysis used model {cached_model}; requested model is {args.model}."

    cached_pdf_detail = cached_data.get('pdf_detail')
    if cached_pdf_detail and cached_pdf_detail != args.pdf_detail:
        return f"Cached analysis used PDF detail {cached_pdf_detail}; requested PDF detail is {args.pdf_detail}."

    drive_mod_time_utc = get_pdf_modified_time_utc(pdf)
    source_mod_time_utc = cached_data.get('source_modified_time_utc')
    if source_mod_time_utc and drive_mod_time_utc:
        return (
            "Cache source modified timestamp differs from Drive file "
            f"(cached source {local_timestamp_or_unknown(source_mod_time_utc)}; "
            f"Drive modified {local_timestamp_or_unknown(drive_mod_time_utc)})."
        )

    cached_at_utc = cached_data.get('cached_at_utc')
    if not cached_at_utc:
        return "Cached analysis has no cached_at_utc timestamp."

    return (
        "Cache is older than Drive file "
        f"(cached {local_timestamp_or_unknown(cached_at_utc)}; "
        f"Drive modified {local_timestamp_or_unknown(drive_mod_time_utc)})."
    )

def save_cached_analysis(file_id, data, state_dir, pdf=None):
    if not os.path.exists(state_dir):
        os.makedirs(state_dir)

    cache_path = os.path.join(state_dir, f"{file_id}.json")
    data['cached_at_utc'] = utc_timestamp()
    data.pop('cached_at', None)
    if pdf:
        source_modified_time_utc = get_pdf_modified_time_utc(pdf)
        if source_modified_time_utc:
            data['source_modified_time_utc'] = source_modified_time_utc
    data['analysis_model'] = args.model
    data['pdf_detail'] = args.pdf_detail
    with open(cache_path, 'w') as f:
        json.dump(data, f, indent=2)

def save_failed_analysis(file_id, error, state_dir, pdf, status):
    data = {
        'is_score': False,
        'song_title': None,
        'lyrics': None,
        'lyrics_summary': None,
        'lyrics_type': None,
        'arrangement_description': None,
        'composer': None,
        'publication_date': None,
        'publisher': None,
        'musician_notes': None,
        'analysis_status': status,
        'analysis_error': error,
    }
    save_cached_analysis(file_id, data, state_dir, pdf)

def build_songs_from_cached_analysis(found_pdfs):
    songs = {}
    for pdf in found_pdfs:
        file_id = pdf['id']
        cached_data = get_cached_analysis(file_id, args.state_dir)
        if not cached_data:
            continue
        try:
            if not is_cached_analysis_fresh(cached_data, pdf):
                log.info(f"Skipping stale cached analysis for {pdf['name']} ({file_id})")
                continue
        except Exception as e:
            log.warning(f"Skipping cached analysis for {pdf['name']} ({file_id}): {e}")
            continue
        add_analysis_to_songs(songs, pdf, cached_data)
    return songs

def get_batch_state_path(state_dir):
    return os.path.join(state_dir, BATCH_STATE_FILENAME)

def create_batch_state():
    return {
        'schema_version': BATCH_STATE_VERSION,
        'generated_at_utc': utc_timestamp(),
        'updated_at_utc': utc_timestamp(),
        'files': {},
        'file_error_history': {},
        'batches': {},
    }

def build_file_error_history_entry(request, status, error):
    entry = {
        'drive_file_id': request.get('drive_file_id'),
        'drive_modified_time_utc': request.get('drive_modified_time_utc'),
        'pdf_name': request.get('pdf_name'),
        'file_link': request.get('file_link'),
        'folder_link': request.get('folder_link'),
        'model': request.get('model'),
        'pdf_detail': request.get('pdf_detail'),
        'lyrics_mode': request.get('lyrics_mode') or LYRICS_MODE_VERBATIM_FIRST,
        'batch_id': request.get('batch_id'),
        'custom_id': request.get('custom_id'),
        'status': status,
        'submitted_at_utc': request.get('submitted_at_utc'),
        'completed_at_utc': request.get('completed_at_utc'),
        'recorded_at_utc': utc_timestamp(),
        'error': error,
    }
    entry.update(analysis_error_summary(error))
    return entry

def record_file_error_history(batch_state, request, status, error):
    if not error or status not in FAILURE_REPORT_STATUSES:
        return False

    drive_file_id = request.get('drive_file_id')
    custom_id = request.get('custom_id')
    if not drive_file_id or not custom_id:
        return False

    histories = batch_state.setdefault('file_error_history', {})
    history = histories.setdefault(drive_file_id, [])
    entry = build_file_error_history_entry(request, status, error)

    for index, existing in enumerate(history):
        if existing.get('custom_id') == custom_id:
            entry['recorded_at_utc'] = existing.get('recorded_at_utc') or entry['recorded_at_utc']
            if existing == entry:
                return False
            history[index] = entry
            return True

    history.append(entry)
    history.sort(key=lambda item: (item.get('completed_at_utc') or '', item.get('custom_id') or ''))
    return True

def normalize_batch_state_statuses(state):
    changed = False

    for batch_record in state.get('batches', {}).values():
        for request in batch_record.get('requests', {}).values():
            if (
                request.get('status') in ('failed', 'permanent_error')
                and request.get('error')
                and is_retryable_analysis_error(request.get('error'))
            ):
                request['status'] = 'retryable_error'
                changed = True

                current_record = state.get('files', {}).get(request.get('drive_file_id'))
                if current_record and current_record.get('custom_id') == request.get('custom_id'):
                    current_record['status'] = 'retryable_error'

    return changed

def rebuild_file_error_history_from_requests(state):
    changed = False
    state.setdefault('file_error_history', {})

    for batch_id, batch_record in state.get('batches', {}).items():
        for request in batch_record.get('requests', {}).values():
            status = request.get('status')
            error = request.get('error')
            if status not in FAILURE_REPORT_STATUSES or not error:
                continue
            if not request.get('batch_id'):
                request['batch_id'] = batch_id
            if record_file_error_history(state, request, status, error):
                changed = True

    return changed

def load_batch_state(state_dir):
    state_path = get_batch_state_path(state_dir)
    if not os.path.exists(state_path):
        return create_batch_state()

    log.info(f"Loading OpenAI batch state from {state_path}...")
    with open(state_path, 'r') as f:
        state = json.load(f)

    if not isinstance(state, dict):
        raise ValueError("OpenAI batch state must be a JSON object")
    if state.get('schema_version') != BATCH_STATE_VERSION:
        raise ValueError(
            f"Unsupported OpenAI batch state schema version: {state.get('schema_version')}"
        )

    state.setdefault('files', {})
    state.setdefault('file_error_history', {})
    state.setdefault('batches', {})
    changed = False
    if normalize_batch_state_statuses(state):
        log.info("Normalized retryable statuses in OpenAI batch state.")
        changed = True
    if rebuild_file_error_history_from_requests(state):
        log.info("Updated OpenAI batch error history from recorded requests.")
        changed = True
    if changed:
        save_batch_state(state, state_dir)
    return state

def save_batch_state(state, state_dir):
    os.makedirs(state_dir, exist_ok=True)
    state['schema_version'] = BATCH_STATE_VERSION
    state['updated_at_utc'] = utc_timestamp()
    state_path = get_batch_state_path(state_dir)
    tmp_state_path = f"{state_path}.tmp"
    with open(tmp_state_path, 'w') as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp_state_path, state_path)

def compact_utc_timestamp_for_filename():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def get_object_value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def serialize_openai_value(value):
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value

def get_openai_client():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        log.error("Error: OPENAI_API_KEY environment variable not set.")
        return None
    return OpenAI(api_key=api_key)

def get_drive_service(phase_label):
    apis = {
        'drive' : { 'scope'       : Google.scopes['drive'],
                    'api_name'    : 'drive',
                    'api_version' : 'v3', },
    }
    try:
        services = GoogleAuth.service_oauth_login(apis,
                                                  app_json=args.app_id,
                                                  user_json=args.user_credentials,
                                                  log=log)
        return services['drive']
    except Exception as e:
        log.error(f"Authentication failed for {phase_label}: {e}")
        return None

def pdf_state_snapshot(pdf):
    return {
        'drive_file_id': pdf['id'],
        'drive_modified_time_utc': get_pdf_modified_time_utc(pdf),
        'pdf_name': pdf.get('name'),
        'file_link': pdf.get('webViewLink'),
        'folder_link': pdf.get('parentFolderLink'),
        'model': args.model,
        'pdf_detail': args.pdf_detail,
    }

def pdf_from_batch_request(request):
    return {
        'id': request.get('drive_file_id'),
        'name': request.get('pdf_name'),
        'webViewLink': request.get('file_link'),
        'parentFolderLink': request.get('folder_link'),
        'modified_time_utc': request.get('drive_modified_time_utc'),
    }

def batch_file_record_matches_pdf(record, pdf):
    if not record:
        return False
    if record.get('drive_modified_time_utc') != get_pdf_modified_time_utc(pdf):
        return False
    if record.get('model') != args.model:
        return False
    if record.get('pdf_detail') != args.pdf_detail:
        return False
    return True

def batch_file_record_source_matches_pdf(record, pdf):
    if not record:
        return False
    return record.get('drive_modified_time_utc') == get_pdf_modified_time_utc(pdf)

def batch_file_record_should_skip_submission(record, pdf):
    if not batch_file_record_matches_pdf(record, pdf):
        return False
    if record.get('error') and is_retryable_analysis_error(record.get('error')):
        return False
    return record.get('status') in BATCH_SKIP_FILE_STATUSES

def iter_batch_error_records_for_pdf(batch_state, pdf):
    file_id = pdf['id']
    seen_custom_ids = set()

    current_record = batch_state.get('files', {}).get(file_id)
    if current_record and batch_file_record_source_matches_pdf(current_record, pdf):
        seen_custom_ids.add(current_record.get('custom_id'))
        yield current_record

    for record in batch_state.get('file_error_history', {}).get(file_id, []):
        if not batch_file_record_source_matches_pdf(record, pdf):
            continue
        custom_id = record.get('custom_id')
        if custom_id in seen_custom_ids:
            continue
        seen_custom_ids.add(custom_id)
        yield record

    for batch_record in batch_state.get('batches', {}).values():
        for request in batch_record.get('requests', {}).values():
            if request.get('drive_file_id') != file_id:
                continue
            if not batch_file_record_source_matches_pdf(request, pdf):
                continue
            custom_id = request.get('custom_id')
            if custom_id in seen_custom_ids:
                continue
            seen_custom_ids.add(custom_id)
            yield request

def pdf_matches_retry_error_filter(pdf, cached_data, batch_state):
    if not args.retry_analysis_error_codes:
        return True

    if cached_data and error_matches_retry_filter(cached_data.get('analysis_error')):
        return True

    for record in iter_batch_error_records_for_pdf(batch_state, pdf):
        if error_matches_retry_filter(record.get('error')):
            return True

    return False

def get_lyrics_mode_for_batch_submission(batch_state, pdf):
    for record in iter_batch_error_records_for_pdf(batch_state, pdf):
        if record.get('lyrics_mode') == LYRICS_MODE_SUMMARY_ONLY:
            return LYRICS_MODE_SUMMARY_ONLY
        if is_content_filter_incomplete_error(record.get('error')):
            return LYRICS_MODE_SUMMARY_ONLY

    return LYRICS_MODE_VERBATIM_FIRST

def choose_pdfs_for_batch_submission(found_pdfs, batch_state):
    candidates = []
    skipped_cached = 0
    skipped_submitted = 0
    skipped_answered = 0
    skipped_retry_filter = 0

    for pdf in found_pdfs:
        file_id = pdf['id']
        cached_data = get_cached_analysis(file_id, args.state_dir)
        if cached_data:
            try:
                if is_cached_analysis_fresh(cached_data, pdf):
                    skipped_cached += 1
                    continue
            except Exception as e:
                log.warning(f"Could not evaluate cached analysis for {pdf['name']} ({file_id}): {e}")

        if not pdf_matches_retry_error_filter(pdf, cached_data, batch_state):
            skipped_retry_filter += 1
            continue

        file_record = batch_state.get('files', {}).get(file_id)
        if batch_file_record_should_skip_submission(file_record, pdf):
            if file_record.get('status') == 'submitted':
                skipped_submitted += 1
            else:
                skipped_answered += 1
            continue

        candidates.append(pdf)

    log.info(
        f"Batch submission candidates: {len(candidates)} "
        f"(fresh cache: {skipped_cached}; already submitted: {skipped_submitted}; "
        f"already answered: {skipped_answered}; "
        f"retry filter: {skipped_retry_filter})"
    )
    return candidates

def get_uncollected_analysis_batches(batch_state):
    return [
        batch_record
        for batch_record in batch_state.get('batches', {}).values()
        if not batch_record.get('collected_at_utc')
    ]

def delete_openai_file(client, file_id, description):
    if not file_id:
        return True
    try:
        client.files.delete(file_id)
        return True
    except Exception as e:
        log.warning(f"Could not delete OpenAI {description} file {file_id}: {e}")
        return False

def delete_uploaded_pdf_for_request(client, batch_state, request):
    if request.get('openai_file_deleted_at_utc'):
        return
    openai_file_id = request.get('openai_file_id')
    if delete_openai_file(client, openai_file_id, "PDF"):
        updates = {'openai_file_deleted_at_utc': utc_timestamp()}
        request.update(updates)
        update_current_file_record_from_request(batch_state, request, updates)

def update_current_file_record_from_request(batch_state, request, updates):
    drive_file_id = request.get('drive_file_id')
    current_record = batch_state.get('files', {}).get(drive_file_id)
    if not current_record:
        return
    if current_record.get('custom_id') != request.get('custom_id'):
        return
    current_record.update(updates)

def mark_batch_request(batch_state, request, status, error=None):
    updates = {
        'status': status,
        'completed_at_utc': utc_timestamp(),
    }
    if error:
        updates['error'] = error
    else:
        request.pop('error', None)

    request.update(updates)
    update_current_file_record_from_request(batch_state, request, updates)
    record_file_error_history(batch_state, request, status, error)

def write_batch_input_file(requests):
    batch_input_dir = os.path.join(args.state_dir, BATCH_INPUT_DIRNAME)
    os.makedirs(batch_input_dir, exist_ok=True)
    filename = f"{compact_utc_timestamp_for_filename()}-{uuid.uuid4().hex[:8]}-analysis.jsonl"
    path = os.path.join(batch_input_dir, filename)

    with open(path, 'w') as f:
        for request in requests:
            f.write(json.dumps(request, separators=(',', ':')))
            f.write("\n")

    return path

def submit_analysis_batch(client, service, found_pdfs):
    try:
        batch_state = load_batch_state(args.state_dir)
    except Exception as e:
        log.error(f"Could not load OpenAI batch state: {e}")
        return False

    uncollected_batches = get_uncollected_analysis_batches(batch_state)
    if uncollected_batches and not args.allow_concurrent_analysis_batches:
        batch_ids = ', '.join(
            batch_record.get('batch_id') or '<unknown>'
            for batch_record in uncollected_batches
        )
        log.warning(
            "Not submitting a new OpenAI batch because previous batches are not collected: "
            f"{batch_ids}. Run --collect-analysis-batch first, or use "
            "--allow-concurrent-analysis-batches."
        )
        return True

    candidates = choose_pdfs_for_batch_submission(found_pdfs, batch_state)
    if not candidates:
        log.info("No PDFs need batch submission.")
        return True
    if len(candidates) > args.analysis_batch_size:
        log.info(
            f"Limiting this OpenAI batch submission to {args.analysis_batch_size} "
            f"of {len(candidates)} outstanding PDFs."
        )
        candidates = candidates[:args.analysis_batch_size]

    submitted_at_utc = utc_timestamp()
    batch_requests = []
    file_records = []
    batch_input_file = None
    created_batch_id = None

    for analysis_index, pdf in enumerate(candidates, start=1):
        file_id = pdf['id']
        lyrics_mode = get_lyrics_mode_for_batch_submission(batch_state, pdf)
        log.info(
            f"Preparing batch request ({analysis_index} of {len(candidates)}): "
            f"{pdf['name']} ({file_id}); lyrics mode: {lyrics_mode}..."
        )
        local_path = None
        openai_file = None
        try:
            local_path = download_file(service, file_id, pdf['name'])
            if not local_path:
                log.warning(f"Skipping {pdf['name']} ({file_id}); download failed.")
                continue

            log.info(f"Uploading {local_path} to OpenAI for batch analysis...")
            with open(local_path, "rb") as f:
                openai_file = client.files.create(
                    file=f,
                    purpose="user_data"
                )

            custom_id = f"{file_id}-{uuid.uuid4().hex[:8]}"
            file_record = pdf_state_snapshot(pdf)
            file_record.update({
                'custom_id': custom_id,
                'openai_file_id': openai_file.id,
                'status': 'submitted',
                'submitted_at_utc': submitted_at_utc,
                'lyrics_mode': lyrics_mode,
            })
            file_records.append(file_record)
            batch_requests.append({
                'custom_id': custom_id,
                'method': 'POST',
                'url': BATCH_ENDPOINT,
                'body': build_openai_response_body(openai_file.id, lyrics_mode),
            })
        except Exception as e:
            log.error(f"Could not prepare batch request for {pdf['name']} ({file_id}): {e}")
            if openai_file:
                delete_openai_file(client, openai_file.id, "PDF")
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)

    if not batch_requests:
        log.info("No batch requests were prepared successfully.")
        return False

    try:
        batch_input_path = write_batch_input_file(batch_requests)
        log.info(f"Uploading OpenAI batch input file {batch_input_path}...")
        with open(batch_input_path, "rb") as f:
            batch_input_file = client.files.create(
                file=f,
                purpose="batch"
            )

        log.info(f"Submitting OpenAI batch with {len(batch_requests)} requests...")
        batch = client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint=BATCH_ENDPOINT,
            completion_window=BATCH_COMPLETION_WINDOW,
            metadata={
                'source': 'index_scores.py',
                'model': args.model,
                'pdf_detail': args.pdf_detail,
            },
        )

        batch_id = get_object_value(batch, 'id')
        if not batch_id:
            raise RuntimeError("OpenAI batch creation did not return a batch id")
        created_batch_id = batch_id
        batch_status = get_object_value(batch, 'status')
        request_map = {}
        for file_record in file_records:
            file_record['batch_id'] = batch_id
            batch_state['files'][file_record['drive_file_id']] = dict(file_record)
            request_map[file_record['custom_id']] = dict(file_record)

        batch_state['batches'][batch_id] = {
            'batch_id': batch_id,
            'input_file_id': batch_input_file.id,
            'endpoint': BATCH_ENDPOINT,
            'completion_window': BATCH_COMPLETION_WINDOW,
            'status': batch_status,
            'submitted_at_utc': submitted_at_utc,
            'model': args.model,
            'pdf_detail': args.pdf_detail,
            'request_count': len(batch_requests),
            'requests': request_map,
        }
        save_batch_state(batch_state, args.state_dir)
        log.info(
            f"Submitted OpenAI batch {batch_id} with {len(batch_requests)} requests. "
            "Run again with --collect-analysis-batch to retrieve completed results."
        )
        return True
    except Exception as e:
        log.error(f"Could not submit OpenAI batch: {e}")
        if created_batch_id:
            log.error(
                f"OpenAI batch {created_batch_id} may have been created, so uploaded files were left in place."
            )
        else:
            for file_record in file_records:
                delete_openai_file(client, file_record.get('openai_file_id'), "PDF")
            if batch_input_file:
                delete_openai_file(client, batch_input_file.id, "batch input")
        return False

def iter_jsonl(text):
    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            yield line_number, json.loads(line)
        except Exception as e:
            log.warning(f"Could not parse JSONL line {line_number}: {e}")

def result_line_error(result):
    error = result.get('error')
    if error:
        return error

    response = result.get('response') or {}
    status_code = response.get('status_code')
    try:
        numeric_status_code = int(status_code) if status_code is not None else None
    except Exception:
        numeric_status_code = None
    if numeric_status_code and numeric_status_code >= 400:
        return {
            'status_code': status_code,
            'body': response.get('body'),
        }

    return None

def incomplete_response_error(response_body):
    if not isinstance(response_body, dict):
        return None
    if response_body.get('status') != 'incomplete':
        return None

    return {
        'message': 'OpenAI response was incomplete',
        'response_status': response_body.get('status'),
        'incomplete_details': response_body.get('incomplete_details'),
    }

def mark_retryable_batch_request(batch_state, request, error):
    mark_batch_request(batch_state, request, 'retryable_error', error)

def process_batch_result_line(client, batch_state, batch_record, pdf_by_id, result):
    custom_id = result.get('custom_id')
    if not custom_id:
        log.warning("Batch result is missing custom_id; skipping.")
        return

    request = batch_record.get('requests', {}).get(custom_id)
    if not request:
        log.warning(f"Batch result custom_id {custom_id} was not found in local batch state; skipping.")
        return

    drive_file_id = request.get('drive_file_id')
    current_pdf = pdf_by_id.get(drive_file_id)
    if current_pdf:
        current_mod_time_utc = get_pdf_modified_time_utc(current_pdf)
        if request.get('drive_modified_time_utc') != current_mod_time_utc:
            log.info(
                f"Batch result for {request.get('pdf_name')} ({drive_file_id}) is stale "
                f"(submitted Drive modified {local_timestamp_or_unknown(request.get('drive_modified_time_utc'))}; "
                f"current Drive modified {local_timestamp_or_unknown(current_mod_time_utc)})."
            )
            mark_batch_request(batch_state, request, 'stale')
            delete_uploaded_pdf_for_request(client, batch_state, request)
            return
        cache_pdf = current_pdf
    else:
        cache_pdf = pdf_from_batch_request(request)

    error = result_line_error(result)
    if error:
        log.warning(f"Batch request failed for {request.get('pdf_name')} ({drive_file_id}): {error}")
        if is_retryable_analysis_error(error):
            mark_retryable_batch_request(batch_state, request, error)
        else:
            save_failed_analysis(drive_file_id, error, args.state_dir, cache_pdf, 'permanent_error')
            mark_batch_request(batch_state, request, 'permanent_error', error)
        delete_uploaded_pdf_for_request(client, batch_state, request)
        return

    response = result.get('response') or {}
    body = response.get('body')
    incomplete_error = incomplete_response_error(body)
    if incomplete_error:
        log.warning(
            f"Batch response incomplete for {request.get('pdf_name')} ({drive_file_id}): "
            f"{incomplete_error}"
        )
        if is_retryable_incomplete_response(incomplete_error):
            mark_retryable_batch_request(batch_state, request, incomplete_error)
        else:
            save_failed_analysis(drive_file_id, incomplete_error, args.state_dir, cache_pdf, 'failed')
            mark_batch_request(batch_state, request, 'failed', incomplete_error)
        delete_uploaded_pdf_for_request(client, batch_state, request)
        return

    output_text = extract_response_output_text(body)
    if not output_text:
        error = {'message': 'No output text found in OpenAI batch response'}
        log.warning(f"Batch request returned no output text for {request.get('pdf_name')} ({drive_file_id})")
        mark_retryable_batch_request(batch_state, request, error)
        delete_uploaded_pdf_for_request(client, batch_state, request)
        return

    try:
        data = json.loads(output_text)
    except Exception as e:
        error = {
            'message': 'Could not parse model JSON output',
            'details': str(e),
        }
        log.warning(f"Could not parse model output for {request.get('pdf_name')} ({drive_file_id}): {e}")
        mark_retryable_batch_request(batch_state, request, error)
        delete_uploaded_pdf_for_request(client, batch_state, request)
        return

    save_cached_analysis(drive_file_id, data, args.state_dir, cache_pdf)
    status = 'not_score' if data.get('is_score') is False else 'completed'
    mark_batch_request(batch_state, request, status)
    delete_uploaded_pdf_for_request(client, batch_state, request)

def mark_unfinished_batch_requests(client, batch_state, batch_record, status):
    for request in batch_record.get('requests', {}).values():
        if request.get('status') in ('completed', 'not_score', 'permanent_error', 'failed', 'stale'):
            continue
        mark_batch_request(batch_state, request, status, {'message': f'Batch ended with status {status}'})
        delete_uploaded_pdf_for_request(client, batch_state, request)

def update_batch_record_from_openai(batch_record, batch):
    batch_record['status'] = get_object_value(batch, 'status')
    batch_record['output_file_id'] = get_object_value(batch, 'output_file_id')
    batch_record['error_file_id'] = get_object_value(batch, 'error_file_id')
    request_counts = serialize_openai_value(get_object_value(batch, 'request_counts'))
    if request_counts is not None:
        batch_record['request_counts'] = request_counts
    usage = serialize_openai_value(get_object_value(batch, 'usage'))
    if usage is not None:
        batch_record['usage'] = usage

def collect_analysis_batches(client, found_pdfs):
    try:
        batch_state = load_batch_state(args.state_dir)
    except Exception as e:
        log.error(f"Could not load OpenAI batch state: {e}")
        return None

    if not batch_state.get('batches'):
        log.info("No OpenAI batches are recorded in local state.")
        generate_failures_markdown(batch_state, args.failures_output)
        return build_songs_from_cached_analysis(found_pdfs)

    pdf_by_id = {pdf['id']: pdf for pdf in found_pdfs}
    for batch_id, batch_record in sorted(batch_state.get('batches', {}).items()):
        if batch_record.get('collected_at_utc'):
            log.info(f"OpenAI batch {batch_id} was already collected at {local_timestamp_or_unknown(batch_record['collected_at_utc'])}.")
            continue

        try:
            log.info(f"Checking OpenAI batch {batch_id}...")
            batch = client.batches.retrieve(batch_id)
            update_batch_record_from_openai(batch_record, batch)
        except Exception as e:
            log.error(f"Could not retrieve OpenAI batch {batch_id}: {e}")
            continue

        status = batch_record.get('status')
        request_counts = batch_record.get('request_counts')
        if request_counts:
            log.info(f"OpenAI batch {batch_id} status: {status}; request counts: {request_counts}")
        else:
            log.info(f"OpenAI batch {batch_id} status: {status}")

        output_file_id = batch_record.get('output_file_id')
        error_file_id = batch_record.get('error_file_id')

        if status not in BATCH_TERMINAL_STATUSES:
            continue

        processing_failed = False
        if output_file_id:
            try:
                output_text = get_openai_file_text(client, output_file_id)
                for _, result in iter_jsonl(output_text):
                    process_batch_result_line(client, batch_state, batch_record, pdf_by_id, result)
            except Exception as e:
                processing_failed = True
                log.error(f"Could not process output file for OpenAI batch {batch_id}: {e}")

        if error_file_id:
            try:
                error_text = get_openai_file_text(client, error_file_id)
                for _, result in iter_jsonl(error_text):
                    process_batch_result_line(client, batch_state, batch_record, pdf_by_id, result)
            except Exception as e:
                processing_failed = True
                log.error(f"Could not process error file for OpenAI batch {batch_id}: {e}")

        if processing_failed:
            log.warning(f"OpenAI batch {batch_id} was not marked collected; retry collection later.")
            save_batch_state(batch_state, args.state_dir)
            continue

        if status != 'completed':
            mark_unfinished_batch_requests(client, batch_state, batch_record, status)
        elif not output_file_id:
            mark_unfinished_batch_requests(client, batch_state, batch_record, 'failed')

        batch_record['collected_at_utc'] = utc_timestamp()
        save_batch_state(batch_state, args.state_dir)

    save_batch_state(batch_state, args.state_dir)
    generate_failures_markdown(batch_state, args.failures_output)
    return build_songs_from_cached_analysis(found_pdfs)

def main():
    global args, log
    args = setup_cli_args()

    log = ECC.setup_logging(info=args.verbose,
                            debug=args.debug,
                            logfile=args.logfile, rotate=True)

    found_pdfs = []

    # Step 1: Google Drive File Discovery
    if not args.skip_discovery:
        if not args.google_drive_root_url:
            log.error("Error: --google-drive-root-url is required for discovery (unless --skip-discovery is used).")
            return

        apis = {
            'drive' : { 'scope'       : Google.scopes['drive'],
                        'api_name'    : 'drive',
                        'api_version' : 'v3', },
        }

        try:
            services = GoogleAuth.service_oauth_login(apis,
                                                      app_json=args.app_id,
                                                      user_json=args.user_credentials,
                                                      log=log)
            service = services['drive']
        except Exception as e:
            log.error(f"Authentication failed: {e}")
            return

        root_id = extract_folder_id(args.google_drive_root_url)
        cache = None
        if os.path.exists(args.google_drive_cache):
            try:
                cache = load_google_drive_cache(args.google_drive_cache)
                if cache.get('root_id') != root_id:
                    log.info(
                        "Existing Google Drive cache is for a different root folder; "
                        "performing full discovery."
                    )
                    cache = None
            except Exception as e:
                log.warning(f"Could not use Google Drive cache {args.google_drive_cache}: {e}")

        if cache:
            cache = refresh_google_drive_cache(service, cache)

        if not cache:
            cache = full_drive_discovery(service, root_id, args.google_drive_root_url)

        save_google_drive_cache(cache, args.google_drive_cache)
        found_pdfs = get_found_pdfs_from_cache(cache)
    else:
        if not os.path.exists(args.google_drive_cache):
            log.error(f"Error: Google Drive cache file {args.google_drive_cache} not found. Cannot skip discovery.")
            return
        try:
            cache = load_google_drive_cache(args.google_drive_cache)
        except Exception as e:
            log.error(f"Error: Could not load Google Drive cache file {args.google_drive_cache}: {e}")
            return
        found_pdfs = get_found_pdfs_from_cache(cache)

    found_pdfs = sort_pdfs_for_analysis(found_pdfs)
    if args.limit and len(found_pdfs) > args.limit:
        log.info(f"Limiting analysis to the first {args.limit} PDFs from cache (original count: {len(found_pdfs)})")
        found_pdfs = found_pdfs[:args.limit]

    # Step 2: Metadata / Lyrics Extraction
    if not args.skip_analysis:
        client = get_openai_client()
        if not client:
            return

        if args.submit_analysis_batch:
            service = get_drive_service("batch submission")
            if not service:
                return
            if not submit_analysis_batch(client, service, found_pdfs):
                return
            log.info("Done!")
            return

        if args.collect_analysis_batch:
            log.info("Collecting OpenAI batch analysis results...")
            songs = collect_analysis_batches(client, found_pdfs)
            if songs is None:
                return
            log.info(f"Generating markdown: {args.output}...")
            generate_markdown(songs, args.output)
            log.info("Done!")
            return

        # Synchronous analysis needs the drive service to download the files.
        service = get_drive_service("analysis phase")
        if not service:
            return

        retry_filter_batch_state = create_batch_state()
        if args.retry_analysis_error_codes:
            try:
                retry_filter_batch_state = load_batch_state(args.state_dir)
            except Exception as e:
                log.error(f"Could not load OpenAI batch state for --retry-analysis-error-codes: {e}")
                return

        log.info(f"Starting analysis of {len(found_pdfs)} PDFs...")
        songs = {}
        skipped_retry_filter = 0

        for analysis_index, pdf in enumerate(found_pdfs, start=1):
            file_id = pdf['id']
            log.info(f"Processing ({analysis_index} of {len(found_pdfs)}): {pdf['name']} ({file_id})...")

            # Check local persistent cache
            cached_data = get_cached_analysis(file_id, args.state_dir)
            use_cache = False
            data = None

            if args.retry_analysis_error_codes and not pdf_matches_retry_error_filter(
                pdf,
                cached_data,
                retry_filter_batch_state,
            ):
                skipped_retry_filter += 1
                if cached_data:
                    try:
                        if is_cached_analysis_fresh(cached_data, pdf, match_analysis_strategy=False):
                            add_analysis_to_songs(songs, pdf, cached_data)
                    except Exception as e:
                        log.warning(f"  Skipping cached analysis for {file_id}: {e}")
                continue

            if cached_data:
                try:
                    drive_mod_time_utc = get_pdf_modified_time_utc(pdf)
                    if is_cached_analysis_fresh(cached_data, pdf):
                        log.info(
                            "  Using cached analysis results "
                            f"(cached {local_timestamp_or_unknown(cached_data.get('cached_at_utc'))}; "
                            f"Drive modified {local_timestamp_or_unknown(drive_mod_time_utc)})"
                        )
                        use_cache = True
                        data = cached_data
                    else:
                        log.info(
                            "  Re-analyzing because "
                            f"{cached_analysis_reanalysis_reason(cached_data, pdf)}"
                        )
                except Exception as e:
                    log.warning(f"  Error comparing timestamps for {file_id}: {e}")

            if not use_cache:
                local_path = download_file(service, file_id, pdf['name'])
                data = analyze_pdf(client, local_path)
                if local_path and os.path.exists(local_path):
                    os.remove(local_path)

                if data is not None:
                    # Save to persistent cache
                    save_cached_analysis(file_id, data, args.state_dir, pdf)

            add_analysis_to_songs(songs, pdf, data)

        if args.retry_analysis_error_codes:
            log.info(
                f"Skipped {skipped_retry_filter} PDFs that did not match "
                "--retry-analysis-error-codes."
            )

        log.info(f"Generating markdown: {args.output}...")
        generate_markdown(songs, args.output)

    log.info("Done!")

if __name__ == '__main__':
    main()
