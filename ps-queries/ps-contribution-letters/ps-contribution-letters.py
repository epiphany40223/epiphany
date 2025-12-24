#!/usr/bin/env python3

import os
import sys
import csv
import json
import re
import argparse
import shutil
import glob
from pathlib import Path
from pypdf import PdfReader, PdfWriter
import pdfplumber

# We assume that there is a "ecc-python-modules" sym link in this
# directory that points to the directory with ECC.py and friends.
moddir = os.path.join(os.getcwd(), 'ecc-python-modules')
if not os.path.exists(moddir):
    print("ERROR: Could not find the ecc-python-modules directory.")
    print("ERROR: Please make a ecc-python-modules sym link and run again.")
    exit(1)

sys.path.insert(0, moddir)

import ECC
import ParishSoftv2 as ParishSoft

def extract_info(pdf_path):
    """
    Extract the Family Envelope Number and Name from the first page of a PDF letter.
    Returns a tuple (envelope_number, name).
    """
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        text = first_page.extract_text()

        # Split text into lines
        lines = text.split('\n')

        envelope_num = None
        name = None

        # Find the line before the address (which should contain the envelope number)
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check for envelope number line
            match = re.match(r'^(\d+)\s+Date Printed:', stripped)
            if match:
                envelope_num = int(match.group(1))

                # The name should be on the next line
                if i + 1 < len(lines):
                    name = lines[i+1].strip()
                break

    return envelope_num, name

def sanitize_filename(name):
    """Sanitize a string to be safe for filenames."""
    # Remove invalid characters
    s = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces with underscores
    s = s.replace(' ', '_')
    return s

def split_pdf_into_letters(input_pdf_path, output_folder, log):
    """
    Split a master PDF into individual letter PDFs.

    Uses "Page x of y" footer to determine letter boundaries.

    Returns a dictionary mapping Family Envelope Number to filename.
    """
    # Create output folder if it doesn't exist
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    # Read the input PDF
    reader = PdfReader(input_pdf_path)

    # Dictionary to store the mapping
    family_mapping = {}

    # Track pages for current letter
    current_letter_pages = []
    current_page_count = 0
    total_pages_in_letter = 0

    def save_letter(pages):
        """Helper to save a list of pages as a PDF."""
        # Create a temporary writer to extract info
        temp_writer = PdfWriter()
        temp_writer.add_page(pages[0])

        # We need to save to a temp file to use pdfplumber for extraction
        # or we could try to extract text directly from pypdf page object
        # Let's use a temp file approach for consistency with existing extraction logic
        temp_filename = output_path / "temp_extract.pdf"
        with open(temp_filename, 'wb') as f:
            temp_writer.write(f)

        envelope_num, name = extract_info(temp_filename)

        # Clean up temp file
        if temp_filename.exists():
            os.remove(temp_filename)

        if name:
            safe_name = sanitize_filename(name)
            # Include envelope number to help ensure uniqueness
            if envelope_num:
                filename = f"{envelope_num}_{safe_name}.pdf"
            else:
                filename = f"{safe_name}.pdf"
        else:
            # Fallback if name not found
            filename = f"letter_unknown_{len(family_mapping)}.pdf"

        filepath = output_path / filename

        # Ensure filename is unique - add counter if file exists
        counter = 1
        while filepath.exists():
            if name:
                safe_name = sanitize_filename(name)
                if envelope_num:
                    filename = f"{envelope_num}_{safe_name}_{counter}.pdf"
                else:
                    filename = f"{safe_name}_{counter}.pdf"
            else:
                filename = f"letter_unknown_{len(family_mapping)}_{counter}.pdf"
            filepath = output_path / filename
            counter += 1

        # Write the full letter
        writer = PdfWriter()
        for p in pages:
            writer.add_page(p)

        with open(filepath, 'wb') as f:
            writer.write(f)

        if envelope_num:
            log.info(f"Parsed letter for envelope {envelope_num}: {filename}")
        else:
            log.warning(f"Parsed letter but could not extract envelope number: {filename}")

        return filename, envelope_num, name

    # Process each page
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text() or ""

        # Look for "Page X of Y" pattern
        # It usually appears at the bottom
        page_match = re.search(r'Page\s+(\d+)\s+of\s+(\d+)', text)

        if page_match:
            current_page_num = int(page_match.group(1))
            total_pages = int(page_match.group(2))

            if current_page_num == 1:
                # Start of a new letter
                # If we have a previous letter pending (which shouldn't happen if logic is correct,
                # but good for safety), save it
                if current_letter_pages:
                    # This case implies we missed the end of the previous letter
                    # or the previous letter didn't have a proper "Page X of Y" on its last page
                    # For now, let's just reset and start fresh, assuming the previous one was saved
                    # or this is a recovery.
                    # But actually, if we hit Page 1, we should definitely start a new accumulation
                    current_letter_pages = []

                current_letter_pages.append(page)
                total_pages_in_letter = total_pages

                # If it's a 1-page letter, save immediately
                if total_pages == 1:
                    filename, envelope_num, name = save_letter(current_letter_pages)
                    if envelope_num:
                        family_mapping[envelope_num] = {
                            'filename': filename,
                            'salutation': name
                        }
                    current_letter_pages = []
                    total_pages_in_letter = 0
            else:
                # Continuation of current letter
                current_letter_pages.append(page)

                # Check if we've reached the last page
                if current_page_num == total_pages:
                    filename, envelope_num, name = save_letter(current_letter_pages)
                    if envelope_num:
                        family_mapping[envelope_num] = {
                            'filename': filename,
                            'salutation': name
                        }
                    current_letter_pages = []
                    total_pages_in_letter = 0
        else:
            # Fallback: if we can't find the page number, but we have pages accumulating
            # This might happen if the footer is missing or unreadable.
            # We'll assume it belongs to the current letter if we are in one.
            if current_letter_pages:
                current_letter_pages.append(page)
                # If we don't know the total pages, we might be in trouble.
                # But usually the "Page X of Y" is reliable.
                pass

    # Handle any remaining pages (if last letter didn't end properly)
    if current_letter_pages:
        filename, envelope_num, name = save_letter(current_letter_pages)
        if envelope_num:
            family_mapping[envelope_num] = {
                'filename': filename,
                'salutation': name
            }

    return family_mapping

def cleanup_tmpdir(tmpdir_path, log):
    """Clean up temporary directory by removing all PDF files."""
    tmpdir = Path(tmpdir_path)
    if tmpdir.exists():
        log.info(f"Cleaning temporary directory: {tmpdir_path}")
        # Remove all PDF files in the temp directory
        for pdf_file in tmpdir.glob('*.pdf'):
            try:
                pdf_file.unlink()
                log.debug(f"Removed: {pdf_file}")
            except Exception as e:
                log.warning(f"Could not remove {pdf_file}: {e}")
    else:
        log.info(f"Creating temporary directory: {tmpdir_path}")
        tmpdir.mkdir(parents=True, exist_ok=True)

def enrich_family_mapping(family_mapping, families, member_workgroups, log):
    """Enrich family mapping with email addresses from ParishSoft data."""
    log.info("Enriching mapping with email addresses...")

    # Create a lookup for families by envelope number
    families_by_envelope = {}
    for family in families.values():
        if 'envelopeNumber' in family and family['envelopeNumber']:
            try:
                env_num = int(family['envelopeNumber'])
                families_by_envelope[env_num] = family
            except ValueError:
                pass

    enriched_mapping = {}
    for env_num, data in family_mapping.items():
        filename = data['filename']
        salutation = data['salutation']

        family_data = {
            'filename': filename,
            'salutation': salutation,
            'emails': []
        }

        if env_num in families_by_envelope:
            family = families_by_envelope[env_num]
            emails = ParishSoft.family_business_logistics_emails(family, member_workgroups, log)
            family_data['emails'] = emails
        else:
            log.warning(f"Could not find family with envelope number {env_num} in ParishSoft data")

        enriched_mapping[env_num] = family_data

    return enriched_mapping, families_by_envelope

def send_contribution_letters(enriched_mapping, families_by_envelope, args,
                              output_folder, emailed_folder, snail_mail_folder,
                              smtp, log):
    """Send contribution letters via email or move to snail mail folder."""
    emails_sent = 0
    no_email_count = 0
    snail_mail_families = []
    test_run_sent_count = 0

    for env_num, data in enriched_mapping.items():
        filename = data['filename']
        salutation = data['salutation']
        emails = data['emails']
        pdf_path = Path(output_folder) / filename

        if not pdf_path.exists():
            log.warning(f"PDF file not found: {pdf_path}")
            continue

        if len(emails) == 0:
            log.info(f"No email addresses for {salutation} (envelope {env_num}) - will need snail mail")

            # Collect family data for CSV
            family_info = {
                'envelope_number': env_num,
                'salutation': salutation,
                'filename': filename,
            }

            # Add family data from ParishSoft if available
            if env_num in families_by_envelope:
                ps_family = families_by_envelope[env_num]
                family_info.update({
                    'fduid': ps_family.get('familyDUID', ''),
                    'family_name': f"{ps_family.get('firstName', '')} {ps_family.get('lastName', '')}".strip(),
                    'last_name': ps_family.get('lastName', ''),
                    'first_name': ps_family.get('firstName', ''),
                    'mailing_name': ps_family.get('mailingName', ''),
                    'address1': ps_family.get('primaryAddress1', ''),
                    'address2': ps_family.get('primaryAddress2', ''),
                    'address3': ps_family.get('primaryAddress3', ''),
                    'city': ps_family.get('primaryCity', ''),
                    'state': ps_family.get('primaryState', ''),
                    'zip': ps_family.get('primaryPostalCode', ''),
                    'zip_plus': ps_family.get('primaryZipPlus', ''),
                })
            else:
                family_info.update({
                    'fduid': '',
                    'family_name': '',
                    'last_name': '',
                    'first_name': '',
                    'mailing_name': '',
                    'address1': '',
                    'address2': '',
                    'address3': '',
                    'city': '',
                    'state': '',
                    'zip': '',
                    'zip_plus': '',
                })

            snail_mail_families.append(family_info)

            # Move to snail mail folder
            dest_path = snail_mail_folder / filename
            shutil.move(str(pdf_path), str(dest_path))
            no_email_count += 1
            continue

        # Prepare email
        smtp_to = ', '.join(emails)
        smtp_subject = f'{args.year} Contribution Letter from Epiphany Catholic Church'

        # Build email body
        body_parts = [
            f"Dear {salutation},",
            "",
            f"Attached is your {args.year} contribution letter from Epiphany Catholic Church.",
            "",
            "Thank you for your generous support of our parish.",
            "",
            "Sincerely,",
            "Epiphany Catholic Church"
        ]

        # Handle test run mode
        actual_recipients = smtp_to
        skip_sending = False

        if args.test_run:
            # Check if we've reached the test run limit
            if test_run_sent_count >= args.test_run_count:
                log.debug(f"TEST RUN: Skipping email to {actual_recipients} (already sent {test_run_sent_count} emails)")
                skip_sending = True
                # Move to emailed folder even though we're skipping
                dest_path = emailed_folder / filename
                shutil.move(str(pdf_path), str(dest_path))
                continue

            body_parts.insert(0, "*** THIS EMAIL WAS SENT TO A TEST RUN OVERRIDE ADDRESS ***")
            body_parts.insert(1, f"*** Intended recipients: {actual_recipients} ***")
            body_parts.insert(2, "")
            smtp_to = args.test_run_email
            log.info(f"TEST RUN: Sending to override address: {smtp_to} (intended: {actual_recipients})")
            test_run_sent_count += 1
        else:
            log.info(f"Sending to {smtp_to}")

        body = '\n'.join(body_parts)

        # Prepare attachment
        attachments = {
            1: {
                'filename': str(pdf_path),
                'type': 'pdf'
            }
        }

        # Send email (unless do-not-send)
        if args.do_not_send:
            log.info(f"NOT SENDING: Would send email to {smtp_to}")
            # Move to emailed folder even though we didn't send
            dest_path = emailed_folder / filename
            shutil.move(str(pdf_path), str(dest_path))
        else:
            try:
                ECC.send_email_existing_smtp(
                    body, 'text/plain',
                    smtp_to, smtp_subject, args.smtp_from,
                    smtp, log,
                    attachments=attachments
                )
                emails_sent += 1

                # Move to emailed folder
                dest_path = emailed_folder / filename
                shutil.move(str(pdf_path), str(dest_path))
                log.info(f"Successfully sent and moved to {dest_path}")
            except Exception as e:
                log.error(f"Failed to send email to {smtp_to}: {e}")

    return emails_sent, no_email_count, snail_mail_families

def write_snail_mail_csv(snail_mail_families, snail_mail_folder, log):
    """Write CSV file for families requiring snail mail."""
    if not snail_mail_families:
        return

    csv_filename = snail_mail_folder / 'snail-mail-families.csv'
    csv_fieldnames = [
        'envelope_number',
        'fduid',
        'salutation',
        'family_name',
        'last_name',
        'first_name',
        'mailing_name',
        'address1',
        'address2',
        'address3',
        'city',
        'state',
        'zip',
        'zip_plus',
        'filename',
    ]

    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames)
        writer.writeheader()
        for family_info in snail_mail_families:
            writer.writerow(family_info)

    log.info(f"Wrote snail mail family data to '{csv_filename}'")

def print_summary(enriched_mapping, emails_sent, no_email_count, args, log):
    """Print summary of processing."""
    log.info("")
    log.info("=== Summary ===")
    log.info(f"Total families processed: {len(enriched_mapping)}")
    if args.do_not_send:
        log.info(f"NOT SENDING: Would have sent {len([d for d in enriched_mapping.values() if len(d['emails']) > 0])} emails")
        log.info(f"NOT SENDING: Would have {no_email_count} families requiring snail mail")
    else:
        log.info(f"Emails sent: {emails_sent}")
        log.info(f"Families requiring snail mail: {no_email_count}")
        log.info(f"Letters moved to '{args.emailed_dir}': {emails_sent}")
        log.info(f"Letters moved to '{args.snail_mail_dir}': {no_email_count}")

def setup_cli():
    parser = argparse.ArgumentParser(description='Split contribution letters and map to families')
    parser.add_argument('--debug',
                        action='store_true',
                        default=False,
                        help='If enabled, emit even more extra status messages during run')
    parser.add_argument('--ps-api-keyfile',
                        default='parishsoft-api-key.txt',
                        help='File containing the ParishSoft API key')
    parser.add_argument('--ps-cache-dir',
                        default='ps-data',
                        help='Directory to cache the ParishSoft data')
    parser.add_argument('--ps-cache-limit',
                        default='1d',
                        help='Cache limit duration (e.g., 1d for 1 day)')
    parser.add_argument('--input',
                        required=True,
                        help='Input PDF file to process')
    parser.add_argument('--tmpdir',
                        default='individual-letters',
                        help='Temporary directory for individual letters')
    parser.add_argument('--smtp-auth-file',
                        help='File containing SMTP authentication credentials (username:password)')
    parser.add_argument('--smtp-server',
                        default='smtp-relay.gmail.com',
                        help='SMTP server hostname')
    parser.add_argument('--smtp-from',
                        default='no-reply@epiphanycatholicchurch.org',
                        help='From email address')
    parser.add_argument('--do-not-send',
                        action='store_true',
                        default=False,
                        help='Process everything but do not actually send emails')
    parser.add_argument('--test-run',
                        nargs=2,
                        metavar=('EMAIL', 'COUNT'),
                        help='Test mode: override email address and max number of emails to send')
    parser.add_argument('--year',
                        required=True,
                        help='Tax year for the contribution letters (e.g., 2024)')
    parser.add_argument('--emailed-dir',
                        default='letters-emailed',
                        help='Directory for successfully emailed letters')
    parser.add_argument('--snail-mail-dir',
                        default='letters-for-snail-mail',
                        help='Directory for letters requiring snail mail')

    args = parser.parse_args()

    # Check for mutually exclusive options
    if args.do_not_send and args.test_run:
        parser.error('--do-not-send and --test-run cannot be used together')

    # Parse test-run parameters if provided
    if args.test_run:
        args.test_run_email = args.test_run[0]
        try:
            args.test_run_count = int(args.test_run[1])
            if args.test_run_count < 0:
                parser.error('Test run count must be a non-negative integer')
        except ValueError:
            parser.error(f'Test run count must be an integer, got: {args.test_run[1]}')
    else:
        args.test_run_email = None
        args.test_run_count = None

    # SMTP auth file is only required if we're actually sending emails
    if not args.do_not_send and not args.smtp_auth_file:
        parser.error('--smtp-auth-file is required unless --do-not-send is specified')

    # Read the PS API key
    if not os.path.exists(args.ps_api_keyfile):
        print(f"ERROR: ParishSoft API keyfile does not exist: {args.ps_api_keyfile}")
        exit(1)
    with open(args.ps_api_keyfile) as fp:
        args.api_key = fp.read().strip()

    # Check SMTP auth file only if we're sending emails
    if not args.do_not_send:
        if not os.path.exists(args.smtp_auth_file):
            print(f"ERROR: SMTP auth file does not exist: {args.smtp_auth_file}")
            exit(1)

    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"ERROR: Input file '{args.input}' not found!")
        exit(1)

    return args

def main():
    """Main function to process the PDF and create individual letters."""
    args = setup_cli()
    log = ECC.setup_logging(debug=args.debug)

    # Clean up temporary directory at start
    cleanup_tmpdir(args.tmpdir, log)

    # Setup SMTP only if we're actually sending emails
    if args.smtp_auth_file:
        log.info("Setting up SMTP...")
        ECC.setup_email(smtp_auth_file=args.smtp_auth_file,
                       smtp_server=args.smtp_server,
                       log=log)

    log.info("Loading ParishSoft data...")
    families, members, family_workgroups, member_workgroups, ministries = \
        ParishSoft.load_families_and_members(api_key=args.api_key,
                                             cache_dir=args.ps_cache_dir,
                                             active_only=False,
                                             parishioners_only=False,
                                             load_contributions=False,
                                             cache_limit=args.ps_cache_limit,
                                             log=log)

    input_pdf = args.input
    output_folder = args.tmpdir
    mapping_file = "family-letter-mappings.json"

    log.info(f"Processing {input_pdf}...")

    # Split the PDF into individual letters
    family_mapping = split_pdf_into_letters(input_pdf, output_folder, log)
    log.info(f"Created {len(family_mapping)} individual letters in '{output_folder}' folder")

    # Enrich the mapping with email addresses
    enriched_mapping, families_by_envelope = enrich_family_mapping(
        family_mapping, families, member_workgroups, log)

    # Save the mapping to JSON file
    with open(mapping_file, 'w') as f:
        json.dump(enriched_mapping, f, indent=2, sort_keys=True)
    log.info(f"Saved family-to-letter mapping to '{mapping_file}'")
    log.info(f"Total families processed: {len(enriched_mapping)}")

    # Create output directories
    emailed_folder = Path(args.emailed_dir)
    snail_mail_folder = Path(args.snail_mail_dir)
    emailed_folder.mkdir(exist_ok=True)
    snail_mail_folder.mkdir(exist_ok=True)

    # Send emails
    log.info("Sending contribution letters via email...")

    # If we were not given SMTP auth file, we cannot proceed
    if not args.smtp_auth_file:
        log.info("Cannot proceed with sending emails without SMTP auth file.")
        return

    log.debug("Opening SMTP connection from main...")
    with ECC.open_smtp_connection(log=log) as smtp:
        log.debug("SMTP connection established")
        emails_sent, no_email_count, snail_mail_families = send_contribution_letters(
            enriched_mapping, families_by_envelope, args,
            output_folder, emailed_folder, snail_mail_folder,
            smtp, log)

    # Write CSV file for snail mail families
    write_snail_mail_csv(snail_mail_families, snail_mail_folder, log)

    # Print summary
    print_summary(enriched_mapping, emails_sent, no_email_count, args, log)

if __name__ == '__main__':
    main()