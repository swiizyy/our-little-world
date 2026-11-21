# Install and operate Our Little World

[Version française](operations.fr.md)

GitHub contains the locked Packwiz files. Each published tag has a
`pack-manifest.json`, a downloadable `.mrpack` and client defaults. The
manifest points to a specific Git commit. Both PCs and the Docker server
should use the same release tag. Keep a private, independent backup of worlds
and player data before your first migration.

## Any Minecraft Java launcher with Fabric

### Direct Java launch hook

Put Packwiz Installer Bootstrap in the Fabric instance's game directory. Use
this pre-launch command to follow stable releases at a fixed URL. Without a
hook, run it from the game directory before playing.

```text
java -jar packwiz-installer-bootstrap.jar https://raw.githubusercontent.com/swiizyy/our-little-world/refs/heads/stable/pack.toml
```

Use Java 25 and a dedicated game directory with no existing mods on the
first Packwiz install. The stable branch advances after publication. Update
the server before launching both clients. Use the PowerShell method below
if you also want to seed the pack's other client defaults.

On instances without an `options.txt`, Default Options enables Faithful and
its add-ons in order. Existing instances keep their resource pack selection.

**One-time import.** Download `our-little-world.mrpack` from the desired
[GitHub release](https://github.com/swiizyy/our-little-world/releases) and
choose **Create instance → Import from file** in Modrinth App. If the launcher
asks about an external download, check that it matches the official URL in the
pack. The Packwiz setup below also works from a standalone game directory,
including launchers that cannot import `.mrpack`.

1. Create a fresh custom Fabric instance with the Minecraft and Fabric versions
   shown in the release notes. In the official Minecraft Launcher, install the
   [Fabric client profile](https://fabricmc.net/use/installer/) and edit its
   **Game Directory** to a dedicated folder. In Prism Launcher or Modrinth App,
   open the game folder of the new instance. Keep the
   old instance as a backup. If migrating, close Minecraft and copy only the
   player files you want such as `saves/`, `options.txt`, `servers.dat`, and
   personal configs or maps. Start with an empty `mods/` directory.
2. Save [the Windows script](../client/Sync-OurLittleWorld.ps1) and the official
   [Packwiz Installer Bootstrap v0.0.3](https://github.com/packwiz/packwiz-installer-bootstrap/releases/tag/v0.0.3)
   JAR locally. Use Java 25 and set `-Java` to the full path of `java.exe` if
   your Windows PATH points to another Java version. Read the downloaded script
   before unblocking it with `Unblock-File` if Windows marks it as downloaded.
3. Run the following command in PowerShell before pressing **Play**. Replace the
   paths and tag with yours. For automatic sync, add the same command as a
   pre-launch hook when your launcher supports one.

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "C:/OLW/Sync-OurLittleWorld.ps1" -InstancePath "C:/path/to/instance" -BootstrapJar "C:/OLW/packwiz-installer-bootstrap.jar" -Java "C:/path/to/java.exe" -Tag v0.1.0
```

| Launcher | Before Play |
| --- | --- |
| Modrinth App | Instance settings → Launch hooks → Pre-launch |
| Prism Launcher | Edit instance → Settings → Custom Commands → Pre-launch command |
| Official Minecraft Launcher or other launchers | Run the command yourself, wait for success, then launch the Fabric profile using that game directory. |

On macOS or Linux, use PowerShell 7 and run
`pwsh -NoProfile -File ./Sync-OurLittleWorld.ps1 -InstancePath "/path/to/game" -BootstrapJar "/path/to/bootstrap.jar" -Tag v0.1.0`
with Java 25 on the PATH.

The script verifies the release and runs Packwiz, which installs or updates
client mods and removes obsolete files it
previously managed. Keep `packwiz.json`. Avoid using the app's mod updater or
adding independent mods in this instance. The script copies visual defaults
only when the destination file is missing. It leaves saves, account data,
key bindings, audio and video preferences alone.

During a server upgrade, change `-Tag` on **both** PCs to the release selected
by the operator before reconnecting. Omitting `-Tag` follows the latest
stable release at every launch. Use this mode only when the server rollout
follows the same release or for LAN play. If Minecraft or Fabric changes,
update the instance and the script's `-Minecraft` / `-Fabric` arguments together.
For rollback, go back to the server's previous tag. Before opening a local
world with older mods, restore a compatible copy.

## Docker on Apple Silicon

Install Docker with Compose v2 and Python 3.12+. Allow Docker more than 12 GB
of RAM so Java and the VM have room outside the 12 GB heap. From `server/`:

```sh
cp .env.example .env
chmod 600 .env
# Set EULA=TRUE, choose a private RCON password and enter the two Minecraft usernames.
python3 deploy.py check
python3 deploy.py apply --tag v0.1.0  # example, replace with an actual stable tag
docker compose --env-file .env --env-file .pack.env logs -f minecraft
```

The container uses Fabric and automatically selects the server side of the
Packwiz index. Persisted data and server configs live in `server/data/`. Allow
TCP 25565 for Minecraft and UDP 24454 for Simple Voice Chat only where the
players connect. RCON runs inside Docker. To use it locally, run
`docker compose --env-file .env --env-file .pack.env exec minecraft rcon-cli list`.
Voice Chat on a dedicated server uses UDP directly. Keep an existing custom
voice-chat bind or port setting and adjust Compose/firewall as needed.

### Migrate a running server

1. Schedule downtime and gracefully stop the old server. Take a full offline
   backup of its data and Compose settings, and keep that backup independently
   from the new server.
2. Copy the old data into `server/data/`. Keep the same `LEVEL` and reproduce the
   player whitelist and required settings in the new local `.env`. Review
   Compose's settings against your current MOTD, ports and whitelist.
3. If the copy was not previously managed by Packwiz, move the copied
   `data/mods/` directory outside `data/` for safekeeping. Packwiz will install
   the locked list. Check world-critical mods from the old installation on a
   separate copy before opening the migrated world. Keep any required mods
   through a reviewed Packwiz change.
4. Apply the desired version and check the logs, world, whitelist and voice
   with both players.

### Update and restore

A local scheduler on the Mac can run `python3 deploy.py check` to discover the
latest stable tag and report it to the operator. This check never changes the
server. For automated application in an approved offline window, schedule
`deploy.py apply` after the scheduled stop and only after scheduling notice
to both players. The script refuses to apply while the service is active.
GitHub Actions publishes the release and never connects to Docker.

1. Announce maintenance and wait for both players to disconnect. Stop with
   `docker compose --env-file .env --env-file .pack.env stop`.
2. Run `python3 deploy.py apply --tag v0.1.1` with the chosen stable tag.
   The script verifies the descriptor, snapshots `data/` and the previous
   release settings, stages installation in an isolated temporary directory,
   then starts the live service and waits for health. If health fails, it
   preserves the failed data and restores the previous snapshot. Allow disk
   space for multiple copies of the world.
3. To roll back later, stop the service, run
   `python3 deploy.py restore backups/snapshot-EXAMPLE`, then start via
   `docker compose --env-file .env --env-file .pack.env up -d --wait`.
   Restoring a snapshot reverts play since that snapshot. The previously active
   data is retained under `backups/recovery-*/previous-data`. For a snapshot
   before the first deployment, use the original Compose to restart, or apply
   a known compatible Packwiz tag. Keep separate backups of `.env`.

## Troubleshooting

- **Release or hash unavailable** — confirm that the tag includes
  `pack-manifest.json` and `client-defaults.zip`. Retry after a network error.
  If hashes keep failing, select the last working tag and report the file and
  release to the maintainer.
- **Client will not launch** — run the hook command manually to see its output.
  Check the paths, Java version, Fabric version and instance directory. Reuse
  the same Packwiz ownership file. A clean instance can be used to isolate
  problems without touching the old instance.
- **Voice chat will not connect** — check the server's UDP 24454 forwarding,
  the voice-chat server configuration and the selected microphone.
- **Server unhealthy** — check Compose logs and the backup path printed by
  the deployment script. Confirm available memory and disk space. Inspect
  the retained data separately before retrying a failed upgrade.
