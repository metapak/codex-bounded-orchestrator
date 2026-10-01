# README visual assets

The English and Turkish README pages use an illustrated cover, a team guide,
and screenshots captured from the current local console.

| Asset | Size | Purpose |
|---|---|---|
| `cover-en.svg`, `cover-tr.svg` | 1600 × 900 | Project identity and the choose → preview → past usage flow |
| `team-guide-en.svg`, `team-guide-tr.svg` | 1600 × 760 | Duties, model selection and recorded usage |
| `preferences-en.png`, `preferences-tr.png` | 1264 × 1105 (EN), 1264 × 1109 (TR) | Current planned-team console with chief settings selected |
| `console-en.png`, `console-tr.png` | 1264 × 1258 (EN), 1264 × 1274 (TR) | Current Usage orchestra, recorded models and token shares |

The illustrations reuse this repository's original orchestra character art.
Each SVG embeds its own symbols and gradients; it has no external images,
fonts or scripts. Colors follow the current console: dark burgundy and brown,
warm gold, cream text. The core palette is `#201619`, `#302124`, `#783238`,
`#E5BE7A`, and `#FFF1D9`.

For a related orchestrator repository, change the cover's product label and
translate the model families in the team guide to that product's actual
choices. The stage, characters and three-step composition are reusable.
Console screenshots belong to this Codex version and should be recaptured
from another product rather than relabeled.

Screenshots use the repository's sanitized usage fixture and a temporary,
empty Git project. No actual user session data or project paths appear.
To open the same console for a capture:

```sh
python3 scripts/dashboard.py /path/to/temporary-git-project \
  --sessions tests/fixtures/usage-sanitized --no-browser --port 8871
```

Use a 1600 × 1100 browser viewport, switch to the desired language, and
capture `.team-builder` in Preferences or `#orchestra-panel` in Usage.
The example model selection reflects the local catalogue at capture time;
it does not promise account access. Token values are sample historical
records. The older GIF/MP4 remains an illustrative short preview.
