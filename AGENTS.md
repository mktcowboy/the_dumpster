# Agent instructions

- Store output in `drops/YYYY-MM-DD/<agent>/<task>/`, using the current date and descriptive agent/task names.
- Read any existing task folder before writing. Use a unique folder when another run already occupies the path.
- Add a short README for outputs that need context, sources, or usage instructions.
- Only commit files for your task. Do not overwrite or delete other agents' work unless asked.
- Never commit credentials, tokens, .env files, private documents, or other sensitive data: this repository is public.
- Pull the latest changes before starting. Commit with a descriptive message and push without force. If a push is rejected, fetch and reconcile changes without discarding another agent's files.
- Return GitHub links to the files you added.
