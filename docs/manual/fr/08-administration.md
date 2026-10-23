# 8. Administration, messages et VPN

[Sommaire](README.md)

Vérifiez état et backup récent avant toute administration. Configurer ne prouve pas fonctionnement sur votre réseau ; testez ensuite.

## Cron

**Schedules & cron tasks**, ou `s`, propose activation, fréquence, heure et jour/expression selon cas. **Reload**, activez le nécessaire, heure `HH:MM`, **Preview**, **Save** puis confirmation ; rechargez pour vérifier. Gère `/etc/cron.d/koha_tasks`, conserve `koha_tasks.bak`. Désactivées restent commentées avec leur horaire ; lignes propres préservées. **Defaults** remplit, mais exige enregistrement.

SQL 23:00 quotidien, MARC dimanche 03:00 par défaut : vérifiez fuseau et personnalisation. Serveur et Linux doivent tourner ; cron ne garantit pas l’allumage Windows. Les avis Koha ont un mécanisme distinct.

## VPN

**Security & access hub > WireGuard VPN**, ou `v` : adresse publique/nom, port UDP. **Set up the VPN** affiche modifications à confirmer ; sur routeur, redirigez UDP vers serveur. Nommez chaque appareil, **Add device**, puis **QR code & profile** pour son client. Contrôlez connexion, staff et trafic.

Ne publiez profil/QR. **Revoke** invalide et impose nouveau profil pour revenir ; **Turn off** déconnecte mais conserve. Split tunnel : `10.66.0.0/24` uniquement, internet/DNS restent propres. Staff connecté `http://10.66.0.1:8080`. WSL sans réseau mirrored est signalé inaccessible directement et cette VPN reste désactivée.

## Communication

**Messaging & interoperability**, ou `m` : **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**.

Activez e-mail et vérifiez SMTP par défaut. Les boutons ouvrent SMTP, adresse bibliothèque, avis/reçus, règles de retard. Activation ne remplit pas tout : préférences, destinataires et modèles sont à vérifier. Suivez l’authentification du fournisseur sans publier d’informations privées.

**Set up WhatsApp and Telegram** gère service, pays/indicatif, test, activation et téléphones. WhatsApp exige passerelle, Telegram bot/destinataires. Testez vers destinataire autorisé avant production ; revoyez formats/modèles avant correction massive. SMS mène à `SMSSendDriver` et préférences lecteurs ; un nom de driver seul ne suffit pas sans service compatible.

**Alerts** règle rappels avant échéance, retards/répétition et résumé quotidien, avec canaux ; enregistrez et **Dry run (sends nothing)** simule. Cela active une tâche, vérifiez cron. Évitez doublons avec avis Koha. SIP2 règle port/réseau/bibliothèque/permissions du libre-service ; retirez exemples et créez le compte Koha via bouton. Compte et serveur doivent correspondre ; n’exposez pas toutes les interfaces pour un test local. Z39.50 mène au chapitre 5, entrée distincte de sortie.

## Sécurité et administration

Le hub regroupe Cloudflare Tunnel, UFW, restriction staff 8080, HTTPS, Fail2ban. Lisez état/résumé ; tunnel, VPN et accès direct diffèrent. Ne modifiez pas firewall distant sans voie d’administration restante. **À confirmer :** domaine, routeur, fournisseur et politique institutionnelle ; aucune recette universelle déduite du code.

**Koha settings & parameters** ajuste mémoire/processus, compte super bibliothécaire et fuseau. Limitez droits étendus. **Koha languages** distingue télécharger/activer, télécharger seul, activer installé, lister ; contrôlez panneau/OPAC/staff.

**Update center** distingue paquets/schémas et panneau GitHub. Backup et maintenance nécessaires ; mise à jour du panneau peut terminer la session pour relancer nouvelle version. Migration échouée n’est pas prouvée réparée par simple redémarrage.

**Library tools** : liens/synchronisation d’autorités, doublons, rapports SQL, catégories, qualité, confidentialité. Catégorie : origines/destinations distinctes, filtre/bibliothèque, simulation puis confirmation protégée. Qualité est lecture, sans correction universelle. Anonymisation supprime liens de vieux historiques avec lecteurs selon Koha, pas toute bibliographie. Suppression lecteurs exige filtres, simulation et nombre confirmé ; action destructive à confronter à rétention. Noms proches ne prouvent pas même personne. Les cartes cachées ne sont pas présentées comme disponibles.

## Sources vérifiées

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
