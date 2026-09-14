# Security

MaxRunway 0.2.0 does not place API keys, OAuth tokens, browser cookies, or ChatGPT session data in a `.max` scene, job manifest, plugin settings file, or diagnostic log.

- ChatGPT authentication is owned by the installed Codex client. The plugin launches `codex login` and reads only the command's status text.
- Codex-managed Runway OAuth is owned by Codex. The plugin can add the configured HTTPS MCP endpoint and launch `codex mcp login`; it does not read the resulting token.
- The direct Runway adapter uses its own `mcp-remote` browser OAuth cache under `%LOCALAPPDATA%\MaxRunway\mcp-auth`. Do not copy this cache between PCs.
- The Omega Plus API key is stored as a generic credential named `MaxRunway/OmegaPlusApiKey` in Windows Credential Manager. It is passed only to the short-lived analysis process through its environment and is redacted from plugin output.
- Provider URLs must use HTTPS and cannot contain embedded usernames or passwords.

Job files can contain scene paths, output paths, provider task IDs, and temporary signed media URLs. Treat job folders as private production data. Native renders and generated files always remain in separate directories.
