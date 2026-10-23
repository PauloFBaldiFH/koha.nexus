# 9. Diagnostic et journaux

[Sommaire](README.md)

Notez action, heure, erreur complète et fonctions encore disponibles. Page accessible, service actif et recherche réussie sont distincts. Ni réinstallation ni restore ne sont une première réponse universelle.

## Démarche et journaux

Actualisez **Control Dashboard**. Dans **Diagnostics & maintenance center**, **Detailed server & Koha status**, puis **Full system health check**, lisez rapport. **View latest validation report** le rouvre ; **Export diagnostics** prépare support et indique chemin. Malgré masquage des secrets, vérifiez données lecteurs, fichiers et adresses avant partage ; ne copiez pas toute l’installation.

Le mode classique de repli en cas d’échec Textual n’annule pas une opération précédente. Gardez message/log.

| Emplacement | Usage |
| --- | --- |
| `/var/log/koha-easy-install/` | Journaux Linux principaux |
| `apt.log` | Paquets et étapes concernées |
| `validacao-*.log` | Rapports datés |
| `new-panel.log` | Textual et traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/export |
| `restore.log`, `restore-import.log` | Restore/import SQL |
| `zebra-rebuild.log`, `search-engine.log` | Index/recherche |
| `/var/log/koha-easy-install/tools/` | Outils |
| `C:\Koha\logs`, anciennement `C:\KohaEasy\logs` | Windows selon installation |

`*` désigne des fichiers datés ; ils peuvent manquer avant première exécution. Préférez le chemin exact affiché. **Library tools > View tool logs** permet date/routine ; accès restreint car données personnelles possibles.

Rapport : contexte, date, version, OK/avertissements/échecs/informations. Lisez chaque message ; **No critical failures** peut comporter avertissements. Un backup ancien n’est pas un échec de base. Revalidez après correction et comparez.

**Real-time Apache log auditing** choisit staff/OPAC avec chemins de repli anciens. Textual **Pause/p** suspend l’affichage, pas Apache ; **Continue** reprend, **Back/Esc** ferme. Le classique emploie `Ctrl+C` pour ce suivi, pas toutes les tâches. Examinez heure/contexte de `error`, `fatal`, `denied`, `fail` ; une couleur n’établit pas la cause.

## Symptômes

- OPAC/staff inaccessible : Apache, MariaDB, Plack, cache et adresse locale/réseau/VPN/tunnel. `localhost` est le poste du navigateur. **Restart / repair Koha services (Memcached, Plack)** peut interrompre ; lisez résultat et revalidez.
- Notice introuvable en recherche : moteur, file, index/base. **Search engine & indexing > Repair / rebuild indexing** exige lecture des confirmations et attente ; changer vers Elasticsearch n’est pas le premier geste obligé.
- Backup absent : heure/résultat/espace et serveur/Linux actifs au cron ; `.part` n’est pas terminé. Consultez `backup_sql.log`, testez ou créez manuellement ; ne supprimez dernière copie valide sans autre sûre et évitez concurrence.
- Import échoué/totaux inattendus : logs Magic Import/MARC, entrée/préparation/écriture, mode/codes/barcodes/rejets/doublons. Échantillon correct ne valide pas l’ensemble ; contrôle intégral et étapes déjà terminées avant nouvelle tentative.
- Restore échoué : identifiez étape. Index peut échouer après base restaurée et rollback peut échouer aussi ; vérifiez base/recherche/validation.
- IA/enrichissement lent : Ollama/choix/mémoire ou travail/serveurs/limites. Ne dupliquez pas une grosse tâche pour retard ; service distant et RAM locale appellent enquêtes différentes.

## Icône Windows

PowerShell de l’utilisateur connecté, **sans administrateur** :

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Ce diagnostic peut recréer raccourcis et relancer la zone de notification ; il n’est pas en lecture seule. Produit `diagnose-<date>.txt` dans `logs` détecté ; conservez chemin et erreur. Diffère de l’installation administrative.

**Deep database optimization & log cleanup** entretient et redémarre, mais peut effacer des traces utiles. Gardez diagnostics avant maintenance ; ne l’utilisez pas pour masquer l’erreur. Pour assistance : version, Windows/WSL ou distribution, action/heure, message complet, OPAC/staff/recherche, opération précédente, extraits relus pour confidentialité.

**À confirmer :** cause sans message complet et log ; ne l’attribuez pas automatiquement au réseau ou à l’installation.

## Sources vérifiées

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
