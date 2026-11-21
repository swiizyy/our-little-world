# Distribution audit / Audit de distribution

The initial `dev` snapshot (`147c405`) had 75 mods, four resource packs and two
shader packs. Packwiz already pinned all 81 downloads. Validation refreshed
the index and opened the export, but did not independently verify downloads,
dependencies or the completeness of the archive. Release builds could change
the pack version after checkout, so a release tag alone could identify a tree
with a different Packwiz version.

Le dépôt ne contenait ni Compose ni procédure de migration. Les réglages
visuels étaient indexés comme fichiers communs et pouvaient être synchronisés
sur le serveur ou remplacer des réglages locaux. Windows pouvait aussi
modifier les fins de ligne des fichiers indexés. Les réglages deviennent des
valeurs initiales client, et Git conserve les octets LF du pack.

The download audit checked the 81 hashes locked in the audited snapshot. The
table records the versions examined at that time. Validation exceptions apply
only to the exact releases and dependency versions verified against the Fabric
manifests.

| Release | Modrinth declaration | Checked against the locked file |
| --- | --- | --- |
| Better Block Entities `wORq9rW6` | Requires Sodium version `aFVpk3tG` | Fabric accepts `>=0.9.3-beta.3`. The audit checked `v7Lw0h1m`, 0.9.3-beta.5. |
| Iris `vTN4NRGW` | Requires Sodium version `bAZQdGpg` | Fabric accepts `0.9.x`, including the locked Sodium. |
| Config Manager `okecULrz` | Requires Mod Menu | The JAR does not require Mod Menu. The pack still includes Mod Menu on the client. |
| Zoomify `RUBpNu00` | Requires project `1vrSzlao` (Kotlin Lang Forge) | The Fabric JAR requires YACL, which the pack provides. Modrinth marks Zoomify's server side unsupported. Packwiz now marks it as client-only. |
| MixinTrace Reborn `j3SeQVjR` | Does not list Minecraft 26.3 | The locked Fabric JAR declares Minecraft `26.x`. |

La CI contrôle les dépendances requises et incompatibilités publiées sur
Modrinth, ainsi que les côtés, les identifiants et la présence des dépendances
Fabric, y compris les bibliothèques embarquées. Ces contrôles statiques ne
résolvent pas toutes les plages de versions Fabric et ne détectent pas les
conflits de mixins ou de gameplay.

Unified Xaero Worldmap remains an external download from the official
CurseForge CDN. Faithful, its add-ons and Sildur's shaders stay on their
official download hosts. See [credits and licenses](../CREDITS.txt).

GitHub hosts the full pack, including the manifest that references these
official downloads. If a launcher refuses an external download on local
import, install the pack with the Packwiz launch hook.
