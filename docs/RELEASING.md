# Releasing GAX to PyPI

> **A PyPI release is permanent.** You can yank a version but never reuse the number,
> and the project name is claimed forever. Do the TestPyPI dry run first.

---

## 0. Revoke any API token that has been shared

If a PyPI API token was ever pasted into a chat, an issue, a screenshot, or a log,
treat it as compromised and revoke it: <https://pypi.org/manage/account/token/>

A publish token can push a malicious release under your name to a package other people
install. The setup below uses **no token at all**.

---

## 1. One-time PyPI setup — pending publisher

PyPI no longer lets you pre-register a name, so for a project that does not exist yet
you add a **pending publisher**. It lives under account settings, *not* under
"Your projects":

**<https://pypi.org/manage/account/publishing/>**

Fill in "Add a new pending publisher":

| Field | Value |
|---|---|
| PyPI Project Name | `gax-cli` |
| Owner | `0sparsh2` |
| Repository name | `GAX` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

Repeat on **TestPyPI** (<https://test.pypi.org/manage/account/publishing/>) with
environment `testpypi` for the dry run.

The first tagged push then creates *and* publishes the project. After that it becomes a
normal trusted publisher and the pending entry disappears.

> **Distribution name vs import name.** The PyPI project is **`gax-cli`**; the Python
> package and the commands stay **`gax`**. So `pip install gax-cli` gives you
> `import gax` plus the `gax`, `gaxd`, and `gax-mcp` executables. This is normal
> (`pip install pillow` → `import PIL`) and intentional — only the `pip install` line
> in the docs uses the distribution name.
>
> The built artifacts are `gax_cli-<version>-py3-none-any.whl` and
> `gax_cli-<version>.tar.gz`; setuptools normalizes the `-` to `_` in filenames.

## 2. One-time GitHub setup — environments

Settings → Environments, create two: `pypi` and `testpypi`.

On `pypi`, add yourself as a **required reviewer**. That turns the real publish into a
manual approval — worth it for an irreversible action.

---

## Release checklist

### Pre-flight

- [ ] `cd gax && pytest -q` — all green
- [ ] Version bumped in `gax/pyproject.toml` (this is the source of truth)
- [ ] Version not already on PyPI (numbers cannot be reused)
- [ ] `docs/QUICKSTART.md` gap table reflects reality
- [ ] Package README (`gax/README.md`) has **no repo-relative links** — it renders on
      PyPI where `../docs/` resolves to nothing

### Dry run on TestPyPI

Actions → **Release** → *Run workflow* → target `testpypi`.

Then install the published artifact in a clean venv:

```bash
python -m venv /tmp/tp && source /tmp/tp/bin/activate
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ gax-cli

export HOME=/tmp/tphome && mkdir -p "$HOME"
gax init --profile k8s
gax demo.echo --message hi          # expect ok:true with an audit_id
GAX_K8S_MOCK=1 gax k8s.namespace.delete --namespace prod   # expect policy_denied
gax doctor
```

- [ ] Install succeeds from a clean venv
- [ ] `gax init` completes and the first command works with **no exports**
- [ ] The destructive command is **refused**
- [ ] Project page renders (description, links, classifiers)

### Real release

```bash
git tag v0.4.0
git push origin v0.4.0
```

Approve the `pypi` environment when prompted.

- [ ] `pip install gax-cli` works in a clean venv
- [ ] `gax init --profile k8s --profile github` registers 22 commands
- [ ] GitHub Release created with notes

---

## What the pipeline guards

`release.yml` refuses to publish a broken artifact. Each gate exists because of a bug
that actually shipped during development:

| Gate | Catches |
|---|---|
| `pytest -q` before build | Obvious regressions |
| `sync_package_data.py` | **The wheel shipping no `config/policy.yaml`** — installs cleanly, then silently drops every tenant allowlist |
| `verify_wheel.py` | Missing manifests/profiles/config; data at wheel root that would collide with other distributions |
| `twine check` | Metadata that fails to render on PyPI |
| Smoke test | Installs the built wheel in a clean venv and asserts policy loads, an invoke succeeds with an `audit_id`, and a destructive command is denied |

The smoke test matters most: a wheel that imports fine but cannot enforce policy is worse
than one that fails outright.

## If a release is broken

```bash
pip install twine
twine yank gax-cli==0.4.0 --reason "shipped without policy data"
```

Yanking hides it from new resolutions but does **not** delete it, and the number stays
burned. Fix forward with a new patch version.
