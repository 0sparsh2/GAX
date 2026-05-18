# Diagram PNG exports

Generated from `../` Mermaid sources via [@mermaid-js/mermaid-cli](https://github.com/mermaid-js/mermaid-cli).

## Regenerate

```bash
cd research/diagrams
mkdir -p png
for f in *.mmd; do
  npx -y @mermaid-js/mermaid-cli@11 -i "$f" -o "png/${f%.mmd}.png" -b transparent
done
```

## Files

| PNG | Source |
|-----|--------|
| [architecture.png](./architecture.png) | [architecture.mmd](../architecture.mmd) |
| [planes.png](./planes.png) | [planes.mmd](../planes.mmd) |
| [sequence-invoke.png](./sequence-invoke.png) | [sequence-invoke.mmd](../sequence-invoke.mmd) |

If rendering fails (Chrome/Puppeteer), try: `PUPPETEER_EXECUTABLE_PATH` or `mmdc -p /path/to/puppeteer-config.json` with `"args": ["--no-sandbox"]`.
