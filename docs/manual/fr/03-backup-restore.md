# 3. Backup et restore

[Sommaire](README.md)

## Centre et types de copie

Ouvrez **Backup center** ou `b` : dernier backup, taille, résultat, **Compression** et cartes suivantes.

| Carte | Fonction |
| --- | --- |
| Download latest backup | Copier le fichier le plus récent trouvé |
| Generate manual backup and download to PC | Créer, contrôler et transférer la base |
| Export MARC21 records now | Exporter bibliographie et autorités |
| Restore database | Remplacer la base actuelle |
| Configure cloud backup | Configurer l’envoi externe |
| Test integrity of latest backup | Tester une importation temporaire |

**Restore database est une carte du centre**, pas un bouton supérieur ni une entrée principale séparée. Résultat décrit le dernier lancement nocturne ; date et taille décrivent le fichier le plus récent, éventuellement différent.

SQL contient la base Koha, pas une image complète Windows/Debian ni tous les fichiers. MARC21 réunit bibliographie et autorités dans `.tar.gz` et ne remplace pas SQL pour lecteurs et circulation. Avant restore d’une base avec tables, une copie de sécurité validée est créée ; une base vide peut sauter cette copie.

Dossiers : `/var/backups/koha_sql` pour SQL automatique et sécurité, `/var/backups/koha_marc` pour MARC. Le manuel a sa destination propre, par défaut `backups` dans le dossier personnel identifié par le panneau. Une copie `.part` reste provisoire jusqu’à validation et renommage final.

## Compression

**Compression** propose gzip `.sql.gz` (compatibilité), Zstandard `.sql.zst` (rapide et plus petit, grands catalogues) et XZ/LZMA `.sql.xz` (plus petit, plus lent). La sélection est enregistrée immédiatement, sans bouton supplémentaire ; elle concerne les nouveaux backups nocturnes, manuels et de sécurité, sans recomprimer l’existant.

Si le programme nécessaire ne peut être installé, lisez le problème et le format utilisé : gzip peut servir de repli. Restore reconnaît les formats compatibles indépendamment de cette sélection. Utilisez `.sql`, `.sql.gz`, `.sql.zst`, `.sql.xz` ; l’extension ne garantit pas le contenu.

## Créer, télécharger et tester

1. **Generate manual backup and download to PC** : vérifiez le dossier serveur et son accès en écriture.
2. **Save backup**, puis attendez génération et contrôle ; la fenêtre ne ferme pas pendant sauvegarde/copie.
3. Vérifiez nom, taille et chemin. Sous WSL : **Save to Windows Downloads** ou **Choose folder in Windows**. À distance, exécutez la commande affichée sur votre propre ordinateur.
4. Vérifiez le fichier reçu et **Finish and exit**.

Les boutons Windows n’existent que sous WSL. Ne réutilisez pas la commande d’une autre installation : elle dépend du serveur/fichier détectés. Si un backup ou restore est en cours, attendez ; ne contournez pas le verrou commun avec un travail concurrent.

**Download latest backup** transfère un fichier existant, sans en créer. Sous Linux de bureau/WSL il essaie Downloads ; par SSH il peut afficher la commande locale. Sans fichier trouvé, créez un backup manuel.

**Test integrity of latest backup** : vérifiez date/fichier, changez via **Choose another file**, confirmez et attendez l’importation temporaire. Le succès indique tables, notices et lecteurs et ne remplace pas la production. Il concerne ce fichier dans cet environnement ; conservez l’accès à cette même copie après transfert.

## MARC et cloud

**Export MARC21 records now** demande confirmation, produit le paquet de notices et autorités et indique chemin/contenu. Téléchargez ou transférez par l’instruction proposée. Koha continue de fonctionner ; un cloud configuré donne aussi le résultat d’envoi. Conservez SQL pour une récupération complète.

**Configure cloud backup** offre deux parcours Google Drive et d’autres services, notamment OneDrive, MEGA, S3. Choisissez autorisation sur serveur ou autre poste selon le contexte, suivez la seule URL présentée et remplissez les champs requis. S3 distingue service, région/endpoint et bucket. Attendez le vrai test d’envoi et vérifiez réception ; ne comptez pas sur un échec de configuration.

Saisissez les informations privées seulement dans l’installation ; aucun document public, capture ou support ne doit les reproduire. Ce manuel ne cite pas leurs fichiers de stockage. Horaires par défaut : SQL quotidien 23:00 et MARC dimanche 03:00, heure serveur. Cron peut les modifier.

## Restore destructif

**Confirmer autorise le remplacement de la base actuelle.** Prévoyez maintenance et copie externe ; le panneau ne réalise pas automatiquement cette précaution à votre place.

1. Dans **Restore database**, choisissez le fichier accessible au serveur, avec transfert guidé si nécessaire. Sous WSL, une copie du disque Windows vers Linux peut précéder l’opération.
2. Lisez contrôles d’accès, contenu, intégrité et espace. Examinez tout fichier suspect/incomplet malgré son extension.
3. Revérifiez le fichier dans la confirmation. Vous pouvez renoncer jusqu’à celle-ci ; ensuite attendez sans fermer, car le flux n’est pas annulable.

D’abord SQL est importé dans une base temporaire et les tables essentielles/nombre sont vérifiés. Un échec arrête avant remplacement. Si la base actuelle contient des tables, crée une copie validée SQL avec préfixe `pre_restore_safety_backup_`, date/heure/compression. Si elle échoue, la base existante ne doit pas être supprimée ; vide, elle peut sauter cette étape.

Puis arrêt des clients, recréation/importation, mise à niveau du schéma, synchronisation recherche, reconstruction et redémarrage. Le thème sauvegardé est réappliqué si son état est disponible, par tentative.

Échec temporaire ou copie préalable ne signifie pas remplacement effectué. Selon étape et copie disponible, un échec recréation/importation/schéma peut déclencher récupération précédente ; **le rollback peut lui-même échouer**. L’index peut échouer alors que la base est déjà restaurée : ne supposez pas retour de l’ancien catalogue.

Gardez message et logs `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log` et `/var/log/koha-easy-install/zebra-rebuild.log` pour indexation. Revenez à la carte du centre, pas à d’anciens numéros ; demandez assistance si l’état est incertain. Actualisez dashboard, vérifiez notices et recherches dans OPAC/staff. La fin SQL ne prouve pas récupération des fichiers externes.

## Sources vérifiées

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
