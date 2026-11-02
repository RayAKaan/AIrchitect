# AIrchitect local agent runtime

AIrchitect's web UI cannot install or launch native software in a user's operating system. The local OpenCode runtime therefore requires an explicit, user-approved setup action. The bootstrap never executes from a browser request.

## Requirements

- Node.js 20 or later
- npm
- A supported OpenCode provider credential (configured in OpenCode)
- The AIrchitect web origin, if it is not served from localhost

## Install and start

From the AIrchitect repository root:

```sh
node scripts/agent-runtime.mjs setup --origin http://localhost:5173
```

The command installs the pinned OpenCode 1.x CLI package and starts its HTTP server bound exclusively to loopback. It prints the local URL, username and generated password once. Enter those values in **Settings → Agent provider**. The generated password is not written to disk by AIrchitect. Keep it private.

For production-hosted AIrchitect, use the exact HTTPS origin:

```sh
node scripts/agent-runtime.mjs setup --origin https://app.example.com
```

## Lifecycle

```sh
node scripts/agent-runtime.mjs install
node scripts/agent-runtime.mjs start --origin http://localhost:5173
node scripts/agent-runtime.mjs status
node scripts/agent-runtime.mjs stop
```

The process is started with a fixed argument vector, without a shell. It binds to `127.0.0.1`; non-loopback binding is deliberately rejected. Only the configured browser origin is added to CORS. The generated HTTP Basic password is passed through the OpenCode process environment and printed once for the user to copy.

## Model credentials

Configure model-provider credentials using OpenCode's own authentication flow. AIrchitect does not collect or persist provider API keys in this local-runtime setup. OpenCode stores its provider credentials in its user data directory. A later AIrchitect credential-vault integration must use encrypted server-side storage and must not expose secrets to browser payloads, logs, telemetry or project artifacts.

## Compatibility

This bootstrap currently pins `opencode-ai@1.19.4` (OpenCode 1.x), matching the existing AIrchitect HTTP client contract (`/global/health`, `/session`, `/session/{id}/message`). Do not silently upgrade to OpenCode 2 or `@opencode/cli` until the API adapter and acceptance suite are migrated together.

OpenCode is MIT-licensed. Preserve its license and notices when redistributing its binaries or package. Verify the pinned upstream release and its transitive package metadata as part of each dependency update.
