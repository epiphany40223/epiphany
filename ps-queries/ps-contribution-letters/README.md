# ps-contribution-letters

This script splits a master PDF of contribution letters into individual PDFs, matches them to families via ParishSoft envelope numbers, and then emails the letters to each family.

## Gmail SMTP auth (Google Workspace)

This tool uses **OAuth2 / XOAUTH2** to authenticate to Gmail SMTP, intended for Google Workspace domains.

### One-time setup checklist

You will do these steps once per environment/domain.

#### 1) Create a Google Cloud service account

1. Open Google Cloud Console: `https://console.cloud.google.com/`
2. Select (or create) the project you want to use.
3. Go to: **IAM & Admin** → **Service Accounts**
4. Click **Create service account**
5. Enter:
   - **Service account name** (e.g., `ecc-contribution-mailer`)
   - (Optional) description
6. Click **Create and continue**
7. Role grants:
   - For SMTP/XOAUTH2, the service account typically does not need any special GCP project roles.
   - If your org policy forces a role, grant the minimal allowed role.
8. Click **Done**

#### 2) Enable Domain-Wide Delegation on the service account

1. In Google Cloud Console: **IAM & Admin** → **Service Accounts**
2. Click your service account (e.g., `...@...iam.gserviceaccount.com`)
3. Click the **Details** tab
4. Find **Domain-wide delegation**
5. Click **Show domain-wide delegation** (if needed)
6. Check **Enable Google Workspace Domain-wide Delegation**
7. (Recommended) Set **Product name for the consent screen** (e.g., `ECC Contribution Letters`)
8. Click **Save**
9. Copy the service account’s **Client ID** (sometimes shown as “Unique ID” / “Client ID”). You will paste this into the Admin console.

#### 3) Create/download a JSON key for the service account

1. Google Cloud Console: **IAM & Admin** → **Service Accounts**
2. Click the service account
3. Go to the **Keys** tab
4. Click **Add key** → **Create new key**
5. Select **JSON** → **Create**
6. Store the downloaded JSON file securely (it is effectively a password).

#### 4) Authorize the service account in Google Workspace Admin (API Controls)

1. Open Google Workspace Admin: `https://admin.google.com/`
2. Go to: **Security** → **Access and data control** → **API controls**
   - If you don’t see **Security**, open the left menu (≡) and find it there.
3. Under **Domain wide delegation**, click **Manage Domain Wide Delegation**
4. Click **Add new**
5. Paste the service account **Client ID** from step 2.9
6. In **OAuth scopes**, enter:
   - `https://mail.google.com/`
7. Click **Authorize**

#### 5) Create the Workspace user to impersonate (must be a real mailbox)

The script authenticates as the service account and then *impersonates a Workspace user*.

- By default, it impersonates the address in `--smtp-from`.
- You can override this with `--gmail-impersonate-user`.

These two are not redundant: the impersonated user must be a real mailbox user, but the `From:` header can be an alias of that mailbox.

`--smtp-from` can be either:

- a bare email: `no-reply@your_domain.org`
- or a full name-addr: `Epiphany Catholic Church <no-reply@your_domain.org>`

If `--gmail-impersonate-user` is not specified, the script impersonates the **email portion** of `--smtp-from`.

Important:
- The impersonated identity must be an actual Google Workspace **User** with a Gmail mailbox (i.e., a real account).
- A Google Group address (e.g., a distribution list) is **not** a valid impersonation target for Gmail SMTP in this flow.

Create a dedicated “mailer” user:

1. Admin console: **Directory** → **Users**
2. Click **Add new user**
3. Create something like:
   - Primary email: `mailer@your_domain.org`
   - Name: `ECC Mailer` (or similar)
4. Ensure the user has a license that includes Gmail (so it has a mailbox).

If you want to send *as* `no-reply@your_domain.org`:

Option A (recommended): add `no-reply@your_domain.org` as an alias on the mailbox user
1. Admin console: **Directory** → **Users** → click `mailer@your_domain.org`
2. Go to **User information** (or **Account**; the exact label varies)
3. Find **Email aliases** → **Add alternate email**
4. Add `no-reply@your_domain.org`
5. In the script, impersonate `mailer@your_domain.org` and set `--smtp-from no-reply@your_domain.org`.

Making Gmail show `From: no-reply@your_domain.org` (instead of rewriting it)

If you impersonate `mailer@your_domain.org` but set `--smtp-from no-reply@your_domain.org`, you might see headers like:

- `X-Google-Original-From: no-reply@your_domain.org`
- `From: mailer@your_domain.org`

This means Gmail accepted your requested From address, but rewrote the visible `From:` because `no-reply@...` is not an allowed “send as” identity for the impersonated mailbox.

To fix it, configure the impersonated mailbox user to be allowed to send as that alias:

1. Sign in to Gmail as the impersonated user (e.g., `mailer@your_domain.org`).
2. Gmail → Settings (gear) → **See all settings** → **Accounts and Import**.
3. In **Send mail as**, add/enable `no-reply@your_domain.org`.
4. If Gmail asks to verify ownership, complete the verification flow.
5. (Optional) Set `no-reply@your_domain.org` as the default “Send mail as” identity.

Option B: make `no-reply@your_domain.org` the primary address
- Create the user with primary email `no-reply@your_domain.org`.
- This is simpler, but some orgs prefer not to have “no-reply” as a primary user.

Notes:
- Default SMTP server is `smtp.gmail.com`.
- `smtp-relay.gmail.com` is a different service and may not support XOAUTH2.

## Install

From this directory:

- `python3 -m pip install -r requirements.txt`

## Run

Example (real send):

- `./ps-contribution-letters.py --year 2025 --input OfferingContributionDetailsFamilyExportReport.pdf --ps-api-keyfile parishsoft-api-key.txt --gmail-service-account-keyfile service-account.json --smtp-from "Epiphany Catholic Church <no-reply@epiphanycatholicchurch.org>"`

Example (send as alias, impersonate mailbox user):

- `./ps-contribution-letters.py --year 2025 --input OfferingContributionDetailsFamilyExportReport.pdf --ps-api-keyfile parishsoft-api-key.txt --gmail-service-account-keyfile service-account.json --gmail-impersonate-user mailer@your_domain.org --smtp-from no-reply@your_domain.org`

Example (test-run override):

- `./ps-contribution-letters.py --year 2025 --input OfferingContributionDetailsFamilyExportReport.pdf --ps-api-keyfile parishsoft-api-key.txt --gmail-service-account-keyfile service-account.json --smtp-from no-reply@epiphanycatholicchurch.org --test-run you@example.com 10`

`--test-run EMAIL COUNT` sends each email to `EMAIL` instead of the intended recipients, and stops processing after sending `COUNT` emails.

Example (no send):

- `./ps-contribution-letters.py --year 2025 --input OfferingContributionDetailsFamilyExportReport.pdf --ps-api-keyfile parishsoft-api-key.txt --do-not-send`

If you need STARTTLS (usually port 587):

- `./ps-contribution-letters.py ... --smtp-starttls --smtp-port 587`

If you need SMTP protocol debug output (useful for troubleshooting auth/relay issues):

- `./ps-contribution-letters.py ... --smtp-debug`
