# 2. Premiers pas et panneau

[Sommaire](README.md)

## Ouvrir et naviguer

Sous Debian/Ubuntu préparé par l’installateur :

```bash
sudo config.sh
```

Sous Windows, utilisez l’icône **Koha** ou Koha.Nexus installé par MSIX. Le premier lancement peut demander la langue. En cas d’échec de préparation Textual, le mode classique peut être proposé. Ce manuel décrit surtout Textual ; les numéros d’un ancien menu ne s’y appliquent pas.

Dans la barre latérale, surlignez avec les flèches puis **Enter**, ou cliquez. Le simple déplacement ne lance pas l’action. Ouvrez la carte et lisez les questions. **Tab** déplace le focus ; quittez un champ de texte avant les raccourcis de lettres.

| Touche | Action |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Terminal Debian |
| `Ctrl+B` | Afficher/masquer la barre latérale |
| `q` | Quitter le panneau |

Quitter le panneau au repos n’arrête pas le serveur. Pour un travail en cours, respectez ses possibilités d’annulation. Installation et restore ont des étapes non annulables ; fermer brutalement n’est pas sûr.

## Lire le tableau de bord

Il présente état Koha et mémoire disponible, dernier backup avec date/âge/fichier, disque libre, adresses d’accès et composants MariaDB, Apache, RabbitMQ, Memcached et Koha, avec contrôles HTTP.

L’indicateur de backup prend en compte âge et dernier résultat nocturne : fichier récent et exécution échouée peuvent coexister. Lisez les deux. Un voyant favorable ne remplace pas un test de restore. Une réponse HTTP ne prouve ni l’achèvement de l’assistant web Koha ni toutes les fonctions bibliothécaires.

**Refresh** relit l’état ; **Restart Koha** demande réparation/redémarrage en tenant compte des usagers ; **Export diagnostics** prépare les informations de support. Ces boutons peuvent manquer de disponibilité si l’installateur présent ne prend pas en charge la tâche.

## Adresses et démarrage de l’activité

Les cartes ouvrent ou copient les URL. Si aucun navigateur ne peut être lancé, collez l’adresse copiée dans celui de votre ordinateur. Par défaut, sur le serveur : OPAC `http://localhost/`, staff `http://localhost:8080/`, ports 80 et 8080.

Depuis un autre ordinateur, prenez l’adresse réseau indiquée, pas votre propre `localhost`. Si WSL utilise NAT et signale un réseau local inaccessible, vérifiez la préparation réseau Windows avec le responsable technique ; n’en déduisez pas un accès universel.

Si le staff affiche l’assistant web Koha, terminez-le avant d’exploiter la collection ; les écrans varient selon version. Ensuite **Create super librarian** sous **Koha settings & parameters** ouvre la création du compte ; saisissez les données privées seulement dans l’installation.

Avant l’activité, actualisez le dashboard, contrôlez composants/adresses, ouvrez OPAC et staff depuis le bon poste, créez et testez un backup, puis vérifiez sa copie hors serveur et les personnes capables de la récupérer. Ce dernier point est une recommandation opérationnelle : il faut terminer et contrôler le transfert pour disposer d’une copie externe utilisable.

## Sources vérifiées

- [installer](../../../installer).
- [app.py](../../../panel/kei_panel/app.py).
- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [main.py](../../../panel/kei_panel/screens/main.py).
- [install.py](../../../panel/kei_panel/routines/install.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [dashboard.py](../../../panel/kei_panel/views/dashboard.py).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [menus.py](../../../panel/kei_panel/menus.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
