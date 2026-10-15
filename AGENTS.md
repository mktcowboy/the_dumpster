# Repository privacy

These rules apply to every contributor and assistant working with this repository, including ChatGPT and Codex.

- Keep the repository owner's identity and personal context out of files, filenames, generated artifacts, metadata, commit messages, and author/co-author fields. Do not copy names, usernames, email addresses, home-directory paths, or personal details from chats or account context.
- Use neutral descriptions such as "initial selections"; omit personal attribution. Preserve unrelated public-source citations and book authors.
- Before delivering or committing changes, run `python3 scripts/check_privacy.py`. Inspect rendered artifacts for personal information that a text scan cannot detect.
- In each fresh checkout, run `sh scripts/setup_privacy.sh` to install local checks and repository-only anonymous commit identity. Never bypass privacy hooks.
- For ChatGPT workflows that write through an API, read these instructions and run the same check before uploading. GitHub's privacy workflow provides an additional check after upload; it cannot prevent initial disclosure.
