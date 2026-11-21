# Installer et exploiter Our Little World

[English version](operations.md)

Chaque release GitHub publie un `.mrpack`, des réglages initiaux client et un
`pack-manifest.json` qui pointe vers les fichiers Packwiz d'un commit précis.
Utilisez le même tag sur le serveur et les deux PC.

## Installer et synchroniser avec un launcher Minecraft Java compatible Fabric

### Pré-lancement direct avec Java

Placez le bootstrap Packwiz dans le dossier de jeu de l'instance Fabric. Dans
le hook de pré-lancement, utilisez cette commande pour suivre la branche stable
sans changer l'URL. Sans hook, exécutez-la depuis le dossier de jeu avant de jouer.

```text
java -jar packwiz-installer-bootstrap.jar https://raw.githubusercontent.com/swiizyy/our-little-world/refs/heads/stable/pack.toml
```

Utilisez Java 25 et un dossier dédié, vide de mods pour la première installation
si Packwiz ne le suit pas encore. La branche stable avance après publication.
Mettez le serveur à jour avant de lancer les deux instances. Pour copier aussi
les réglages initiaux sans remplacer vos fichiers, utilisez la méthode
PowerShell ci-dessous.

Pour une installation ponctuelle, téléchargez `our-little-world.mrpack` depuis
les [releases GitHub](https://github.com/swiizyy/our-little-world/releases).
Dans Modrinth App, créez une instance en choisissant **Importer depuis un
fichier**. Vérifiez l'origine des téléchargements externes si l'application
vous demande de les autoriser. Si votre launcher ne sait pas importer les
`.mrpack`, installez directement le pack avec la méthode ci-dessous.

Pour les mises à jour à chaque lancement, créez une **instance Fabric
personnalisée** avec les versions Minecraft et Fabric de la release. Ouvrez
son dossier depuis Modrinth App ou Prism Launcher. Dans le launcher Minecraft
officiel, installez [le profil Fabric client](https://fabricmc.net/use/installer/),
puis indiquez un dossier de jeu dédié dans les paramètres du profil.
En cas de migration, conservez l'ancienne
instance et copiez uniquement vos données personnelles, comme les sauvegardes,
`options.txt`, `servers.dat`, les cartes et les préférences. Le dossier
`mods/` de la nouvelle instance doit être vide.

Enregistrez [le script Windows](../client/Sync-OurLittleWorld.ps1) et le
[bootstrap Packwiz officiel](https://github.com/packwiz/packwiz-installer-bootstrap/releases/tag/v0.0.3)
sur le PC. Utilisez Java 25. Lisez le script avant de le débloquer avec
`Unblock-File` si Windows l'a marqué comme téléchargé. Lancez la commande
suivante dans PowerShell avant de jouer. Adaptez les chemins et le tag.

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "C:/OLW/Sync-OurLittleWorld.ps1" -InstancePath "C:/chemin/instance" -BootstrapJar "C:/OLW/packwiz-installer-bootstrap.jar" -Java "C:/chemin/java.exe" -Tag v0.1.0
```

| Launcher | Avant de jouer |
| --- | --- |
| Modrinth App | Paramètres de l'instance → Launch hooks → Pre-launch |
| Prism Launcher | Modifier l'instance → Paramètres → Commandes personnalisées → Commande de pré-lancement |
| Launcher Minecraft officiel ou autre launcher | Lancez la commande, attendez sa réussite, puis cliquez sur **Jouer** dans le profil Fabric qui utilise ce dossier. |

Sur macOS ou Linux, utilisez PowerShell 7 avec Java 25 dans le PATH.
`pwsh -NoProfile -File ./Sync-OurLittleWorld.ps1 -InstancePath "/chemin/jeu" -BootstrapJar "/chemin/bootstrap.jar" -Tag v0.1.0`

Packwiz ajoute les mods client et retire uniquement les fichiers obsolètes
dont il assure le suivi. Gardez `packwiz.json` et évitez les mises à jour de mods
effectuées séparément dans Modrinth App. Les réglages visuels du pack sont
copiés uniquement s'il manque le fichier. Les sauvegardes, comptes, touches
et préférences vidéo ou audio sont conservés.

Avant de rejoindre le serveur après une mise à jour ou un retour arrière,
changez `-Tag` sur les deux PC. Sans cet argument, le script suit la dernière
release stable. Réservez ce mode au LAN ou à un serveur qui suit la même
release au même moment. En cas de changement de Minecraft ou Fabric, adaptez
l'instance et les arguments `-Minecraft` et `-Fabric`. Pour rouvrir un monde
local avec des mods plus anciens, utilisez une sauvegarde compatible.

## Déployer Docker sur le Mac mini

Installez Docker avec Compose v2 et Python 3.12+. Allouez à Docker plus de
12 Go de RAM pour laisser de la marge à Java et à la VM. Depuis `server/` :

```sh
cp .env.example .env
chmod 600 .env
# Renseigner EULA=TRUE, un mot de passe RCON local et les deux pseudos Minecraft.
python3 deploy.py check
python3 deploy.py apply --tag v0.1.0  # remplacer par un tag stable publié
docker compose --env-file .env --env-file .pack.env logs -f minecraft
```

Le conteneur installe uniquement les fichiers Packwiz applicables au serveur.
Le monde et les configurations serveur restent dans `server/data/`. Autorisez
TCP 25565 pour Minecraft et UDP 24454 pour Simple Voice Chat sur le réseau
utilisé par les joueurs. RCON est interne à Docker. Vérifiez la liste des
joueurs avec
`docker compose --env-file .env --env-file .pack.env exec minecraft rcon-cli list`.
Si votre ancien serveur utilise un port vocal personnalisé, conservez la
configuration du mod et adaptez Compose et le pare-feu.

### Migrer un serveur existant

1. Prévoyez une maintenance, arrêtez proprement l'ancien serveur et conservez
   une sauvegarde indépendante de ses données et de ses réglages Compose.
2. Copiez ses données dans `server/data/`. Gardez le même `LEVEL`, renseignez
   la whitelist dans `.env` et vérifiez les ports.
3. Si l'ancien serveur ne passait pas par Packwiz, déplacez le dossier
   `mods/` de **la copie** hors de `data/`. Testez les différences de mods
   sur une copie du monde avant de servir le monde migré. Ajoutez à Packwiz,
   après validation, les mods réellement indispensables à votre monde.
4. Appliquez le tag et vérifiez le monde, la whitelist et le chat vocal
   avec les deux joueurs.

### Mettre à jour ou restaurer

Un planificateur local peut lancer `python3 deploy.py check` pour découvrir
la dernière release stable. GitHub Actions publie les fichiers sans joindre
le serveur. Pour automatiser l'application, planifiez `deploy.py apply`
pendant une fenêtre approuvée, après l'arrêt du serveur et après avoir prévenu
les joueurs. Le script refuse l'application si le service est actif.

1. Attendez la déconnexion des joueurs, puis lancez
   `docker compose --env-file .env --env-file .pack.env stop`.
2. Lancez `python3 deploy.py apply --tag v0.1.1` avec le tag voulu. Le script
   vérifie le descripteur, sauvegarde `data/` et la version précédente, teste
   l'installation dans un dossier temporaire, puis attend le healthcheck.
   En cas d'échec, il conserve les données de la tentative et restaure
   l'instantané précédent. Prévoyez de l'espace pour plusieurs copies du monde.
3. Pour restaurer un instantané plus tard, arrêtez le serveur et lancez
   `python3 deploy.py restore backups/snapshot-EXEMPLE`. Redémarrez via
   `docker compose --env-file .env --env-file .pack.env up -d --wait`.
   L'état du monde revient à la date de la sauvegarde. L'ancienne copie active
   reste dans `backups/recovery-*/previous-data`. Pour un instantané d'avant
   le premier déploiement, utilisez le Compose d'origine ou appliquez un tag
   compatible. Sauvegardez également `.env` à part.

## Dépannage

- **Le hook échoue** — lancez la commande dans PowerShell, vérifiez les chemins,
  Java, Minecraft et Fabric. Utilisez une instance vierge pour isoler le
  problème tout en conservant l'ancienne.
- **Release inaccessible ou hash incorrect** — confirmez que la release
  contient le manifeste et les réglages initiaux. Si l'erreur persiste,
  revenez au dernier tag fonctionnel et signalez le fichier concerné.
- **Chat vocal indisponible** — vérifiez UDP 24454, la configuration serveur
  de Voice Chat et le microphone choisi dans le jeu.
- **Serveur indisponible** — consultez les logs Compose et le chemin de
  sauvegarde affiché. Vérifiez la mémoire et l'espace disque avant de réessayer.

Pour ajouter un mod, actualiser le pack ou publier un tag, consultez le
[guide des contributions](../CONTRIBUTING.md).
