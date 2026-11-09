import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import canal


class CanalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        (self.racine / "demandes").mkdir()
        (self.racine / "projets.json").write_text(json.dumps({"api": {}, "web": {}, "outils": {}}))

    def tearDown(self):
        self.tmp.cleanup()

    def lancer(self, *args):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = canal.main(list(args), racine=self.racine)
        return code, sortie.getvalue().strip()

    def nouveau(self, titre, **opts):
        args = ["nouveau", "--de", opts.get("de", "web"), "--pour", opts.get("pour", "api"),
                "--titre", titre, "--jour", "2026-11-05"]
        for cle in ("priorite", "statut", "depend_de"):
            if cle in opts:
                args += ["--" + cle.replace("_", "-"), opts[cle]]
        return Path(self.lancer(*args)[1])

    def test_nouveau_numerote_et_relit(self):
        a = self.nouveau("Compacter une conversation")
        b = self.nouveau("Écran support")
        self.assertEqual(a.name, "2026-11-05-001-compacter-une-conversation.md")
        self.assertEqual(b.name, "2026-11-05-002-ecran-support.md")
        d = canal.lire(a)
        self.assertEqual(d["statut"], "nouvelle")
        self.assertEqual(d["depend-de"], [])
        self.assertEqual(canal.verifier(self.racine), [])

    def test_projet_inconnu_refuse(self):
        with self.assertRaises(SystemExit):
            self.nouveau("x", pour="inconnu")

    def test_prets_attend_les_dependances_et_trie_par_priorite(self):
        base = self.nouveau("Base")
        self.nouveau("Suite", depend_de="2026-11-05-001")
        self.nouveau("Urgente", priorite="haute")
        self.nouveau("Proposée", statut="proposee")
        self.assertEqual([d["titre"] for d in canal.prets(self.racine)], ["Urgente", "Base"])
        self.lancer("maj", "2026-11-05-001", "--statut", "faite", "--branche", "canal/x", "--commit", "abc")
        self.assertEqual([d["titre"] for d in canal.prets(self.racine)], ["Urgente", "Suite"])
        d = canal.lire(base)
        self.assertEqual((d["branche"], d["commits"]), ("canal/x", ["abc"]))
        self.assertIn("## Constat", d.corps)

    def test_verifier_signale_les_erreurs(self):
        chemin = self.nouveau("Base")
        chemin.write_text(chemin.read_text().replace("statut: nouvelle", "statut: finie")
                          .replace("depend-de: []", "depend-de: [2026-01-01-009]"))
        erreurs = canal.verifier(self.racine)
        self.assertTrue(any("statut" in e for e in erreurs))
        self.assertTrue(any("dépendance" in e for e in erreurs))
        self.assertEqual(self.lancer("verifier")[0], 1)

    def test_etat_regroupe_par_statut(self):
        self.nouveau("Base")
        self.nouveau("Autre", statut="proposee")
        self.lancer("etat")
        texte = (self.racine / "ETAT.md").read_text()
        self.assertIn("| nouvelle | 1 |", texte)
        self.assertIn("## proposee", texte)
        self.assertIn("[Base](demandes/2026-11-05-001-base.md)", texte)


    def test_archiver_deplace_les_demandes_closes_et_garde_les_dependances(self):
        self.nouveau("Base")
        self.nouveau("Suite", depend_de="2026-11-05-001")
        self.lancer("maj", "2026-11-05-001", "--statut", "faite")
        code, sortie = self.lancer("archiver")
        self.assertEqual(code, 0)
        self.assertEqual(sortie, "demandes/archive/2026-11-05-001-base.md")
        self.assertEqual(canal.verifier(self.racine), [], "la dépendance vers une archivée reste connue")
        self.assertEqual([d["titre"] for d in canal.prets(self.racine)], ["Suite"])
        self.assertEqual(self.lancer("lister")[1].count("\n"), 0, "lister masque les archivées")
        self.assertIn("Base", self.lancer("lister", "--archives")[1])
        self.assertEqual(Path(self.lancer("nouveau", "--de", "web", "--pour", "api", "--titre", "Trois",
                                          "--jour", "2026-11-05")[1]).name, "2026-11-05-003-trois.md")
        texte = (self.racine / "ETAT.md").read_text()
        self.assertNotIn("## faite", texte)
        self.assertIn("Archivées : 1", texte)
        self.lancer("maj", "2026-11-05-001", "--statut", "en-cours")
        self.assertTrue(any("archivée" in e for e in canal.verifier(self.racine)))


if __name__ == "__main__":
    unittest.main()
