# 4. Importation magique

[Sommaire](README.md)

## Préparer et reconnaître

Magic Import lit notices bibliographiques, exemplaires, lecteurs et autorités. Format reconnu n’implique pas tous les champs bien compris, surtout sans en-têtes ou dans les zones locales. Gardez original et backup vérifié, essayez un échantillon représentatif (plusieurs exemplaires, accents, vides, exceptions), comparez les totaux avec l’ancien système. Ne publiez pas d’exports lecteurs.

Ouvrez **Magic Import Tool**, ou `i`, puis sa carte. Le fichier/dossier doit être accessible au Linux du panneau ; ce qui n’existe que sur le poste du navigateur ou terminal distant n’est pas automatiquement sur le serveur.

| Entrée | Vérifications |
| --- | --- |
| MARC21 ISO 2709, MARCXML, texte MARC | Titres, accents, autorités et exemplaires. `.mrk` MarcEdit est reconnu sans conversion imposée par la seule extension. |
| CSV/TSV, `.xlsx`, `.xls`, `.ods`, `.dbf` | Séparateur, en-têtes, valeurs et destinations ; détection par contenu et en-têtes disponibles. |
| JSON/XML tabulaire | Structure reconnue ; XML quelconque n’est pas forcément MARCXML. |
| SQL tabulaire, fragments sans en-têtes | Données et relations reconnues, pas exécution comme programme de migration ; revoyez les ambiguïtés. |
| ISIS | Export PostgreSQL reconnu avec `acervo` ; maître CDS/ISIS `.mst` à exporter de WinISIS en ISO 2709. |
| Biblioteca Fácil | Backup reconnu ou dossier de données, tables liées réunies ; vérifiez séparément notices, lecteurs, prêts et réservations. |
| Backup Koha complet | Redirection vers restore, qui remplace la base plutôt que d’ajouter des notices. |

Un dump PostgreSQL d’un autre système, surtout binaire `pg_dump`, n’est pas une base MariaDB prête. Si refusé, exportez MARC ou tableaux dans le système d’origine. Vérifiez chaque membre d’archive. PDF, images, documents et exécutables ne sont pas des exports utilisables par ce lecteur.

## Correspondance manuelle intégrée

1. Vérifiez **Bibliographic**, **Patrons**, **Authorities** et corrigez le mode.
2. Examinez grille et destinations ; séparateur ou **Ctrl+Up/Down** règle la hauteur.
3. Choisissez conserver, rediriger, texte fixe ou ignorer. Comprenez les liens avant d’écarter un identifiant.
4. **Values of this Koha** présente codes disponibles, bibliothèque/type/catégorie par défaut et remplacements source/cible.
5. **Record preview** affiche le résultat. **Check the whole file** prépare/valide tout le fichier sans importer dans Koha à ce stade.
6. Nommez puis **Save** pour un profil ; sélectionnez et **Use** pour charger. Révisez si la structure change.
7. **Apply/Ctrl+S** accepte le mapping et continue la préparation, sans confirmation finale d’écriture. **Skip: import as it is**, y compris **Esc**, saute la correspondance manuelle, pas toute la procédure.

Regroupement et corrections textuelles exigent une prévisualisation ; évitez les transformations aveugles de sigles, noms et codes.

## Exemplaires, lecteurs, autorités

`952` natif est conservé et peut remapper bibliothèque/type sur demande. Ne remplacez pas un code valide uniquement différent du défaut. Examinez barcode, bibliothèque propriétaire/détentrice, cote, type, localisation et acquisition. `949`, `852`, `950`, `990` sont locaux : Pergamum/Biblivre peuvent donner des sens différents aux sous-zones.

Une annotation de dépôt légal avec `DL`/date ne crée pas automatiquement un exemplaire ; revoyez exclusions et preuves indépendantes d’inventaire. Barcode absent demande révision par défaut ; génération exige choix explicite et identité stable migration/source, sans renumérotation silencieuse des collisions. En SQL lié, une relation doit être reconnue ; position de colonne ou ordre de lignes ne suffit pas. Arrêtez et corrigez un lien incertain.

En **Patrons**, vérifiez prénom/nom, carte, contacts, adresse, dates, bibliothèque/catégorie existante. E-mail, CPF et dates reconnus ne sont que des indices ; naissance, inscription et expiration ont parfois même format. Le flux demande mise à jour des lecteurs existants par correspondance de carte, différente d’ajout seul. N’attribuez pas permissions/authentification par supposition.

En **Authorities**, examinez identifiant, vedette autorisée, variantes, relations et type ; changer de mode ne crée pas l’information absente.

## Confirmer et contrôler

Lisez quantités, rejets et questions avant écriture. Pour les notices existantes : garder catalogue et ajouter nouveaux exemplaires, remplacer par l’entrant, ou créer sans comparaison. Évitez de répéter un lot involontairement.

**Un échec tardif peut laisser les étapes précédentes importées.** Gardez résumé/logs et vérifiez avant de recommencer. Contrôlez échantillons, exemplaires, lecteurs et liens dans Koha. **Library tools > Undo a MARC import** traite les lots MARC, pas toute la circulation ou les lecteurs. Pour récupération complète, suivez Backup center avec ses précautions.

**À confirmer :** compatibilité d’un format propriétaire/version précise sans échantillon et contrôle du résultat.

## Sources vérifiées

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
