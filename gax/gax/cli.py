from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import click

from gax.caps import mint_capability
from gax.client import remote_doc, remote_invoke, remote_schema, remote_search
from gax.executor import invoke
from gax.paths import DEFAULT_HOST, DEFAULT_PORT, PID_PATH
from gax.registry import Registry

_REGISTRY = Registry()


def _print_json(obj: object) -> None:
    click.echo(json.dumps(obj, indent=2))


def _capability() -> str | None:
    """
    Capability for this invocation: explicit env wins, else the one `gax init`
    saved. Falling back to the saved file is what makes the first run work
    without the user having to export anything.
    """
    from gax.onboarding import read_saved_cap

    return os.environ.get("GAX_CAP", "").strip() or read_saved_cap()


def _hint(message: str, fix: str) -> None:
    """First-run errors should say what to do, not just what failed."""
    click.echo(f"\n  {message}\n  → {fix}\n", err=True)


def _run_local(command: str, args: dict, surface: str) -> int:
    cap = _capability()
    if not cap:
        _print_json(
            {
                "ok": False,
                "error": {
                    "kind": "capability_invalid",
                    "message": "no capability token found",
                },
            }
        )
        _hint(
            "No capability token.",
            'Run "gax init", then: eval "$(gax init --print-export)"',
        )
        return 3
    env, code = invoke(
        _REGISTRY, command=command, args=args, surface=surface, capability=cap
    )
    _print_json(env)
    return code


def _run_remote(command: str, args: dict, surface: str, host: str, port: int) -> int:
    try:
        env, code = remote_invoke(
            command, args, surface=surface, host=host, port=port, capability=_capability()
        )
    except Exception as e:
        click.echo(json.dumps({"ok": False, "error": str(e)}), err=True)
        if _is_connection_error(e):
            _hint(
                f"gaxd is not running on {host}:{port}.",
                'Run "gax init" (starts it), or "gaxd start --background", '
                'or use "gax --local <command>" to run without the sidecar.',
            )
        return 1
    _print_json(env)
    return code


def _is_connection_error(e: Exception) -> bool:
    text = str(e).lower()
    return "connect" in text or "refused" in text or "errno 61" in text


@click.group()
@click.option("--local", is_flag=True, help="Run in-process without gaxd")
@click.option("--host", default=DEFAULT_HOST, envvar="GAX_HOST")
@click.option("--port", default=DEFAULT_PORT, type=int, envvar="GAX_PORT")
@click.pass_context
def main(ctx: click.Context, local: bool, host: str, port: int) -> None:
    ctx.ensure_object(dict)
    ctx.obj["local"] = local
    ctx.obj["host"] = host
    ctx.obj["port"] = port


@main.command("init")
@click.option("--force", is_flag=True, help="Re-mint the dev capability even if valid")
@click.option("--no-daemon", is_flag=True, help="Set up but do not start gaxd")
@click.option(
    "--profile",
    "profiles_",
    multiple=True,
    help="Install a command profile (repeatable): k8s, github",
)
@click.option(
    "--print-export",
    is_flag=True,
    help='Print only: export GAX_CAP="..."  (use with eval)',
)
@click.pass_context
def init_cmd(
    ctx: click.Context,
    force: bool,
    no_daemon: bool,
    profiles_: tuple[str, ...],
    print_export: bool,
) -> None:
    """Set up ~/.gax, mint a dev capability, and start the sidecar."""
    from gax.onboarding import run_init

    host, port = ctx.obj["host"], ctx.obj["port"]

    if print_export:
        # Quiet path for eval "$(gax init --print-export)" — no daemon side effects.
        report = run_init(host=host, port=port, start_daemon=False, force=force)
        click.echo(f'export GAX_CAP="{report["capability"]}"')
        return

    report = run_init(
        host=host,
        port=port,
        start_daemon=not no_daemon,
        force=force,
        profiles=list(profiles_),
    )

    click.echo("\nGAX is ready.\n")
    for step in report["steps"]:
        click.echo(f"  ✓ {step}")

    if not report["daemon_running"] and not no_daemon:
        click.echo(
            "\n  ! gaxd did not start — commands still work with: gax --local <cmd>"
        )

    click.echo("\nTry it:\n")
    click.echo("  gax demo.echo --message hello")
    click.echo("  gax search 'pull requests'")
    click.echo("\nConnect an agent (Claude Code, Cursor, any MCP client):\n")
    click.echo("  claude mcp add gax -- gax-mcp")
    click.echo("\nFor scripts and other shells:\n")
    click.echo('  eval "$(gax init --print-export)"')
    click.echo(
        "\nThe dev capability is read-only. To run destructive commands, mint one"
        "\nexplicitly:\n"
    )
    click.echo(
        "  gax auth cap-mint --command k8s.pod.delete --scope k8s:pods:write \\\n"
        "    --max-side-effect destructive --raw"
    )
    click.echo("\nCheck setup any time with: gax doctor\n")


@main.group("profile")
def profile_group() -> None:
    """Bundled command sets (k8s, github)."""


@profile_group.command("list")
def profile_list() -> None:
    """Show available profiles and what they register."""
    from gax.profiles import available_profiles, installed_commands

    profiles = available_profiles()
    if not profiles:
        click.echo("No profiles bundled with this install.")
        return

    present = installed_commands()
    click.echo("")
    for name, p in profiles.items():
        have = sum(1 for c in p.commands if c.command in present)
        mark = "installed" if have == len(p.commands) else (
            f"{have}/{len(p.commands)} installed" if have else "available"
        )
        click.echo(f"  {name:<10} {len(p.commands)} commands ({p.summary})  [{mark}]")
        for c in p.commands:
            flag = {"read": " ", "write": "~", "destructive": "!"}.get(c.side_effects, "?")
            click.echo(f"      {flag} {c.command:<28} {c.description[:44]}")
        click.echo("")
    click.echo("  Legend:   read    ~ write    ! destructive\n")
    click.echo("  Install:  gax profile add <name>\n")


@profile_group.command("add")
@click.argument("name")
@click.option("--force", is_flag=True, help="Overwrite manifests already installed")
def profile_add(name: str, force: bool) -> None:
    """Install a profile's commands into ~/.gax/manifests/."""
    from gax.profiles import available_profiles, install_profile

    try:
        result = install_profile(name, force=force)
    except KeyError:
        names = ", ".join(available_profiles()) or "(none)"
        raise click.ClickException(f"unknown profile '{name}'; available: {names}")

    click.echo(f"\n  Installed profile '{name}' → {result['target']}")
    click.echo(f"  {len(result['installed'])} command(s) added: {result['summary']}")
    if result["skipped"]:
        click.echo(
            f"  {len(result['skipped'])} already present (use --force to overwrite)"
        )
    click.echo(
        "\n  Installing a profile grants nothing on its own — invoking still needs a"
        "\n  capability naming the command, holding its scope, and reaching its ceiling."
    )
    click.echo("\n  Mint one for the read-only commands:\n")
    click.echo(f"    gax init --profile {name} --force")
    click.echo("\n  Or for a specific destructive command:\n")
    destructive = [
        c for c in (available_profiles()[name].commands) if c.side_effects == "destructive"
    ]
    example = destructive[0] if destructive else available_profiles()[name].commands[0]
    click.echo(
        f"    gax auth cap-mint --command {example.command} \\\n"
        f"      --scope {(example.required_scopes or ['<scope>'])[0]} \\\n"
        f"      --max-side-effect {example.side_effects} --raw"
    )
    click.echo("\n  Restart gaxd to pick up new commands: gaxd stop && gaxd start --background\n")


@main.group("mcp")
def mcp_group() -> None:
    """Import and verify MCP servers as pinned GAX commands."""


@mcp_group.command(
    "import",
    # Server args routinely start with a dash (`npx -y ...`); without this click
    # tries to parse them as GAX options and the command is unusable for the most
    # common invocation there is.
    context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False},
)
@click.argument("server_command")
@click.argument("server_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--id", "server_id", required=True, help="Short name, e.g. 'filesystem'")
@click.option("--only", multiple=True, help="Import just these tools (repeatable)")
@click.option("--force", is_flag=True, help="Overwrite manifests already imported")
@click.option("--dry-run", is_flag=True, help="Show what would be imported")
def mcp_import(
    server_command: str,
    server_args: tuple[str, ...],
    server_id: str,
    only: tuple[str, ...],
    force: bool,
    dry_run: bool,
) -> None:
    """
    Import an MCP server's tools as pinned commands.

    Example: gax mcp import --id filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
    """
    from gax.mcp_import import import_server

    try:
        report = import_server(
            server_id=server_id,
            server_command=server_command,
            server_args=list(server_args),
            only=list(only) or None,
            force=force,
            dry_run=dry_run,
        )
    except Exception as e:
        raise click.ClickException(f"import failed: {e}")

    verb = "Would import" if dry_run else "Imported"
    click.echo(f"\n  {verb} {len(report['written'])} of {report['tool_count']} tool(s) "
               f"from '{server_id}'")
    if not dry_run:
        click.echo(f"  → {report['target']}\n")
    else:
        click.echo("")

    for row in report["written"]:
        flag = {"read": " ", "write": "~", "destructive": "!"}.get(row["side_effects"], "?")
        click.echo(f"    {flag} {row['command']:<44} {row['pin'][:19]}…")

    if report["skipped"]:
        click.echo(
            f"\n  {len(report['skipped'])} already imported "
            "(use --force to re-pin)"
        )

    click.echo(
        "\n  Every tool is pinned: its name, description, and input schema are"
        "\n  hashed now and re-checked before each invoke. If the server changes"
        "\n  what a tool does, the call fails closed with `pin_mismatch`."
    )
    click.echo(
        "\n  Imported tools default to `destructive` unless clearly read-only, so"
        "\n  your read-only capability cannot invoke them yet. Review each one,"
        "\n  then set `side_effects` in its manifest and mint a capability for it."
    )
    click.echo("\n  Re-check pins any time: gax mcp verify\n")


@mcp_group.command("verify")
@click.option("--server", default=None, help="Only commands imported from this server id")
def mcp_verify(server: str | None) -> None:
    """Re-check every imported pin against the live servers."""
    import yaml

    from gax.mcp_import import verify_manifest_pins
    from gax.paths import USER_MANIFESTS_DIR

    manifests = []
    unpinned: list[str] = []
    for m in _REGISTRY.list_commands():
        if m.adapter != "mcp":
            continue
        data = m.raw or {}
        if not data.get("mcp_pin"):
            unpinned.append(m.command)
            continue
        if server and data.get("mcp_pin_imported_from") != server:
            continue
        manifests.append(data)

    if not manifests:
        click.echo("\n  No pinned MCP commands found. Import one: gax mcp import --help\n")
        if unpinned:
            click.echo(
                f"  {len(unpinned)} unpinned MCP command(s) present — these are not"
                "\n  verified against their server:\n"
            )
            for cmd in unpinned:
                click.echo(f"    ! {cmd}")
            click.echo("")
        return

    results = verify_manifest_pins(manifests)
    symbols = {"ok": "✓", "mismatch": "✗", "missing": "✗", "unpinned": "!", "unreachable": "?"}
    click.echo("")
    for r in results:
        click.echo(f"  {symbols.get(r['status'], '?')} {r['command']:<44} {r['status']}")
        if r["status"] in ("mismatch", "missing"):
            click.echo(f"      {r['detail']}")

    # Hand-written manifests predate pinning and are skipped above. Say so
    # explicitly — "All N verified" would otherwise imply full coverage.
    for cmd in unpinned:
        click.echo(f"  ! {cmd:<44} unpinned (not verified)")

    bad = [r for r in results if r["status"] in ("mismatch", "missing")]
    click.echo("")
    if unpinned:
        click.echo(
            f"  {len(unpinned)} command(s) have no pin — hand-written manifests are"
            "\n  not checked against their server. Re-import to pin them.\n"
        )
    if bad:
        click.echo(
            f"  {len(bad)} tool(s) changed since import. These fail closed on invoke.\n"
            "  Review the change, then re-pin deliberately:\n"
            "    gax mcp import --id <server> --force <command> <args...>\n"
        )
        sys.exit(1)
    click.echo(f"  All {len(results)} pin(s) verified.\n")


@main.command("doctor")
@click.pass_context
def doctor_cmd(ctx: click.Context) -> None:
    """Diagnose setup: config, capability, sidecar, backends."""
    from gax.onboarding import run_doctor

    checks = run_doctor(host=ctx.obj["host"], port=ctx.obj["port"])
    click.echo("")
    for c in checks:
        click.echo(f"  {c.symbol} {c.name:<18} {c.detail}")
        if not c.ok and c.fix:
            click.echo(f"      → {c.fix}")
    failures = [c for c in checks if not c.ok]
    click.echo("")
    if failures:
        click.echo(f"  {len(failures)} issue(s) found.\n")
        sys.exit(1)
    click.echo("  All checks passed.\n")


@main.group()
def auth() -> None:
    """Authentication and capabilities."""


@auth.command("login")
@click.option("--tenant", default="default", help="Tenant id")
@click.option(
    "--provider",
    default="github",
    help="OAuth provider from config/oauth_providers.yaml",
)
@click.option("--no-browser", is_flag=True, help="Do not open verification URL")
def auth_login(tenant: str, provider: str, no_browser: bool) -> None:
    """OAuth 2.0 device flow (RFC 8628); stores tokens under ~/.gax/tokens/."""
    from gax.oauth import device_flow_login, load_providers
    from gax.paths import CONFIG_PATH, ensure_gax_home

    providers = load_providers()
    if provider not in providers:
        names = ", ".join(providers) or "(none — check config/oauth_providers.yaml)"
        raise click.ClickException(f"unknown provider '{provider}'; available: {names}")

    ensure_gax_home()
    cfg = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    cfg["tenant_id"] = tenant
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

    click.echo(f"Starting device flow for provider={provider} tenant={tenant}")
    tokens = device_flow_login(
        providers[provider],
        tenant=tenant,
        open_browser=not no_browser,
    )
    scope = tokens.get("scope", "")
    click.echo(f"Saved tokens to ~/.gax/tokens/{tenant}/{provider}.json")
    if scope:
        click.echo(f"Scopes: {scope}")
    click.echo("Mint capability: gax auth cap-from-oauth --export")


@auth.command("cap-from-oauth")
@click.option("--tenant", default=None)
@click.option("--provider", default="github")
@click.option("--command", "commands", multiple=True)
@click.option("--ttl", default=3600, type=int)
@click.option("--export", is_flag=True)
def cap_from_oauth(
    tenant: str | None,
    provider: str,
    commands: tuple[str, ...],
    ttl: int,
    export: bool,
) -> None:
    """Mint GAX_CAP JWT using scopes from stored OAuth tokens."""
    from gax.oauth import mint_cap_from_oauth
    from gax.paths import CONFIG_PATH

    tid = tenant
    if not tid and CONFIG_PATH.exists():
        tid = json.loads(CONFIG_PATH.read_text()).get("tenant_id", "default")
    tid = tid or "default"
    cmd_list = list(commands) if commands else ["*"]
    token = mint_cap_from_oauth(tid, provider, commands=cmd_list, ttl_seconds=ttl)
    if export:
        click.echo(f'export GAX_CAP="{token}"')
    else:
        click.echo(token)


@auth.command("status")
@click.option("--tenant", default=None)
def auth_status(tenant: str | None) -> None:
    """Show stored OAuth providers for tenant."""
    from gax.oauth import load_tokens
    from gax.paths import CONFIG_PATH, GAX_HOME

    tid = tenant
    if not tid and CONFIG_PATH.exists():
        tid = json.loads(CONFIG_PATH.read_text()).get("tenant_id", "default")
    tid = tid or "default"
    tok_dir = GAX_HOME / "tokens" / tid
    if not tok_dir.exists():
        click.echo(f"No OAuth tokens for tenant={tid}")
        return
    for p in sorted(tok_dir.glob("*.json")):
        data = json.loads(p.read_text())
        click.echo(
            f"{p.stem}: access_token=*** scopes={data.get('scope', data.get('scopes', '?'))}"
        )


@auth.command("cap-mint")
@click.option("--tenant", default=None)
@click.option("--command", "commands", multiple=True, help="Allowed commands (repeatable)")
@click.option("--scope", "scopes", multiple=True, help="Scopes (repeatable)")
@click.option("--ttl", default=3600, type=int, help="TTL seconds")
@click.option("--macaroon", is_flag=True, help="Emit macaroon-style cap instead of JWT")
@click.option("--export", is_flag=True, help="Print export GAX_CAP=... line (use with eval)")
@click.option("--raw", is_flag=True, help="Print the bare token, no quotes or prefix")
@click.option(
    "--max-side-effect",
    type=click.Choice(["read", "write", "destructive"]),
    default="read",
    show_default=True,
    help="Danger ceiling. A command above this is refused even if allowlisted.",
)
def cap_mint(
    tenant: str | None,
    commands: tuple[str, ...],
    scopes: tuple[str, ...],
    ttl: int,
    macaroon: bool,
    export: bool,
    raw: bool,
    max_side_effect: str,
) -> None:
    from gax.paths import CONFIG_PATH

    cmd_list = list(commands) if commands else ["*"]
    scope_list = list(scopes) if scopes else ["*"]
    tid = tenant
    if not tid and CONFIG_PATH.exists():
        tid = json.loads(CONFIG_PATH.read_text()).get("tenant_id", "default")
    if macaroon:
        from gax.macaroons_cap import mint_macaroon

        token = mint_macaroon(
            tenant_id=tid or "default",
            subject="dev@local",
            commands=cmd_list,
            scopes=scope_list,
            ttl_seconds=ttl,
        )
    else:
        token = mint_capability(
            tenant_id=tenant,
            commands=cmd_list,
            scopes=scope_list,
            ttl_seconds=ttl,
            max_side_effect=max_side_effect,
        )
    if export and not raw:
        click.echo(f'export GAX_CAP="{token}"')
    else:
        click.echo(token)


@main.group()
def daemon() -> None:
    """Manage gaxd sidecar."""


@daemon.command("start")
@click.option("--background", is_flag=True)
@click.option("--host", default=DEFAULT_HOST)
@click.option("--port", default=DEFAULT_PORT, type=int)
def daemon_start(background: bool, host: str, port: int) -> None:
    args = [sys.executable, "-m", "gax.daemon", "start", "--host", host, "--port", str(port)]
    if background:
        args.append("--background")
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        click.echo(f"gaxd starting on http://{host}:{port}")
    else:
        os.execv(sys.executable, [sys.executable, "-m", "gax.daemon", "start", "--host", host, "--port", str(port)])


@daemon.command("stop")
def daemon_stop() -> None:
    subprocess.call([sys.executable, "-m", "gax.daemon", "stop"])


@daemon.command("status")
def daemon_status() -> None:
    subprocess.call([sys.executable, "-m", "gax.daemon", "status"])


@main.command("search")
@click.argument("query")
@click.pass_context
def search_cmd(ctx: click.Context, query: str) -> None:
    if ctx.obj["local"]:
        hits = _REGISTRY.search(query)
        _print_json(
            {
                "query": query,
                "results": [
                    {"command": m.command, "description": m.description, "category": m.category}
                    for m in hits
                ],
            }
        )
        return
    _print_json(remote_search(query, ctx.obj["host"], ctx.obj["port"]))


@main.command("doc")
@click.argument("command")
@click.pass_context
def doc_cmd(ctx: click.Context, command: str) -> None:
    if ctx.obj["local"]:
        stub = _REGISTRY.doc_stub(command)
        if not stub:
            click.echo(json.dumps({"error": "not_found"}), err=True)
            sys.exit(4)
        _print_json(stub)
        return
    try:
        _print_json(remote_doc(command, ctx.obj["host"], ctx.obj["port"]))
    except Exception:
        sys.exit(4)


@main.command("schema")
@click.argument("command")
@click.pass_context
def schema_cmd(ctx: click.Context, command: str) -> None:
    m = _REGISTRY.get(command)
    if ctx.obj["local"]:
        if not m:
            sys.exit(4)
        _print_json({"command": command, "input_schema": m.input_schema, "output_schema": m.output_schema})
        return
    try:
        _print_json(remote_schema(command, ctx.obj["host"], ctx.obj["port"]))
    except Exception:
        sys.exit(4)


@main.group()
def plan() -> None:
    """Multi-step DAG-style plans."""


@plan.command("run")
@click.argument("plan_file", type=click.Path(exists=True))
@click.option("--surface", default=None, help="Override plan surface")
@click.pass_context
def plan_run(ctx: click.Context, plan_file: str, surface: str | None) -> None:
    """Run a YAML plan (sequential steps with {{ steps.* }} templates)."""
    from gax.plan import load_plan, run_plan

    spec = load_plan(plan_file)
    surf = surface or spec.get("surface") or "model"

    def _invoke(**kw: object) -> tuple[dict, int]:
        if ctx.obj["local"]:
            return invoke(_REGISTRY, capability=os.environ.get("GAX_CAP"), **kw)  # type: ignore[arg-type]
        env, code = remote_invoke(
            str(kw["command"]),
            dict(kw["args"]),  # type: ignore[arg-type]
            surface=str(kw["surface"]),
            host=ctx.obj["host"],
            port=ctx.obj["port"],
        )
        return env, code

    env, code = run_plan(
        _REGISTRY,
        spec,
        surface=surf,
        capability=os.environ.get("GAX_CAP"),
        invoke_fn=_invoke if not ctx.obj["local"] else None,
    )
    _print_json(env)
    sys.exit(code)


@main.command("commands")
@click.pass_context
def commands_cmd(ctx: click.Context) -> None:
    items = [
        {"command": m.command, "version": m.version, "description": m.description}
        for m in _REGISTRY.list_commands()
    ]
    _print_json({"commands": items})


@main.command("run")
@click.argument("command")
@click.option("--surface", default="model", type=click.Choice(["model", "human", "full"]))
@click.option("--repo", default=None, help="For gh.* commands")
@click.option("--number", type=int, default=None)
@click.option("--limit", type=int, default=None)
@click.option("--state", default=None)
@click.option("--message", default=None, help="For demo.echo")
@click.pass_context
def run_cmd(
    ctx: click.Context,
    command: str,
    surface: str,
    repo: str | None,
    number: int | None,
    limit: int | None,
    state: str | None,
    message: str | None,
) -> None:
    args: dict = {}
    if repo:
        args["repo"] = repo
    if number is not None:
        args["number"] = number
    if limit is not None:
        args["limit"] = limit
    if state:
        args["state"] = state
    if message:
        args["message"] = message
    if ctx.obj["local"]:
        sys.exit(_run_local(command, args, surface))
    sys.exit(_run_remote(command, args, surface, ctx.obj["host"], ctx.obj["port"]))


@main.group()
def openapi() -> None:
    """OpenAPI → GAX manifest generator."""


@openapi.command("generate")
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--out", "out_dir", default=None, help="Manifests dir (default: gax/manifests)")
@click.option("--prefix", default="api")
@click.option("--adapter", default="mock", type=click.Choice(["mock", "http"]))
def openapi_generate(spec_path: str, out_dir: str | None, prefix: str, adapter: str) -> None:
    from gax.openapi_gen import generate_manifests, load_spec, write_manifests
    from gax.paths import MANIFESTS_DIR

    spec = load_spec(Path(spec_path))
    manifests = generate_manifests(spec, prefix=prefix, adapter=adapter)
    target = Path(out_dir) if out_dir else MANIFESTS_DIR
    paths = write_manifests(manifests, target)
    click.echo(f"Wrote {len(paths)} manifests to {target}")
    click.echo("Restart gaxd or use --local to reload registry.")


@main.group()
def vault() -> None:
    """Tenant secret vault (file or HashiCorp via GAX_HASHICORP_VAULT_ADDR)."""


@vault.command("put")
@click.argument("key")
@click.argument("value")
@click.option("--tenant", default=None)
def vault_put(key: str, value: str, tenant: str | None) -> None:
    from gax.paths import CONFIG_PATH
    from gax.vault import vault_put as vp

    tid = tenant or "default"
    if not tenant and CONFIG_PATH.exists():
        tid = json.loads(CONFIG_PATH.read_text()).get("tenant_id", "default")
    vp(tid, key, value)
    click.echo(f"stored {key} for tenant={tid}")


@vault.command("get")
@click.argument("key")
@click.option("--tenant", default=None)
def vault_get(key: str, tenant: str | None) -> None:
    from gax.paths import CONFIG_PATH
    from gax.vault import vault_get as vg

    tid = tenant or "default"
    if not tenant and CONFIG_PATH.exists():
        tid = json.loads(CONFIG_PATH.read_text()).get("tenant_id", "default")
    val = vg(tid, key)
    if val is None:
        raise click.ClickException(f"key not found: {key}")
    click.echo(val)


@main.group()
def compliance() -> None:
    """Compliance exports (SOC2-aligned audit bundles)."""


@compliance.command("export")
@click.option("--format", "fmt", default="csv", type=click.Choice(["csv", "json"]))
@click.option("--out", default=None, help="Output path")
def compliance_export(fmt: str, out: str | None) -> None:
    from gax.compliance import export_soc2_csv, export_soc2_json
    from gax.paths import GAX_HOME

    if fmt == "csv":
        path = Path(out) if out else GAX_HOME / "exports" / "audit_soc2.csv"
        n = export_soc2_csv(path)
        click.echo(f"exported {n} records to {path}")
    else:
        path = Path(out) if out else GAX_HOME / "exports" / "audit_soc2.json"
        bundle = export_soc2_json(path)
        click.echo(f"exported {bundle['record_count']} records to {path}")


# Dynamic command aliases: gax gh.pr.list ...
_JSON_TO_CLICK = {
    "integer": int,
    "number": float,
    "boolean": bool,
    "string": str,
}


def _options_from_schema(schema: dict) -> list:
    """
    Build click options from a manifest's input_schema.

    Derived rather than hardcoded: a new manifest gets working CLI flags with no
    change here. Booleans become `--flag/--no-flag` so `--dry-run` reads naturally.
    """
    props = (schema or {}).get("properties") or {}
    required = set((schema or {}).get("required") or [])
    opts = []
    for name, spec in props.items():
        flag = "--" + name.replace("_", "-")
        jtype = (spec or {}).get("type", "string")
        help_text = (spec or {}).get("description", "")
        if required:
            help_text = (help_text + (" [required]" if name in required else "")).strip()
        if jtype == "boolean":
            opts.append(
                click.option(
                    f"{flag}/--no-{name.replace('_', '-')}",
                    name,
                    default=None,
                    help=help_text,
                )
            )
        else:
            opts.append(
                click.option(
                    flag,
                    name,
                    type=_JSON_TO_CLICK.get(jtype, str),
                    default=None,
                    help=help_text,
                )
            )
    return opts


def _register_command_aliases() -> None:
    for m in _REGISTRY.list_commands():

        def make_callback(cmd_name: str, schema: dict, description: str):
            @click.pass_context
            def cmd(ctx: click.Context, surface: str, **kwargs) -> None:
                # Drop unset options so adapters see only what the user passed.
                args = {k: v for k, v in kwargs.items() if v is not None}
                if ctx.obj.get("local"):
                    sys.exit(_run_local(cmd_name, args, surface))
                sys.exit(_run_remote(cmd_name, args, surface, ctx.obj["host"], ctx.obj["port"]))

            cmd = click.option(
                "--surface", default="model", type=click.Choice(["model", "human", "full"])
            )(cmd)
            for opt in reversed(_options_from_schema(schema)):
                cmd = opt(cmd)
            return click.command(name=cmd_name, help=description or None)(cmd)

        main.add_command(make_callback(m.command, m.input_schema, m.description))


_register_command_aliases()


if __name__ == "__main__":
    main(obj={})
