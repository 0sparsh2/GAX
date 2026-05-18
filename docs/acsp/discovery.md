# Lazy discovery

Agents must **not** load full tool catalogs.

| Command | Purpose | Target size |
|---------|---------|-------------|
| `gax search <query>` | Fuzzy command search | ~150–250 tokens |
| `gax doc <command>` | Args + scopes stub | ~80–120 tokens |
| `gax schema <command>` | Full JSON Schema | On demand |

Registry lives in `gaxd` / `manifests/*.yaml`.
