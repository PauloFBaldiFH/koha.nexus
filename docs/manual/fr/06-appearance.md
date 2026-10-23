# 6. Apparence de l’OPAC et du staff

[Sommaire](README.md)

Ouvrez **OPAC and Staff Appearance**, ou `o` : catalogue public et staff/intranet ont leurs propres réglages.

## Appliquer après contrôle

**Sync current OPAC settings** lit l’existant sans appliquer. Ajustez un groupe à la fois, puis **Preview** : CSS, JavaScript et contenu à écrire, pas rendu complet de navigateur. **Apply** présente résumé/confirmation et crée un backup avant application. Dans le navigateur vérifiez accueil, recherche, notice et connexion, également sur petit écran.

Les blocs vont dans `OpacUserCSS`/`OpacUserJS`, et `IntranetUserCSS`/`IntranetUserJS` selon besoins staff. Le code propre est conservé, sans garantir absence de conflits visuels avec d’autres personnalisations.

## Lisibilité et images

Texture, flou, opacité, angles, accents et fonds sont réglables ; clair/sombre et thème initial sont distincts. Maintenez un contraste suffisant avec image/transparence. Le staff ajoute barre supérieure, recherche rapide, cartes, densité des tableaux, texte et contraste. Activez **Apply color theme to Staff Client** ; **Copy OPAC preset** remplit seulement, **Apply** enregistre.

Choisissez fichier accessible au serveur, hébergeur proposé ou URL HTTPS directe. PNG, JPEG, GIF, WebP, ICO acceptés, SVG refusé. Un fichier du seul poste client n’est pas encore accessible au serveur. Utilisez des images autorisées et une description accessible au login ; page d’hébergement n’est pas toujours URL directe. Vérifiez les services externes et ne publiez pas de données privées.

## Carrousel et contenus

Nouveautés ou liste Koha : pour celle-ci, indiquez `shelfnumber=` de son adresse. Réglez titre, quantité, style, vitesse, lecture automatique ; **Refresh carousel** actualise. Les nouveautés dépendent des notices/couvertures disponibles ; pas de couverture ne signifie pas suppression, et les sources externes demandent réseau.

Boutons OPAC et staff sont séparés : texte, adresse, cible, ordre ; **Add a button** ajoute, le bouton de ligne retire avant application. Login accepte image/description/HTML filtré (scripts, styles, événements exclus) ; n’y publiez pas d’instructions internes. Actualités des deux côtés ont leurs propres titre/texte/boutons ; les entrées du panneau ne remplacent pas celles de la bibliothèque.

Crédits de pied : lignes `Field: value` selon champs affichés. Liens supplémentaires : texte `|` adresse, six au maximum ; informations publiques seulement.

## Retirer

**Remove** confirme et sauvegarde avant de retirer les blocs du thème et revenir à l’apparence Koha en gardant vos personnalisations. Ce n’est pas un restore général ni l’annulation d’autres opérations. Corrigez le groupe d’une image/couleur/bouton erroné et réappliquez ; gardez tout message d’échec pour diagnostic.

## Sources vérifiées

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
