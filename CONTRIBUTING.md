# Contributing

## Branch flow

- `main` is the stable line and should represent code that is ready for release or already released.
- `develop` is the active development branch for the next beta cycle.
- `feature/*` branches are for new tools, enhancements, or larger scoped changes.
- `hotfix/*` branches are for urgent corrections that must be handled quickly.
- `release/*` branches are for final preparation before publishing a version.

## Working rules

- do not develop directly on `main`;
- keep changes small and focused;
- avoid mixing unrelated fixes in the same branch;
- validate functional changes with the available test and lint commands before opening a merge request or pull request;
- if a change affects packaging, verify the generated release files outside the repository root.

## Suggested workflow

1. create or update your branch from `develop`;
2. implement the change;
3. run the relevant checks;
4. review the diff for unintended changes;
5. merge back through the normal branch flow once the change is ready.

## Release discipline

- use `release/*` only when the version is close to publication;
- keep `main` reserved for stabilized code;
- merge tested work from `develop` into `main` only when the release is approved;
- prefer small follow-up hotfixes over broad unreviewed edits on the stable branch.
