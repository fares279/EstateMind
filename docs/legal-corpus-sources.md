# Legal assistant corpus: where more text could legitimately come from

The legal assistant answers from 51 passages (collection v3) (registration duties, mortgage law, collective
investment, debt recovery, and the Ministry of Justice's land-registration guide), a hard
ceiling on what it can answer. Research of 2026-09-29, updated 2026-10-01.

## What has been downloaded (2026-09-30)

`python -m ml.legal.fetch_official_texts` downloads a fixed list of seven guides and codes from
justice.gov.tn (the official publisher; no crawling) into `data/official/` with a manifest
(source URL, date, SHA-256):

- *Immatriculation foncière* (id 318): indexed, 15 passages (Arabic).
- *Juge du registre foncier* (id 326): downloaded, but its text extracts as glyph names; it needs
  OCR and is not indexed.
- The codes (ids 294, 287, 288, 297, 289, incl. Code des droits réels and the COC): the site
  stopped answering from this machine during the download and on every retry since (DNS and
  connection timeouts). Rerun the command from another network.

## Outside copies (approved 2026-10-01): what was verified, indexed or dropped

Rule, set before each comparison: a copy is kept only if every passage checked against an
independent official text matches word for word, apart from scan errors, split words and page
numbers. One substantive difference, or too little that can be checked, and it is dropped.

| Text | Copy | Checked against | Result |
| --- | --- | --- | --- |
| Code des droits réels (IORT 2011 edition, compiled by Droit-Afrique) | [bna.tn](http://www.bna.tn/documents/Tunisie_Code_2011_droits_reels.pdf), SHA-256 `b28c84dbe716…` | JORT texts of laws 2001-35 and 2010-34 on FAOLEX ([tun25583](https://faolex.fao.org/docs/pdf/tun25583.pdf), [tun97218](https://faolex.fao.org/docs/pdf/tun97218.pdf)): art. 316, 354, 358, 374, 375, 381, 384, 377 ter §5, 394 §1, 380 §4 | **Verified**: no substantive difference. Stored as `data/official/code_droits_reels.pdf`; only the code is used, not the appended annexes (not verified) |
| Code des obligations et des contrats | [bna.tn](http://www.bna.tn/documents/Code_des_obligations_et_des_contrats.pdf) (Ministry of Justice 2009 edition) and [africa-laws.org](https://www.africa-laws.org/Tunisia/civil%20law/Code%20des%20obligations%20et%20contrats.pdf) (IORT 2015 edition) | each other (global word alignment: 79,440 words equal, 284 other differences) | **Dropped**: most differences are recorded amendments or corrections the 2015 edition annotates, but some meaning-changing words are not annotated (*conditionnelle/conventionnelle*, *incorporels/corporels*, *voluptuaires/volontaires*, *accessions/accessoires*, *délais/détails*). Without the JORT text, which edition is right cannot be told |
| Code de l'aménagement du territoire et de l'urbanisme | [cgdr.nat.tn](https://cgdr.nat.tn/upload/files/18.pdf) (IORT 2011 edition) | the 1994 JORT text on FAOLEX ([tun16294](https://faolex.fao.org/docs/pdf/tun16294.pdf)) | **Dropped**: the JORT scan is unreadable for most of the code (OCR returns "illegible"), so only the first articles could be checked |
| Code des droits réels, Droit-Afrique original | droit-afrique.com | — | Not fetched: the site refused the download (HTTP 403); not worked around |
| JuriSite Tunisie copies | — | — | Not used (excluded by your standing rule) |

The ministry's own copies are still unreachable: justice.gov.tn now answers, but its code pages
redirect to `formation.e-justice.tn`, which does not exist in DNS (checked with two public
resolvers); the same path on `www.e-justice.tn` returns 404.

### Indexing result

The verified Code des droits réels adds 451 passages, each cited by article
("Code des droits réels, art. 67 à 69"). A collection built with it (`legal_tunisia_all_v4`)
**failed the existing activation gate** and is not served; `legal_tunisia_all_v3` stays active:

| | v3 (active) | v4 (with the code) | Target |
| --- | ---: | ---: | ---: |
| Recall@3 (answerable questions) | 0.963 (27 questions) | 0.789 (38) | 0.85 |
| Recall@5 | 0.963 | 0.842 | 0.90 |
| Uncovered questions correctly blocked | 0.938 | 0.562 | — |

The 11 questions on the code were added before indexing and not changed after. Two effects:
the code's passages are close enough to many uncovered questions (inheritance, building
permits) that the retrieval gate no longer blocks them, and three mortgage questions now
retrieve the code's mortgage articles ahead of their gold article. Per the standing rule, the
gate, its targets and the questions were not adjusted. Shipping the code needs a design change
measured on fresh questions (for example routing by legal domain before retrieval), not a
lower threshold.

## Legal status of the texts

Tunisian official texts are **not protected by copyright**. Law No. 94-36 of 24 February 1994 on
literary and artistic property, article 1, excludes "les textes officiels d'ordre législatif,
administratif ou judiciaire et leurs traductions officielles" ([WIPO Lex](https://www.wipo.int/edocs/lexdocs/laws/fr/tn/tn022fr.pdf)).
The laws and codes themselves can therefore be reused. A third party's compilation, editing or
website terms can still apply to *their copy*, which is why official copies are preferred below.

## Sources found

| Source | What it offers | Assessment |
| --- | --- | --- |
| [legislation.tn](http://www.legislation.tn/en), the national legal information portal | Constitution, the Official Journal (JORT), laws, decrees | Official. Reported to be intermittently unreachable. No bulk download seen |
| [justice.gov.tn, Codes juridiques](https://www.justice.gov.tn/index.php?id=223&L=3) | The main codes, incl. Code des droits réels and Code des obligations et des contrats | Official. Guides downloaded on 2026-09-30; the codes time out from here |
| Imprimerie Officielle (IORT) editions | Printed/PDF editions of the codes | Official publisher of the JORT |
| [data.gov.tn](https://www.data.gov.tn/fr/documentation-open-data/), the national open-data portal | Public datasets | Official. No legislation dataset seen; its terms page could not be verified (TLS error) |
| [droit-afrique.com](https://www.droit-afrique.com/upload/doc/tunisie/Tunisie-Code-2011-droits-reels.pdf) and similar | PDF copies of codes | Third party; its own terms apply. Avoid in favour of official copies |
| MustacharAI repository ([PR #53](https://github.com/AmineMabrouk17/MustacharAI/pull/53)) | 15 codes / 3,714 articles, cleaned text | Taken from a private mirror (9anoun.tn); no licence stated. Do not use |
| Hugging Face | Tunisian dialect/language corpora | No Tunisian legal corpus found |

## Next steps

1. **Serve the Code des droits réels**: it is verified and in the repository; what blocks it is
   retrieval, not the text. Route questions by legal domain before retrieval (the domain
   classifier already has property, leasing, zoning and inheritance categories), then validate
   on a fresh set of questions written before the change, with the same activation gate.
2. **COC and urban-planning code**: get the JORT texts (IORT, or the ministry once its links are
   fixed) to settle the differing words, then run the same comparison.
3. Still missing: the full registration and stamp duties code, property acquisition by
   foreigners (governor's authorisation), residential leases.
