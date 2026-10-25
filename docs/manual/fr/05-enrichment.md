# 5. Enrichissement et Z39.50/SRU

[Sommaire](README.md)

## Enrichir des notices existantes

Importer apporte un export ; enrichir cherche des compléments ou un livre nouveau. Un titre correspondant exige toujours révision bibliographique. Ouvrez **Library tools > Enrich from world catalogues**, ou `n` ; l’ancienne interface bibliographique par lots n’est plus le parcours actuel du menu.

1. Saisissez `all` ou des `biblionumbers`, par exemple `101, 102, 500-510`, puis **Search**.
2. Suivez travail et serveurs. Une grosse tâche reste en arrière-plan et peut reprendre après redémarrage ; la machine doit être disponible.
3. **Pause/Resume** contrôle la recherche, sans annuler des modifications appliquées.
4. Ouvrez le rapport du travail et comparez sujets, classement, notes et description physique.
5. **Search more servers** cherche des sources non interrogées ; **Choose donor** choisit la source de groupes de zones parmi les résultats.
6. **Apply** seulement après lecture et confirmation. Recherche/préparation n’écrit pas les propositions.

La recherche actuelle utilise Z39.50 direct. Limites et indisponibilités distantes peuvent retarder ou ne rien retourner sans prouver absence du livre. Pas de plafond général de 50 notices : ce seuil sert à choisir la protection d’application, copies de notices pour petits travaux, backup complet vérifié pour grands. Révision toujours requise.

**Revert** restitue les versions antérieures selon les protections, tout en conservant les notices modifiées après application. Ce n’est pas un restore global ni l’annulation de toutes les éditions d’autrui.

## Trouver et ajouter un livre

Saisissez ISBN ou titre, avec auteur/année si possible ; **Find**, examinez sources, sélectionnez. **Import as new record** ajoute avec confirmation sans remplacer une notice au même ISBN. Retire `9XX` locaux du donneur et conserve provenance, évitant ses exemplaires comme vôtres. Vérifiez la notice et créez vos exemplaires selon les procédures locales ; le lot MARC peut être traité par **Undo a MARC import**.

## Autorités et serveurs

**Enrich & standardize authorities**, ou `h`, permet portée et formes exactes/proches. Les proches peuvent corriger et créer des autorités préliminaires : prudence. Priorité aux autorités Koha propres, puis base d’enrichissement et serveurs directs ; sources brésiliennes prioritaires, sujets limités à celles-ci. Cela ne garantit pas adéquation à votre politique.

Lisez rapport avant **Apply**, qui crée autorités et liens avec backup de sécurité, préservant les notices modifiées depuis le rapport. Revert conserve les nouvelles autorités encore liées plutôt que les supprimer aveuglément.

**Z39.50 / SRU servers**, ou `z`, distingue serveur entrant, réseau communautaire et catalogues sortants. L’interrupteur entrant permet des consultations externes et modifie le port firewall. Le réseau partagé est distinct des sources directes d’enrichissement. **Reset/Reset all** dans la santé permet nouvel essai, sans réparer le serveur distant. Pour copie : espace sélectionne, **Scan** effectue une vraie recherche, **Add to Koha** ajoute les sources sélectionnées fonctionnelles.

SRU dans cette configuration ne signifie pas SRU pour chaque enrichissement. Interroger une source ne demande pas d’exposer le serveur entrant.

**À confirmer :** disponibilité, couverture et conditions d’accès de chaque source depuis votre réseau au moment de l’utilisation.

## Sources vérifiées

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
