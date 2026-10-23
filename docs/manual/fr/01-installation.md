# 1. Installation

[Sommaire](README.md)

## Environnement et prérequis

Sous Windows, Koha fonctionne dans Debian avec WSL 2. Les outils Windows préparent cet environnement, ouvrent le panneau et intègrent l’application. Sous Debian ou Ubuntu, services et panneau sont installés directement. Pour accéder à un catalogue existant, ouvrez le panneau ; ne relancez pas l’installation.

| Environnement | Contrôles du code |
| --- | --- |
| Windows | Windows 10 version 2004, build 19041 ou ultérieur, ou Windows 11 ; 64 bits, virtualisation activée ; 8 Go de RAM, 12 Go recommandés ; 10 Go libres sur le disque d’installation, 20 Go recommandés. |
| Debian/Ubuntu | Debian 11/12/13 ou Ubuntu 22.04/24.04 ; amd64 et arm64 identifiés par l’installateur ; moins de 5 Go bloque, de 5 à moins de 10 Go produit un avertissement, 10 Go ou plus satisfait ce contrôle. |

Le catalogue, les pièces jointes, les index et les backups demandent de l’espace supplémentaire. **RAM Linux, à confirmer :** le guide recommande 4 Go sur serveur dédié, 8 Go conseillés ; sur poste de travail ou environnement virtualisé, 8 Go et 12 Go conseillés. Le contrôle Linux n’impose actuellement aucun seuil numérique de RAM ; le réussir ne garantit pas la capacité pour toute charge. Windows tient compte de mémoire réservée au matériel : seuils détectés 7,5 et 11,5 Go.

Linux exige des droits administratifs et l’accès au dépôt Koha. Les ports TCP 80 et 8080 servent l’OPAC et le staff. S’ils sont occupés, le panneau propose d’arrêter les services concernés. **N’acceptez que si ces services peuvent être interrompus.**

## Windows : PowerShell

Connectez-vous au compte Windows administrateur qui utilisera Koha, puis ouvrez PowerShell en administrateur dans ce même compte :

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Si l’élévation demande le compte d’une autre personne, annulez et ouvrez une session appropriée : WSL appartient au compte d’installation. Lisez les contrôles et corrigez une virtualisation désactivée. Répondez dans la fenêtre aux questions du compte Debian, distinct du compte bibliothécaire Koha.

Attendez WSL 2 et Debian. Un redémarrage demandé enregistre la reprise à la prochaine connexion Windows. Dans le panneau, choisissez la langue puis **Install Koha server**. Après son achèvement, quittez normalement le panneau et attendez la fin de l’intégration Windows.

Le dossier par défaut est `C:\Koha` ; une ancienne installation peut garder `C:\KohaEasy`. Ne le déplacez pas pour réparer une interruption. Notez l’erreur : le programme conserve les étapes et peut reprendre ou rouvrir le panneau pour terminer le serveur. Cela ne rend pas une réinstallation destructive inoffensive.

## Windows : MSIX

Le MSIX prépare le même WSL ; le paquet installé ne signifie pas serveur et base configurés. Dans PowerShell **normal, sans élévation préalable** :

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

L’auxiliaire télécharge le paquet prévu dans son code, vérifie son origine, demande l’autorisation administrative et installe pour l’utilisateur actuel. Ne négligez aucun refus. Au premier lancement, attendez la préparation puis terminez l’installation guidée. Quittez normalement le panneau et laissez finir raccourcis, tâches et réseau Windows. Fermer avant la fin du serveur n’achève pas l’installation : rouvrez pour continuer.

**À confirmer :** disponibilité et adresse publique Microsoft Store ; le mode d’empaquetage ne prouve pas une publication. L’exécution complète MSIX sur ARM64 reste également à confirmer : le manifeste est x64, le support arm64 de Linux ne suffit pas. Le manifeste accepte un Windows plus ancien que le parcours WSL complet ; retenez les exigences complètes ci-dessus.

## Debian ou Ubuntu

Depuis le terminal du serveur :

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Pour garder le dépôt et ses traductions :

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Choisissez langue et **Install Koha server**. Corrigez les échecs critiques et lisez les avertissements : ils ne certifient pas toute charge. Une distribution WSL doit utiliser WSL 2 et systemd ; WSL 1 est refusé. Sous Windows, privilégiez la préparation guidée précédente.

## Installation dans le panneau

1. Ouvrez **Install Koha server**, attendez le précontrôle et lisez le rapport. Évaluez l’impact de libérer des ports occupés.
2. Vérifiez l’ordinateur cible avant de confirmer ; acceptez le fuseau ou choisissez région et ville.
3. **Instance existante : arrêtez-vous pour vérifier.** La réinstallation efface base et configuration, avec confirmation supplémentaire et mot exact `REINSTALL`. Elle ne sert pas simplement à ouvrir ou mettre à jour le panneau.
4. Attendez sans fermer : l’installation n’est pas annulable. Les 10 à 30 minutes estimées dépendent du matériel et du réseau.
5. Lisez le résultat et le rapport proposé ; une fin avec incidents n’atteste pas des services sains. Envisagez le redémarrage proposé et, en MSIX, attendez aussi la continuation Windows.

Ne recopiez pas les données privées du résultat dans des documents publics ou demandes d’assistance.

## Sources vérifiées

- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [installer](../../../installer).
- [README.md](../../../README.md).
- [install.ps1](../../../windows/install.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [instalar_msix.ps1](../../../windows/msix/instalar_msix.ps1).
- [KohaMsixEntry.cs](../../../windows/msix/KohaMsixEntry.cs).
- [KohaMsixPanel.ps1](../../../windows/KohaMsixPanel.ps1).
- [compilar_msix.ps1](../../../windows/msix/compilar_msix.ps1).
- [install.py](../../../panel/kei_panel/routines/install.py).
