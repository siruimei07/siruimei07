# Profile maintenance

This repository powers [siruimei07's GitHub profile](https://github.com/siruimei07).

## Banners

Add images to `banners/originals/` and push to `main`. See [banner settings](banners/README.md) for crop positions and selecting a fixed image.

The default is a transparent APNG slideshow with a 12-second interval. The README uses a static fallback when the visitor requests reduced motion. Original image pixels are cropped directly; no generative image tools are used.

## Automatic updates

[Update profile](https://github.com/siruimei07/siruimei07/actions/workflows/profile.yml) runs daily at 10:17 UTC, on relevant pushes, or manually. Its optional `banner` input saves a new banner selection; leave it empty to keep the current setting.

The workflow builds banners, refreshes the public repository table, and renders the Metrics charts. It uses the automatically supplied repository `GITHUB_TOKEN`; no personal access token or extra repository secret is needed.

## Metrics

The charts use [lowlighter/metrics](https://github.com/lowlighter/metrics) source pinned to `366f8b9dfe3a59656c67d5dcad9950f59c9bc96d`. The necessary plugins and templates are stored in `scripts/metrics/vendor/`, with licenses, provenance, and SHA-256 checks. The adapter supplies publicly available data to those renderers.

- Calendar: rolling half year of contributions visible on the public GitHub profile, including any anonymous private-contribution counts the account has chosen to make public. This measures contributions, not only commits.
- Languages: GitHub's language byte totals across owned, public, non-fork repositories, excluding this Profile repository. Percentages describe code volume, not proficiency.
- Repository list: all owned public repositories, including labeled forks, excluding this Profile repository.

Calendar pages are fetched anonymously. Language and repository requests use public REST endpoints. If source parsing or rendering fails, the workflow keeps the last published charts.

To regenerate locally, use Node.js 22+, Python 3.12+, and Chrome or Chromium:

```powershell
python -m pip install Pillow==12.3.0
npm ci --prefix scripts/metrics --ignore-scripts
python scripts/build_banner.py
python scripts/update_repositories.py
$env:METRICS_OUTPUT_DIR = 'assets'
node scripts/metrics/render.mjs
```

Set `PUPPETEER_EXECUTABLE_PATH` if Chrome is installed in a nonstandard location. The renderer can also use `GITHUB_TOKEN` to increase the API rate limit; a local token is optional.
