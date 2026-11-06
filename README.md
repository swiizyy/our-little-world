# Our Little World

Community Minecraft Java Cozy Adventure modpack.

Project foundations are developed on `dev` and reviewed into `main`.

## Modpack development

The modpack is managed with [packwiz](https://packwiz.infra.link/). Install the
packwiz CLI by following its [installation guide](https://packwiz.infra.link/installation/),
then run these commands from the repository root:

```sh
packwiz refresh
packwiz modrinth export
```

Add mods with `packwiz modrinth install <mod>` or `packwiz curseforge install <mod>`.
Run `packwiz refresh` after manually changing mod metadata or pack files so the
index and its integrity hash stay up to date. GitHub Actions refreshes the index on
every push and pull request and checks that no tracked Packwiz metadata changes
are needed.

### Optimization mods

The initial optimization baseline uses the 47 mod versions from
[Fabulously Optimized 15.0.0-beta.3](https://modrinth.com/modpack/fabulously-optimized/version/FLkaba1E)
for Minecraft 26.3 and Fabric 0.20.1. Packwiz metadata links to the original
Modrinth files. Fabulously Optimized's resource packs and configuration overrides
are not included, so this is not an exact reproduction of that modpack.

To update these mods to the latest Fabulously Optimized version compatible with
the pack's Minecraft and Fabric versions, run:

```sh
python3 -m pip install -r scripts/requirements.txt
python3 scripts/sync_fabulously_optimized.py
```

The script requires Python 3.9+ and Packwiz. It chooses the most recent upstream
release using the exact Minecraft and Fabric loader versions in `pack.toml`,
including beta and alpha releases. It checks the upstream archive's SHA-512 hash,
installs the exact upstream mod versions, and refreshes the pack index. It keeps
mods that are no longer in Fabulously Optimized, as well as locally added mods.
Updated mods' Packwiz metadata is regenerated; review the resulting changes
before releasing.

The **Sync Fabulously Optimized** workflow also checks daily at 04:23 UTC and
opens or updates a pull request against the default branch when there are mod
changes. It can be started manually from GitHub Actions. Scheduled workflows
run only when the workflow exists on the default branch; the current default is
`dev`. Enable **Allow GitHub Actions to create and approve pull requests** in
repository Settings → Actions → General → Workflow permissions. The pull request
must be reviewed and merged before the updates become part of the pack; the
workflow does not create a release. The sync job runs the tests and verifies the
refreshed index before opening the pull request. Pull requests created with
`GITHUB_TOKEN` do not automatically trigger other workflows, so run any
additional required validation separately before merging. GitHub may delay
scheduled runs or disable them after prolonged repository inactivity.

The CurseForge export embeds mods without CurseForge metadata as JARs. Their
redistribution permissions and CurseForge approval have not been verified; do not
run or publish that export until they have been reviewed. The release workflow
currently exports and uploads it automatically, so do not trigger that workflow
with these mods until the review is complete.

### Releasing

To create a version with a click, open **Actions → Release modpack → Run
workflow**, choose `stable`, `beta`, or `alpha` (default: `beta`), then run it.
The workflow generates a unique version and creates a GitHub Release with both
downloadable pack formats.

Push a semantic-version tag such as `v0.1.0` or `v0.2.0-beta.1` to create a
GitHub Release with downloadable Modrinth `.mrpack` and CurseForge `.zip` files.
Tags ending in `-alpha...` publish as alpha; other prerelease tags publish as
beta; tags without a prerelease suffix publish as stable releases.

Push to the `stable`, `beta`, or `alpha` branch to create a uniquely versioned
continuous build, downloadable from the GitHub Actions run. The matching branch
sets the platform release channel.

To publish to Modrinth, add the `MODRINTH_TOKEN` repository secret and the
`MODRINTH_PROJECT_ID` repository variable. To publish to CurseForge, add the
`CURSEFORGE_API_TOKEN` secret and the `CURSEFORGE_PROJECT_ID` variable. Without
either platform's values, the workflow still creates the downloadable
GitHub release or Actions artifact.
