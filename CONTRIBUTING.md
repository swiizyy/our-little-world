# Contributing to Our Little World

The pack is maintained with [Packwiz](https://packwiz.infra.link/). Open
changes against `dev` for review. Install the
[Packwiz CLI](https://packwiz.infra.link/installation/), then run these
commands from the repository root.

```sh
# Add a mod from Modrinth
packwiz modrinth install <mod>

# Refresh the index after manually changing pack files
packwiz refresh

# Verify the index locally (Python 3.12+)
python scripts/validate_pack.py

# Validate downloads and export release artifacts into dist/
python scripts/build_pack.py
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
uses a darker tooltip background for better contrast against bright blocks,
and Zoomify eases in over 180 ms and out over 220 ms. InventoryHUD+ uses a compact inventory display
with a softened background that disappears when the inventory is empty. JEI's
ingredient and bookmark lists are limited to six columns, leaving more room
around the inventory.
These settings do not change survival balance or world generation. BetterGrassify
already defaults to fancy grass and Lambda-style snow, so it needs no override.

JEI's pack defaults live in `config/jei/client/default/jei-client.ini` and can
be overridden by the player's own JEI client settings. InventoryHUD+ reads
`config/inventoryhud.json` directly; its options can be adjusted in game.

Xaero's Minimap and World Map starter profiles are in `defaultconfigs/xaero/`.
They keep Waystones visible, set minimap waypoint opacity to 65%, and enable blended
biome colors and the hovered-biome label on the world map. Xaero copies these
profiles into its config directory on first launch; existing local profiles are
left untouched.

Unified Xaero Worldmap shares explored map areas between players. It is included
for both sides, so multiplayer servers and every player need to use the pack's
same mod version for map synchronization. Its author has permitted its use in
this modpack, but has not permitted re-uploading the mod to Modrinth; the
Packwiz metadata therefore keeps the official CurseForge download URL.

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

## Editing the pack

- Add a reviewed mod with `packwiz modrinth install <mod>`. For selected
  updates use `packwiz update <mod>`, then review the exact version, hashes,
  side and dependencies. To remove a mod, remove its metadata and review
  any libraries that other mods may still need.
- Run `packwiz refresh` and `python scripts/build_pack.py` before opening a PR
  to `dev`. Commit the refreshed index and pack descriptor with the metadata
  change. On Windows, replace `python` with `py -3.12` if appropriate. If an
  existing Windows checkout reports only hash changes after refresh, normalize
  the indexed files to LF as specified in `.gitattributes` before continuing.
- Keep client-only defaults under `config/` and `defaultconfigs/`. The build
  adds tracked defaults to the Modrinth client overrides and the Windows seed
  archive. The Windows script preserves existing files. Server configs remain
  local in `server/data/`. Discuss a destination and migration policy before
  introducing a file that needs to be enforced on both sides.

## Releasing

1. Set `version` in `pack.toml` before merging the release candidate. Use a
   plain version for stable releases, or a suffix such as `-beta.1` /
   `-alpha.1` for previews. Run the same checks as the PR workflow.
2. Tag the reviewed commit with the exact version prefixed by `v`. For
   example, once `pack.toml` says `0.1.0`, run `git tag v0.1.0` and
   `git push origin v0.1.0`. Keep published tags on their original commits.
3. GitHub Actions produces the `.mrpack`, client defaults, manifest and
   changelog. The manifest and release notes link to the Packwiz file for
   that exact commit. Preview tags create prereleases. Branch and PR builds
   appear in the validation artifacts. Stable deployment follows stable tags.
4. Update the server and both PCs using the
   [operations guide](docs/operations.md) or [guide français](docs/operations.fr.md).

GitHub Releases uses the workflow's built-in token. GitHub hosts the release
assets, and Modrinth App can use the local archive or the Packwiz launch hook.
Server credentials stay on the Mac. [MODRINTH.md](MODRINTH.md) contains the
player-facing description.

## Publier et contribuer en français

Pour ajouter un mod, utilisez `packwiz modrinth install <mod>`. Pour actualiser
un seul mod, utilisez `packwiz update <mod>` et vérifiez la version, les
dépendances et le côté. Pour en retirer un, supprimez son fichier `.pw.toml`
et vérifiez les dépendances des autres mods. Exécutez `packwiz refresh`, puis
`python scripts/build_pack.py`. Incluez le nouvel index dans la PR vers `dev`.

Pour publier, modifiez la version dans `pack.toml`, faites valider le commit,
puis poussez le tag correspondant avec le préfixe `v` (par exemple `v0.1.0`).
Les suffixes `-alpha.1` et `-beta.1` produisent des préversions. Les builds de
branche restent des artefacts de CI. La release stable fournit le manifeste et
les fichiers utilisés dans le [guide de déploiement](docs/operations.fr.md).
GitHub héberge les fichiers de release. Téléchargez le `.mrpack` pour
l'importer dans Modrinth App ou installez le pack avec le hook Packwiz.
