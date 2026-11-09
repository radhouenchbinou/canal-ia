#!/usr/bin/env python3
"""Outil du canal de demandes entre agents.

Usage :
  canal.py nouveau --de web --pour api --titre "..." [--priorite haute] [--statut proposee] [--depend-de ID,ID]
  canal.py lister [--statut nouvelle] [--pour api] [--archives]
  canal.py prets                  demandes `nouvelle` dont toutes les dépendances sont faites
  canal.py maj ID [--statut S] [--branche B] [--commit SHA]
  canal.py verifier               contrôle de tous les fichiers (code retour 1 si erreur)
  canal.py etat                   régénère ETAT.md
  canal.py archiver               déplace les demandes faites ou refusées dans demandes/archive/

Bibliothèque standard seulement.
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
STATUTS = ["proposee", "nouvelle", "en-cours", "bloquee", "faite", "refusee"]
CLOSES = {"faite", "refusee"}
PRIORITES = ["haute", "normale", "basse"]
CHAMPS = ["id", "titre", "de", "pour", "statut", "priorite", "cree", "maj", "depend-de", "branche", "commits"]
LISTES = {"depend-de", "commits"}
ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{3}$")

MODELE = """## Constat

## Demande

## Critères d'acceptation

- [ ]

## Réponse

(écrite par l'agent qui traite la demande : ce qui a été fait, ADR, tests, ce qui reste à l'émetteur)
"""


class Demande:
    def __init__(self, chemin, champs, corps):
        self.chemin = chemin
        self.champs = champs
        self.corps = corps

    def __getitem__(self, cle):
        return self.champs.get(cle, [] if cle in LISTES else "")

    def texte(self):
        lignes = ["---"]
        for cle in CHAMPS:
            valeur = self[cle]
            if cle in LISTES:
                valeur = "[" + ", ".join(valeur) + "]"
            lignes.append(f"{cle}: {valeur}".rstrip())
        lignes.append("---")
        return "\n".join(lignes) + "\n\n" + self.corps.lstrip("\n")

    @property
    def archivee(self):
        return self.chemin.parent.name == "archive"


def lire(chemin):
    texte = Path(chemin).read_text(encoding="utf-8")
    if not texte.startswith("---\n"):
        raise ValueError(f"{chemin.name} : en-tête --- absent")
    fin = texte.find("\n---", 4)
    if fin < 0:
        raise ValueError(f"{chemin.name} : en-tête non fermé")
    champs = {}
    for ligne in texte[4:fin].splitlines():
        if not ligne.strip():
            continue
        cle, sep, valeur = ligne.partition(":")
        if not sep:
            raise ValueError(f"{chemin.name} : ligne d'en-tête illisible « {ligne} »")
        cle, valeur = cle.strip(), valeur.strip()
        if cle in LISTES:
            valeur = [v.strip() for v in valeur.strip("[]").split(",") if v.strip()]
        champs[cle] = valeur
    return Demande(Path(chemin), champs, texte[fin + 4:])


def demandes(racine=RACINE):
    """Toutes les demandes, archivées comprises (ids, dépendances, numérotation)."""
    chemins = list((racine / "demandes").glob("*.md")) + list((racine / "demandes" / "archive").glob("*.md"))
    return [lire(c) for c in sorted(chemins, key=lambda c: c.name)]


def archiver(racine=RACINE):
    archive = racine / "demandes" / "archive"
    deplacees = []
    for d in demandes(racine):
        if d["statut"] in CLOSES and not d.archivee:
            archive.mkdir(exist_ok=True)
            cible = archive / d.chemin.name
            d.chemin.rename(cible)
            deplacees.append(cible)
    etat(racine)
    return deplacees


def projets(racine=RACINE):
    return json.loads((racine / "projets.json").read_text(encoding="utf-8"))


def trouver(racine, ident):
    for d in demandes(racine):
        if d["id"] == ident:
            return d
    raise SystemExit(f"demande {ident} introuvable")


def slug(titre):
    s = titre.lower()
    for a, b in (("àâä", "a"), ("éèêë", "e"), ("îï", "i"), ("ôö", "o"), ("ùûü", "u"), ("ç", "c")):
        for c in a:
            s = s.replace(c, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50]


def prochain_id(racine, jour):
    deja = [d["id"] for d in demandes(racine) if d["id"].startswith(jour)]
    numero = max([int(i[-3:]) for i in deja], default=0) + 1
    return f"{jour}-{numero:03d}"


def verifier(racine=RACINE):
    erreurs = []
    connus = projets(racine)
    try:
        liste = demandes(racine)
    except ValueError as e:
        return [str(e)]
    ids = [d["id"] for d in liste]
    for d in liste:
        nom = d.chemin.name
        if not ID_RE.match(d["id"]):
            erreurs.append(f"{nom} : id invalide « {d['id']} »")
        elif not nom.startswith(d["id"]):
            erreurs.append(f"{nom} : le nom du fichier doit commencer par l'id {d['id']}")
        if ids.count(d["id"]) > 1:
            erreurs.append(f"{nom} : id {d['id']} en double")
        if not d["titre"]:
            erreurs.append(f"{nom} : titre vide")
        for cle in ("de", "pour"):
            if d[cle] not in connus:
                erreurs.append(f"{nom} : projet « {d[cle]} » inconnu dans {cle} (voir projets.json)")
        if d["statut"] not in STATUTS:
            erreurs.append(f"{nom} : statut « {d['statut']} » invalide ({', '.join(STATUTS)})")
        if d["priorite"] not in PRIORITES:
            erreurs.append(f"{nom} : priorité « {d['priorite']} » invalide")
        for dep in d["depend-de"]:
            if dep not in ids:
                erreurs.append(f"{nom} : dépendance {dep} inconnue")
        if d["statut"] == "faite" and "## Réponse" not in d.corps:
            erreurs.append(f"{nom} : demande faite sans section « ## Réponse »")
        if d.archivee and d["statut"] not in CLOSES:
            erreurs.append(f"{nom} : demande archivée au statut « {d['statut']} » (seules faite et refusee s'archivent)")
    return erreurs


def prets(racine=RACINE):
    liste = demandes(racine)
    faites = {d["id"] for d in liste if d["statut"] == "faite"}
    ordre = {p: i for i, p in enumerate(PRIORITES)}
    choix = [d for d in liste if d["statut"] == "nouvelle" and set(d["depend-de"]) <= faites]
    return sorted(choix, key=lambda d: (ordre.get(d["priorite"], 9), d["id"]))


def etat(racine=RACINE):
    toutes = demandes(racine)
    liste = [d for d in toutes if not d.archivee]
    lignes = [
        "# État des demandes",
        "",
        "Généré par `outils/canal.py etat`, ne pas éditer à la main.",
        "",
        "| Statut | Nombre |",
        "| --- | --- |",
    ]
    for s in STATUTS:
        lignes.append(f"| {s} | {sum(1 for d in liste if d['statut'] == s)} |")
    archivees = len(toutes) - len(liste)
    if archivees:
        lignes += ["", f"Archivées : {archivees} demandes faites ou refusées, dans `demandes/archive/` "
                   "(`canal.py lister --archives`)."]
    for s in STATUTS:
        groupe = [d for d in liste if d["statut"] == s]
        if not groupe:
            continue
        lignes += ["", f"## {s}", "", "| Id | De → pour | Priorité | Titre | Branche |", "| --- | --- | --- | --- | --- |"]
        for d in groupe:
            lien = f"[{d['titre']}]({d.chemin.relative_to(racine).as_posix()})"
            lignes.append(f"| {d['id']} | {d['de']} → {d['pour']} | {d['priorite']} | {lien} | {d['branche']} |")
    (racine / "ETAT.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")


def main(argv=None, racine=RACINE):
    p = argparse.ArgumentParser(description="Canal de demandes entre agents")
    sous = p.add_subparsers(dest="cmd", required=True)
    n = sous.add_parser("nouveau")
    n.add_argument("--de", required=True)
    n.add_argument("--pour", required=True)
    n.add_argument("--titre", required=True)
    n.add_argument("--priorite", default="normale", choices=PRIORITES)
    n.add_argument("--statut", default="nouvelle", choices=["nouvelle", "proposee"])
    n.add_argument("--depend-de", default="")
    n.add_argument("--jour", default=datetime.date.today().isoformat())
    l = sous.add_parser("lister")
    l.add_argument("--statut")
    l.add_argument("--pour")
    l.add_argument("--archives", action="store_true", help="inclure les demandes archivées")
    sous.add_parser("prets")
    m = sous.add_parser("maj")
    m.add_argument("id")
    m.add_argument("--statut", choices=STATUTS)
    m.add_argument("--branche")
    m.add_argument("--commit", action="append", default=[])
    sous.add_parser("verifier")
    sous.add_parser("etat")
    sous.add_parser("archiver")
    a = p.parse_args(argv)

    if a.cmd == "nouveau":
        connus = projets(racine)
        for cle in ("de", "pour"):
            if getattr(a, cle) not in connus:
                raise SystemExit(f"projet « {getattr(a, cle)} » inconnu ({', '.join(connus)})")
        ident = prochain_id(racine, a.jour)
        champs = {"id": ident, "titre": a.titre, "de": a.de, "pour": a.pour, "statut": a.statut,
                  "priorite": a.priorite, "cree": a.jour, "maj": a.jour,
                  "depend-de": [x.strip() for x in a.depend_de.split(",") if x.strip()],
                  "branche": "", "commits": []}
        chemin = racine / "demandes" / f"{ident}-{slug(a.titre)}.md"
        chemin.write_text(Demande(chemin, champs, MODELE).texte(), encoding="utf-8")
        print(chemin)
    elif a.cmd == "lister":
        for d in demandes(racine):
            if (a.archives or not d.archivee) and (not a.statut or d["statut"] == a.statut) \
                    and (not a.pour or d["pour"] == a.pour):
                print(f"{d['id']}  {d['statut']:<9} {d['de']:>7} → {d['pour']:<7} {d['titre']}")
    elif a.cmd == "prets":
        for d in prets(racine):
            print(f"{d['id']}  {d['priorite']:<7} {d['de']:>7} → {d['pour']:<7} {d.chemin.relative_to(racine)}")
    elif a.cmd == "maj":
        d = trouver(racine, a.id)
        if a.statut:
            d.champs["statut"] = a.statut
        if a.branche is not None:
            d.champs["branche"] = a.branche
        d.champs["commits"] = d["commits"] + [c for c in a.commit if c not in d["commits"]]
        d.champs["maj"] = datetime.date.today().isoformat()
        d.chemin.write_text(d.texte(), encoding="utf-8")
        etat(racine)
        print(d.chemin)
    elif a.cmd == "verifier":
        erreurs = verifier(racine)
        for e in erreurs:
            print(e, file=sys.stderr)
        if erreurs:
            return 1
        print(f"{len(demandes(racine))} demandes, aucune erreur")
    elif a.cmd == "archiver":
        for c in archiver(racine):
            print(c.relative_to(racine))
    elif a.cmd == "etat":
        etat(racine)
        print(racine / "ETAT.md")
    return 0


if __name__ == "__main__":
    os.chdir(RACINE)
    sys.exit(main())
