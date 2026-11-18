# tiny-web-code

A portable snapshot of the Hermes `tiny-web-code` profile. Runs the local
`qwen3.5:2b-64k` Ollama model with web tools and Python code execution.

**No memories, user profile, conversations, credentials, logs, caches, databases,
or model weights are included.** Your existing profile on the source device is
not changed by this repository.

## Install on another device

### Automatic install (Ubuntu 22.04+ / Debian 12+)

Download and extract the project archive, then run this from the extracted folder:

```bash
bash install.sh
```

The script uses the official Hermes Agent and Ollama installers if those programs
are missing. It starts local Ollama if needed, downloads and verifies the
original ~2.7 GB model, installs the profile, and opens terminal chat. Run it as
your normal account; it may ask for `sudo` for system packages or Ollama. No
model API key or GitHub login is needed for local chat from the archive. Add
`--with-web` to install and select DDGS for keyless web search. Searches go over
the internet and may be rate-limited. This option does not set up a provider
for page extraction.

Use `bash install.sh --install-only` to skip opening chat, or `--name my-profile`
to install alongside an existing profile. The script does not upgrade existing
apps or overwrite existing profiles or model aliases. To reopen chat, run
`hermes -p tiny-web-code` (open a new terminal if `hermes` isn't on your PATH
yet). If Ollama wasn't installed as a startup service, you may need to run
`ollama serve` after reboot. Keep the extracted folder if you want Hermes to
update from it later.

### Manual install

Prerequisites:

- Git and Python 3.10+ (`python3` below; `python` also works).
- Hermes Agent **0.22.4 or newer**, with its CLI on `PATH` and normal runtime
  dependencies installed. Official installation:
  <https://hermes-agent.nousresearch.com/docs/getting-started/installation>.
- Ollama, with the local server running on `http://127.0.0.1:11434` and its CLI on
  `PATH`. The source device uses Ollama **0.34.4**; use that version or newer.
  Install from <https://ollama.com/download>. Open the Ollama app, or run
  `ollama serve` in a separate terminal if no server is running.
- Enough disk and RAM for the source Q8_0 model (about **2.7 GB of weights**) and
  its **65,536-token** context. Runtime RAM is higher than the model file size;
  the required amount depends on the inference backend and context use.
  A GPU is not required, but CPU inference can be slow.

From a fresh checkout:

```bash
git clone https://github.com/H-Lupercal/tiny-web-code.git
cd tiny-web-code
python3 scripts/setup.py
hermes -p tiny-web-code
```

The setup script:

1. Checks an existing `qwen3.5:2b` or pulls the exact original manifest via the
   `pull_source` recorded in `setup-lock.json`. The default upstream tag has
   moved, so setup verifies the full digest before copying to the local name.
2. Builds `qwen3.5:2b-64k` using the portable `Modelfile`, or validates an existing
   alias without overwriting it.
3. Installs the local checkout using Hermes' native profile-distribution installer.

It does **not** overwrite an existing profile, change your active/default
profile, copy secrets, or run inference. Use `--name another-name` to install
alongside a profile of the same name. That only changes the Hermes profile name;
all copies still reference the same Ollama alias.

Upstream Ollama tags are mutable. If the download source changes digest, setup
stops. If you already have a different local `qwen3.5:2b`, setup also stops by
default. After reviewing the change, `python3 scripts/setup.py --allow-model-drift`
can accept the existing local base, but will still refuse to overwrite an
incompatible alias. The original versions, model digests, and Hermes commit are
recorded in `setup-lock.json`; this is provenance, not a vendored copy or an
automatic Hermes/Ollama version pin.

## What is preserved

- Original `config.yaml`, `profile.yaml`, and `SOUL.md`.
- Ollama model alias and all recorded model parameters, including `num_ctx 65536`.
- Custom provider at `http://127.0.0.1:11434/v1` and the 65,536-token Hermes context.
- CLI toolsets: `web` and `code_execution`; direct terminal/file tools disabled.
- Maximum 4 agent turns, concise personality, and reasoning disabled for this alias.
- Smart approvals, noninteractive single-query approval mode `deny`, and strict
  code-execution mode.
- The profile's existing `hermes-agent` skill and references, its avatar, and its
  opt-out marker for automatic bundled-skill seeding. Skill bookkeeping is omitted.

The supplied `distribution.yaml` explicitly limits what Hermes installs. Repo-only
setup scripts and tests are not placed in your live profile. The config is copied
from the source, not rewritten or broadened for the destination.

**Security:** `strict` code-execution mode is not an OS/container security boundary.
Python still runs locally with the OS user's permissions. Only use this profile
with code and tasks you trust. Disabling direct terminal/file tools does not make
arbitrary Python harmless.

No existing memories are transferred. Hermes may create new per-device state under
its normal defaults; this is a clean starting profile, not a memory sync mechanism.

## Web access

The source profile has no pinned web provider and no web API credentials in its
`.env`. Its original automatic provider selection is intentionally preserved.
Available keyless services and rate limits can differ across devices and networks;
web search still sends queries over the internet even though inference is local.

If web search is unavailable, select a provider in `hermes -p tiny-web-code tools`.
Add any required credentials **only on the destination device**, never to this repo.
For example, Hermes provides `hermes tools post-setup ddgs` to install its optional
keyless search dependency; select that provider in the tools UI afterwards.

## Verify

Offline installer tests (no model downloads or API calls):

```bash
python3 -m unittest discover -s tests -v
```

Check the actual local Ollama model without installing or downloading anything:

```bash
python3 scripts/setup.py --check-models
```

Check an installed distribution's real Hermes configuration, tool registration,
and Python execution; add `--web` for a live search:

```bash
python3 scripts/smoke.py \
  --home "$HOME/.hermes/profiles/tiny-web-code" --web
```

Use the actual profile path printed by the installer if your Hermes home differs
(e.g. Windows or a custom data root). The smoke test delegates to Hermes' own
Python runtime; it does not guess a `venv` path or install system Python packages.
It executes a small Python calculation and may write normal per-device runtime
state. It does not test the model's quality or load the model for inference.

For a files-only install, without any Ollama/model operations:

```bash
python3 scripts/setup.py --skip-model
```

## Updates

This is a snapshot, not automatic syncing from the source device. To take a future
repo update:

```bash
git pull
hermes profile update tiny-web-code
```

The local-checkout installation records this checkout as its source, so keep it
on disk. Hermes preserves your destination config by default during profile
updates. After reviewing a changed repo config, use the explicit
`hermes profile update tiny-web-code --force-config` option to adopt it.
Re-run model validation if `Modelfile` or `setup-lock.json` changes.

Alternatively, if you already prepared the model, Hermes can install this
repository directly:

```bash
hermes profile install https://github.com/H-Lupercal/tiny-web-code --yes
```

That command installs the distribution files only; it does **not** execute the
setup script, download model weights, or create the Ollama alias.

## Upstream material

The copied `hermes-agent` skill is from Nous Research's Hermes Agent and declares
an MIT license. Its license is retained in `THIRD_PARTY_LICENSES/Hermes-Agent-MIT.txt`.
The Ollama model weights are not redistributed; they retain their upstream license.

Official profile-distribution documentation:
<https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions>.
