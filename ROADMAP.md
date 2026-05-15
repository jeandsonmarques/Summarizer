# ROADMAP

## Objective for the next version

Deliver a stable beta-to-release path for Summarizer, keeping `main` protected as the stabilized line and using `develop` for ongoing work before publication in QGIS.

## Planned improvements

- polish the Summary and Reports user experience without changing core behavior;
- continue small visual and usability refinements in charts, tables, dialogs, and tooltips;
- improve release packaging and validation checks;
- strengthen documentation for installation, release, and contribution flow;
- reduce friction in common analyst workflows such as connections, report generation, and dashboard review.

## Future refactors

- isolate repeated UI helpers where the code can be simplified safely;
- continue consolidating shared rendering and formatting logic;
- review release automation for clearer validation and packaging steps;
- keep compatibility-sensitive areas stable unless a change is explicitly planned and tested.

## Criteria to ship to QGIS

- `main` is clean and tagged as release-ready;
- compile, test, and lint checks pass;
- the release ZIP is generated outside the repository root;
- the package contains the expected plugin structure and required assets;
- no temporary files, caches, or local paths are included in the release;
- manual verification on QGIS confirms the plugin opens and the main workflows still work.

## Criteria to leave beta

- no known release-blocking bugs remain open;
- the main user flows are stable in QGIS on the supported versions;
- release packaging is repeatable and documented;
- the last round of fixes has been validated on a clean checkout and a packaged ZIP;
- the team agrees the next release can be treated as stable for broader use.

## Branching rule

- do not develop directly on `main`;
- keep `main` as the stabilized branch;
- do active work on `develop`;
- use `feature/*` for new tools or enhancements;
- use `hotfix/*` for urgent fixes;
- use `release/*` when preparing a publication.
