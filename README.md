# Canal de demandes entre agents

Un agent qui travaille sur un projet (`ai-core`, `ba`, `front`, `mcp` : voir `projets.json`) et qui a besoin d'une
évolution dans **un autre** projet ne la code pas lui-même : il écrit une demande ici. L'agent maître (session
ouverte sur ce dossier, voir `CLAUDE.md`) lance alors un agent dans le projet concerné pour la traiter.

État courant : [`ETAT.md`](ETAT.md). Idée de départ : un agent qui ne code pas le projet d autrui, il écrit une demande.

## Écrire une demande

Avec la commande `/demande` (skill `skills/demande`), ou à la main :

```bash
python3 ~/canal-ia/outils/canal.py nouveau --de web --pour api --titre "Compacter une conversation"
```

Puis remplir les sections du fichier créé, et committer **dans ce dépôt** :

```bash
git -C ~/canal-ia add demandes && git -C ~/canal-ia commit -m "Demande <id> : <titre>"
```

Une demande doit se suffire à elle-même : l'agent qui la traitera ne connaît pas ta conversation.

- **Constat** : ce qui manque ou ne marche pas, avec les fichiers, routes, classes concernés.
- **Demande** : le contrat attendu (route, champ, comportement), pas l'implémentation.
- **Critères d'acceptation** : cases à cocher vérifiables.
- Renvoyer vers un document long par son chemin complet (`~/code/<projet>/docs/…`) plutôt que de le recopier.
- Jamais de secret, de jeton ni de donnée réelle de client.

## En-tête

| Champ | Valeurs |
| --- | --- |
| `id` | `AAAA-MM-JJ-NNN`, donné par `canal.py nouveau` |
| `de`, `pour` | un nom de `projets.json` |
| `statut` | voir ci-dessous |
| `priorite` | `haute`, `normale`, `basse` |
| `depend-de` | ids qui doivent être `faite` avant de commencer |
| `branche`, `commits` | remplis par l'agent qui traite |

## Statuts

| Statut | Sens | Qui le pose |
| --- | --- | --- |
| `proposee` | à valider par le responsable avant tout travail ; le maître ne la lance pas | émetteur |
| `nouvelle` | prête à être traitée | émetteur, ou le responsable qui valide une `proposee` |
| `en-cours` | un agent la traite | agent qui traite |
| `bloquee` | question ouverte (écrite dans `## Réponse`) | agent qui traite |
| `faite` | réalisée sur `branche`, `## Réponse` remplie | agent qui traite |
| `refusee` | non réalisée, raison dans `## Réponse` | agent qui traite ou responsable |

Changer un statut : `canal.py maj <id> --statut faite --branche canal/<id> --commit <sha>` (régénère `ETAT.md`).

## Traiter une demande (agent lancé par le maître)

1. `canal.py maj <id> --statut en-cours --branche <ta branche>` puis commit dans `canal-ia`.
2. Travailler **dans le projet cible uniquement**, en suivant son `CLAUDE.md` (ses règles priment : par exemple
   une décision d'architecture dans `ai-core` attend la validation du responsable → statut `bloquee`).
3. Tests du projet au vert, commit sur ta branche. **Ne jamais** fusionner dans la branche de base, pousser, déployer.
4. Remplir `## Réponse` : ce qui est fait, ADR, tests lancés et résultat, ce que l'émetteur doit faire ensuite.
5. Si l'émetteur doit s'aligner (nouveau champ à afficher, écran à faire…) : créer la demande retour
   (`--de <cible> --pour <émetteur> --depend-de <id>`).
6. `canal.py maj <id> --statut faite --commit <sha>`, `canal.py verifier`, commit dans `canal-ia`.

Plusieurs agents committent ici : si `git commit` échoue sur un verrou (`index.lock`), réessayer quelques secondes
plus tard. Ne modifier que ses propres demandes, et ne committer que ses fichiers : `git commit -m "…" -- <fichiers>`
(un `git commit` nu embarque ce qu'un autre agent a mis dans l'index).

## Archiver

Une demande `faite` ou `refusee` peut être rangée dans `demandes/archive/` :

```bash
python3 ~/canal-ia/outils/canal.py archiver
```

L'outil lit toujours les archives : ids, dépendances et numérotation restent valides, et `maj` les trouve encore.
`ETAT.md` et `lister` ne montrent que les demandes actives (`lister --archives` pour tout voir). Une archivée qui
repasse à un autre statut est signalée par `verifier` : la remettre dans `demandes/` à la main.

## Contrôle

```bash
python3 ~/canal-ia/outils/canal.py verifier
```

```bash
cd ~/canal-ia/outils && python3 -m unittest test_canal
```
