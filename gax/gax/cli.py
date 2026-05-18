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


def _run_local(command: str, args: dict, surface: str) -> int:
    env, code = invoke(_REGISTRY, command=command, args=args, surface=surface)
    _print_json(env)
    return code


def _run_remote(command: str, args: dict, surface: str, host: str, port: int) -> int:
    try:
        env, code = remote_invoke(command, args, surface=surface, host=host, port=port)
    except Exception as e:
        click.echo(json.dumps({"ok": False, "error": str(e)}), err=True)
        return 1
    _print_json(env)
    return code


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
@click.option("--export", is_flag=True, help="Print export GAX_CAP=... line")
def cap_mint(
    tenant: str | None,
    commands: tuple[str, ...],
    scopes: tuple[str, ...],
    ttl: int,
    macaroon: bool,
    export: bool,
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
        )
    if export:
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
def _register_command_aliases() -> None:
    for m in _REGISTRY.list_commands():

        def make_callback(cmd_name: str):
            @click.command(name=cmd_name, context_settings={"ignore_unknown_options": True})
            @click.option("--surface", default="model", type=click.Choice(["model", "human", "full"]))
            @click.option("--repo", default=None)
            @click.option("--number", type=int, default=None)
            @click.option("--limit", type=int, default=None)
            @click.option("--state", default=None)
            @click.option("--message", default=None)
            @click.pass_context
            def cmd(
                ctx: click.Context,
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
                if ctx.obj.get("local"):
                    sys.exit(_run_local(cmd_name, args, surface))
                sys.exit(_run_remote(cmd_name, args, surface, ctx.obj["host"], ctx.obj["port"]))

            return cmd

        main.add_command(make_callback(m.command))


_register_command_aliases()


if __name__ == "__main__":
    main(obj={})
