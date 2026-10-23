# 7. IA locale

[Sommaire](README.md)

**AI**, touche `a`, regroupe fournisseur, Ollama et outils photo MARC Replace/assistant staff. Configurer ne les installe pas automatiquement.

## Ollama local

Lisez l’avertissement de consommation CPU/RAM et ralentissement de Koha. Dans **Ollama on this server**, **Check Ollama**, puis **Install Ollama** si absent. Choisissez dans la liste et **Download** : réseau et disque nécessaires. Aucun nom de modèle n’est imposé, les offres pouvant changer.

Choisissez **Local Ollama**, contrôlez URL (par défaut `http://127.0.0.1:11434`), puis **Use for chat** ou **Use for cataloguing**. Les photos nécessitent vision, pas uniquement texte. **Test connection/Save**, ou **F5/Ctrl+S** : remplir n’est pas enregistrer. Chat vide reprend vision. **Load models** interroge le fournisseur et signale une liste intégrée si inaccessible.

Installé occupe disque, chargé occupe RAM ; **Free memory** décharge sans supprimer, avec rechargement possible à la demande. La boîte Ollama reste affichée avec un autre fournisseur : vérifiez fournisseur/URL sauvegardés avant de conclure au traitement local.

## MARC Replace

Installez/mettez à jour puis ouvrez la page ; l’installateur vérifie compilation et propose raccourcis staff. Une notice à la fois : `.mrc`/`.xml` ou texte, `biblionumber` à remplacer, **Preview**, comparaison puis confirmation. Identifiant vide crée une nouvelle notice : évitez doublons. Exemplaires existants préservés, zones d’items entrantes écartées ; version précédente téléchargeable MARCXML, à renvoyer au même identifiant pour récupérer. Ne remplace pas backup complet.

Dans **AI cataloguing**, fournissez photos lisibles couverture, page de titre et verso disponibles, JPEG/PNG/WebP, au moins une. Choisissez framework nouveau ou cible, **Read the photos**, attendez et comparez brouillon : titre, responsabilité, publication, ISBN, classement, absences. Corrigez MARC avant confirmation. Classement suggéré à contrôler dans les tables ; chiffre ISBN correct ne prouve pas édition. Les zones d’exemplaires ne sont pas sauvegardées depuis ce brouillon.

## Assistant et confidentialité

**Install, update or remove the assistant** gère le chat remplaçant les nouvelles de l’accueil staff, sans toucher l’OPAC. Recherche Koha et requêtes de lecture définies, pas SQL libre généré. Réponses avec liens/propositions possibles.

**Une proposition n’est pas exécutée.** Vérifiez cible, avant/après et effet ; **Approve & Execute** exige vos permissions. Une modification depuis la proposition peut la faire refuser. Consultez changements confirmés : effacer conversation ou retirer l’assistant ne les annule pas. Retrait efface conversations mais conserve historique des actions approuvées.

Surveillez matériel et Koha ; si lent, évitez nouvelles photos et libérez mémoire si approprié. Pas de délai garanti. Un fournisseur distant reçoit la requête : évaluez politique de données/images, ne testez pas avec lecteurs réels. Les catégories de coût ne garantissent pas gratuité.

**À confirmer :** RAM, disque et temps de réponse par choix/matériel ; minimum Koha ne garantit pas performance IA.

## Sources vérifiées

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
