from __future__ import annotations

from typing import Any

from gax.registry import CommandManifest


def run(manifest: CommandManifest, args: dict[str, Any]) -> dict[str, Any]:
    if manifest.command == "demo.echo":
        return {"echo": args.get("message", "hello")}
    if manifest.command == "gh.pr.list":
        repo = args.get("repo", "octocat/Hello-World")
        return {
            "items": [
                {
                    "number": 1,
                    "title": f"[mock] Sample PR for {repo}",
                    "state": "OPEN",
                    "url": f"https://github.com/{repo}/pull/1",
                    "author": "mock-user",
                    "draft": False,
                }
            ],
            "_mock": True,
        }
    if manifest.command == "gh.pr.view":
        return {
            "number": args.get("number", 1),
            "title": "[mock] PR title",
            "body": "Mock body",
            "state": "OPEN",
            "url": f"https://github.com/{args.get('repo', 'o/r')}/pull/{args.get('number', 1)}",
            "author": "mock-user",
            "_mock": True,
        }
    if manifest.command == "kubectl.get.pods":
        ns = args.get("namespace", "default")
        return {
            "items": [{"name": "mock-pod-1", "namespace": ns, "status": "Running"}],
            "_mock": True,
        }
    if manifest.command == "aws.s3.list":
        return {"buckets": [{"name": "mock-bucket-a"}, {"name": "mock-bucket-b"}], "_mock": True}
    if manifest.command == "jira.issue.get":
        key = args.get("issue_key", "DEMO-1")
        return {"key": key, "summary": "[mock] Issue", "status": "Open", "_mock": True}
    if manifest.command.startswith("api."):
        return {"_mock": True, "command": manifest.command, "args": args}
    return {"result": "ok", "command": manifest.command, "args": args}
