# Contributing to Our Little World

The pack is maintained with [Packwiz](https://packwiz.infra.link/). Development
happens on `dev`, with changes reviewed into `main`. Install the
[Packwiz CLI](https://packwiz.infra.link/installation/), then run commands from
the repository root:

```sh
# Add a mod from Modrinth
packwiz modrinth install <mod>

# Refresh the index after manually changing pack files
packwiz refresh

# Export a Modrinth modpack
packwiz modrinth export
```

Commit the updated `pack.toml` and `index.toml` alongside pack changes. GitHub
Actions checks that the index is up to date on pushes and pull requests.

## Optimization baseline

The original optimization baseline uses the 47 mod versions from
[Fabulously Optimized 15.0.0-beta.3](https://modrinth.com/modpack/fabulously-optimized/version/FLkaba1E)
for Minecraft 26.3 and Fabric 0.20.1. Packwiz metadata links to the original
Modrinth files. Fabulously Optimized's resource packs and configuration overrides
are not included, so this is not an exact reproduction of that modpack.

The pack also includes 20 additional mod versions imported from the local
Our Little World — Cozy Edition 1.0.0 modpack. Existing optimization mod versions
and Fabric 0.20.1 were retained where they differed from that archive. Its
resource packs, shaders, and configuration overrides were not imported.

Traveler's Backpack and Storage Drawers are additional gameplay mods selected
for Minecraft 26.3; they are not managed by the Fabulously Optimized sync
script. Simply Cozy - Halloween Update is also included in the pack.

Voice Bridge for e4mc is a small multiplayer compatibility mod outside that
sync. It routes Simple Voice Chat through an e4mc-hosted world, avoiding the
separate UDP port that voice chat normally requires. Keep it in the pack with
e4mc and Simple Voice Chat so the documented quick-hosting flow keeps working.

InventoryHUD+ and JEI provide client-side inventory and recipe information.
JEI's required MezzConfig library is included automatically by Packwiz.

Faithful 64x is a client-side resource pack distributed through Modrinth. Its
Ore Borders 64x add-on is downloaded from the author's GitHub release. Players
can also use Clear Glass for less obstructed glass and Visual Waxed Copper
Items to identify waxed copper in their inventories. They enable the packs
manually in Minecraft's resource pack menu, with add-ons above Faithful,
preserving their existing options. See `CREDITS.txt` for attribution and
license information.

The current pack includes a small set of client-side visual overrides in
`config/`: Sodium uses alternative fluid shaping for more consistent-looking
water around waterlogged builds while keeping crisp pixel textures, and
LambDynamicLights keeps fancy lighting and illuminated entities/fireflies. Jade
uses its dark tooltip theme with slightly softened opacity, and Zoomify uses
smooth, short zoom transitions. InventoryHUD+ uses a compact inventory display
with a softened background that disappears when the inventory is empty. JEI's
ingredient and bookmark lists are limited to six columns, leaving more room
around the inventory.
These settings do not change survival balance or world generation. BetterGrassify
already defaults to fancy grass and Lambda-style snow, so it needs no override.

JEI's pack defaults live in `config/jei/client/default/jei-client.ini` and can
be overridden by the player's own JEI client settings. InventoryHUD+ reads
`config/inventoryhud.json` directly; its options can be adjusted in game.

Xaero's Minimap and World Map starter profiles are in `defaultconfigs/xaero/`.
They keep Waystones visible, soften minimap waypoint markers, and enable blended
biome colors and the hovered-biome label on the world map. Xaero copies these
profiles into its config directory on first launch; existing local profiles are
left untouched.

Unified Xaero Worldmap shares explored map areas between players. It is
temporarily excluded from the pack while distribution permission is confirmed.
If it is restored, multiplayer servers and every player will need to use the
pack's same mod version for map synchronization.

The minimap profile also displays tracked players on both maps. Xaero can only
show positions shared by the server or a supported party/tracking integration;
these client settings do not enable server-side tracking.

## Syncing optimization mods

To sync with the latest Fabulously Optimized release using the exact Minecraft
and Fabric versions in `pack.toml`:

```sh
python3 -m pip install -r scripts/requirements.txt
python3 scripts/sync_fabulously_optimized.py
```

The script requires Python 3.9+ and Packwiz. It includes upstream beta and
alpha releases, checks the upstream archive's SHA-512 hash, installs the exact
upstream mod versions, and refreshes the index. Mods removed upstream and
locally added mods are retained. Updated mods' Packwiz metadata is regenerated;
review the changes before releasing.

The **Sync Fabulously Optimized** workflow checks daily at 04:23 UTC and opens
or updates a pull request against the default branch when there are mod
changes. It can also be started manually from GitHub Actions. It runs tests and
checks the refreshed index but does not merge or publish a release.

For scheduled checks, the workflow must exist on the default branch, currently
`dev`. Enable **Allow GitHub Actions to create and approve pull requests** in
repository Settings → Actions → General → Workflow permissions. Pull requests
created with `GITHUB_TOKEN` do not automatically trigger other workflows, so
run any additional required validation separately before merging. GitHub may
delay scheduled runs or disable them after prolonged repository inactivity.

## 🚀 Releasing

From **Actions → Release modpack → Run workflow**, select a branch and the
`stable`, `beta`, or `alpha` channel (default: `beta`). The workflow generates
a unique version and creates a GitHub Release containing the `.mrpack`.
Release notes are generated from commit subjects since the previous reachable
tag and used for both the GitHub Release and the Modrinth version changelog.

Alternatively:

- Push a semantic-version tag such as `v0.1.0` or `v0.2.0-beta.1` to create a
  GitHub Release. Tags with an `-alpha...` suffix use the alpha channel; other
  prereleases use beta; tags without a prerelease suffix use the release channel.
- Push to the `stable`, `beta`, or `alpha` branch to produce a uniquely
  versioned build as a downloadable GitHub Actions artifact.

To publish to Modrinth, configure the `MODRINTH_TOKEN` repository secret and
the `MODRINTH_PROJECT_ID` repository variable. Without both, the GitHub Release
or Actions artifact is still created. The [Modrinth description](MODRINTH.md)
is ready to copy to the project page; upload [the icon](assets/icon.png)
separately in Modrinth's project settings.
