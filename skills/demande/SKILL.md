---
name: demande
description: Écrire une demande d'évolution pour un autre projet (api, web, outils) dans le canal ~/canal-ia, au lieu de modifier ce projet soi-même. À utiliser dès qu'une tâche a besoin d'un changement hors du dépôt courant (route ou champ du back, écran du web, script d outil…), ou quand on tape /demande.
---

# Écrire une demande dans le canal

Le canal est `~/canal-ia`. Lire son `README.md` une fois par session. Ne jamais modifier l'autre
projet toi-même : un agent dédié le fera à partir de ta demande.

1. **Projet émetteur** : le dépôt courant, traduit par `~/canal-ia/projets.json`
   (`~/code/mon-api` → `api`, `~/code/mon-front` → `web`, `~/code/mes-outils` → `outils`).
2. **Projet cible, titre, priorité, dépendances** : déduits de la tâche ; ne demander à l'utilisateur que ce qui
   reste ambigu. Vérifier qu'une demande proche n'existe pas déjà :
   `python3 ~/canal-ia/outils/canal.py lister --pour <cible>`.
3. **Statut** : `nouvelle` si le besoin est clair et ne demande pas de décision du responsable ; `proposee` s'il
   faut d'abord valider un choix (architecture, coût, contrat ouvert).
4. Créer le fichier :
   `python3 ~/canal-ia/outils/canal.py nouveau --de <émetteur> --pour <cible> --titre "<titre>" [--priorite haute] [--statut proposee] [--depend-de <id>]`
5. Remplir **Constat**, **Demande**, **Critères d'acceptation** pour un lecteur qui n'a pas ta conversation :
   fichiers, routes, classes, comportement attendu. Laisser `## Réponse` vide. Aucun secret ni donnée réelle.
6. `python3 ~/canal-ia/outils/canal.py verifier && python3 ~/canal-ia/outils/canal.py etat`
7. Committer dans le canal seulement :
   `git -C ~/canal-ia add demandes ETAT.md && git -C ~/canal-ia commit -m "Demande <id> : <titre>"`
8. Dire à l'utilisateur l'id créé et, côté projet courant, ce qui attend la demande (repli, drapeau, TODO).
