# Profile maintenance

This repository powers [siruimei07's GitHub profile](https://github.com/siruimei07).

## Design system

The README matches the owner's website, [siruimei07.github.io](https://github.com/siruimei07/siruimei07.github.io), a Rhine Lab-style "Analysis OS". `scripts/rhine.py` holds the shared drawing kit: the website's palette tokens for the section headers, the fonts in `banners/fonts/`, the ∞± mark, black tags and corner brackets. Every drawing is supersampled and composited through its own alpha layer, so transparent images blend cleanly into either GitHub theme.

## Opening panel

The panel above the image banner plays once for about 13 seconds and holds the `WELCOME TO / SIRUI MEI / PERSONAL DATABASE` frame. Its motion follows the website's opening (`src/boot/` there), using the measured tracks ported to `scripts/boot_tracks.py`: ACCESS PERMISSION REQUIRED typed in bursts, the ∞± mark drawn along one contour, `ID CONFIRMED : VISITOR` / `REQUEST RECEIVED` / `START PROCESSING...`, and the PERMISSION AUTHORIZED rings. Pauses are shortened to fit a README visit. The panel itself stays minimal: flat paper, two faint ∞ outlines, the name in Barlow without a bar. Light and dark versions follow the visitor's color scheme; reduced-motion preferences select the still.

The sequence is a decorative introduction; it does not check identity or authenticate access.

Settings are in `banners/loading/config.json` (see [its README](banners/loading/README.md)). `scripts/build_loading.py` writes `assets/loading-light.png`, `assets/loading-dark.png`, `assets/loading-static-light.png`, and `assets/loading-static-dark.png`; optional `--config` and `--output-dir` arguments support alternate settings and output folders. Each theme's frames share one 256-color palette that reserves the panel colors and their anti-aliasing ramps.

## Section headers

`scripts/build_sections.py` renders the README's section headers (the website's home callouts) from `banners/sections/config.json` into `assets/sections/`, as transparent 2x PNGs in light and dark versions. See [its README](banners/sections/README.md).

## Banners

Add images to `banners/originals/` and push to `main`. See [banner settings](banners/README.md) for crop positions and selecting a fixed image.

The default is a transparent APNG slideshow with a 5-second interval and a shuffled order. Every build shuffles all images once; that order repeats until the next build. The README uses the configured default image as a static fallback when the visitor requests reduced motion. Original image pixels are cropped directly; no generative image tools are used.

## Automatic updates

[Update profile](https://github.com/siruimei07/siruimei07/actions/workflows/profile.yml) runs daily at 10:17 UTC, on relevant pushes, or manually. Its optional `banner` input saves a new banner selection; leave it empty to keep the current setting.

The workflow runs the Python and Node checks, builds the opening panel, section headers and banners, refreshes the public repository table, and renders the Metrics charts. Calendar, languages, activity, and the repository list use public data with the automatically supplied repository `GITHUB_TOKEN`. Traffic uses an optional `TRAFFIC_TOKEN` secret because GitHub restricts analytics to people with repository access.

## Metrics

The charts use [lowlighter/metrics](https://github.com/lowlighter/metrics) source pinned to `366f8b9dfe3a59656c67d5dcad9950f59c9bc96d`. The necessary plugins and templates are stored in `scripts/metrics/vendor/`, with licenses, provenance, and SHA-256 checks. The adapter supplies public data and authenticated traffic counts for the selected public repositories.

The cards are styled after the website's ACTIVITY LOG screen without changing any vendored file: `scripts/metrics/theme.mjs` supplies per-theme CSS (black tags with a Chinese gloss and a mono readout, ■ labels, the command-log event list, frames with corner squares), recolors the isometric calendar from grey to ink with the best day in orange, gives languages a lime-then-ink ramp, and rewrites each heading through guarded, exactly-once replacements that fail the run if the upstream markup drifts. The traffic card uses the profile-owned `scripts/metrics/templates/traffic.ejs`. Cards shown side by side in the README (`PAIRS` in `render.mjs`: calendar with languages, activity with traffic) are rendered at a common height; update `PAIRS` if the README pairs them differently.

An SVG shown as an image loads no web fonts, so the cards embed small WOFF2 subsets of Montserrat, JetBrains Mono and the Noto Sans SC glyphs used in their labels (`scripts/metrics/fonts/`, about 38 KB). `render.mjs` checks them against `scripts/metrics/fonts/provenance.json` and waits until they load before measuring. After changing a card label, regenerate them with `python -m pip install fonttools==4.60.1 brotli==1.2.0` and `python scripts/build_card_fonts.py`; the daily workflow does not need fontTools.

- Calendar: rolling half year of contributions visible on the public GitHub profile, including any anonymous private-contribution counts the account has chosen to make public. This measures contributions, not only commits. The pinned Metrics plugin ends at the previous UTC day and aligns the start to a Sunday; GitHub's native calendar can show a different range and the current incomplete day.
- Languages: GitHub's language byte totals across owned, public, non-fork repositories, excluding this Profile repository. Percentages describe code volume, not proficiency.
- Repository list: all owned public repositories, including labeled forks, excluding this Profile repository.
- Recent activity: five recent public events within the last 30 days, with timestamps in Toronto time. The adapter handles the reduced event payloads introduced by GitHub in 2025 before calling the pinned Metrics plugin.
- Repositories traffic: page views for the public repositories in the table, summed using the Metrics traffic plugin. The standalone card adds a daily chart and repository breakdown. It displays its actual measurement period and acquisition date; unique visitors are not summed across repositories.

Calendar pages are fetched anonymously. Language, activity, and repository requests use public REST endpoints. If source parsing or rendering fails, the workflow keeps the last published charts. If the traffic credential is missing or unavailable, the last successful, explicitly dated traffic snapshot is retained.

### Image updates and caching

The renderer writes canonical SVGs in `assets/`. After all charts render successfully, `scripts/metrics/publish.mjs` copies them to content-hashed filenames under `assets/metrics/` and updates every light/dark README image reference. Changed image bytes therefore get a new URL, avoiding stale browser or GitHub image caches. Unchanged charts keep the same URL. The current and previous version of each chart are retained so recently cached README pages can still load their images. The workflow commits the README and its matching images together.

### Enable daily traffic refresh

Create a [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new) for `siruimei07`. Choose only the public repositories listed in this profile and grant **Repository permissions → Administration → Read-only** (Metadata read access is automatic). Add it as an Actions repository secret named **`TRAFFIC_TOKEN`** in [this repository's secrets settings](https://github.com/siruimei07/siruimei07/settings/secrets/actions), then run **Update profile**. The profile repository's normal `GITHUB_TOKEN` cannot read traffic for the other repositories. When adding a new public repository, include it in the token's selected repositories as well.

The initial snapshot was acquired with the locally authenticated GitHub CLI. That CLI credential is never copied into the repository or GitHub Actions. To refresh manually using the CLI again, set `METRICS_TRAFFIC_USE_GH=1` only for the local rendering command. The committed snapshot contains only the selected public repositories' daily page-view counts.

To regenerate locally, use Node.js 22+, Python 3.12+, and Chrome or Chromium:

```powershell
python -m pip install Pillow==12.3.0
npm ci --prefix scripts/metrics --ignore-scripts
python -m unittest discover -s scripts -p "test_*.py"
python scripts/build_loading.py
python scripts/build_sections.py
python scripts/build_banner.py
python scripts/update_repositories.py
$env:METRICS_OUTPUT_DIR = 'assets'
node scripts/metrics/render.mjs
node scripts/metrics/publish.mjs
```

Set `PUPPETEER_EXECUTABLE_PATH` if Chrome is installed in a nonstandard location. The renderer can also use `GITHUB_TOKEN` to increase the API rate limit; a local token is optional.
