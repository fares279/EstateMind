# Legal assistant corpus: where more text could legitimately come from

The legal assistant answers from 23 passages (registration duties and mortgage law), a hard
ceiling on what it can answer. As instructed, nothing has been scraped or downloaded. This page
is research only (2026-09-29), for a decision.

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
| [justice.gov.tn, Codes juridiques](https://www.justice.gov.tn/index.php?id=223&L=3) | The main codes, incl. Code des droits réels and Code des obligations et des contrats | Official. Could not be opened from here (connection reset); worth a manual visit |
| Imprimerie Officielle (IORT) editions | Printed/PDF editions of the codes | Official publisher of the JORT |
| [data.gov.tn](https://www.data.gov.tn/fr/documentation-open-data/), the national open-data portal | Public datasets | Official. No legislation dataset seen; its terms page could not be verified (TLS error) |
| [droit-afrique.com](https://www.droit-afrique.com/upload/doc/tunisie/Tunisie-Code-2011-droits-reels.pdf) and similar | PDF copies of codes | Third party; its own terms apply. Avoid in favour of official copies |
| MustacharAI repository ([PR #53](https://github.com/AmineMabrouk17/MustacharAI/pull/53)) | 15 codes / 3,714 articles, cleaned text | Taken from a private mirror (9anoun.tn); no licence stated. Do not use |
| Hugging Face | Tunisian dialect/language corpora | No Tunisian legal corpus found |

## Recommendation

The simplest legitimate route is for you to download the relevant official texts yourself, a
one-off and specific use rather than scraping, from justice.gov.tn, legislation.tn or IORT, and
put the files in the repository. `index_legal_data` then ingests them with their source
recorded. In priority order for property questions:

1. **Code des droits réels**: ownership, co-ownership, easements, land registration.
2. **Code des obligations et des contrats**: sale and lease contracts.
3. **Code de l'aménagement du territoire et de l'urbanisme**: zoning, building permits.
4. **Code des droits d'enregistrement et de timbre**: complete version (partly covered today).
5. Texts on **property acquisition by foreigners** (governor's authorisation regime).
6. Landlord–tenant legislation for residential leases.

The domain classifier already has categories for these topics (transactions, leasing, zoning,
foreign ownership, inheritance), so they would be used as soon as passages exist.
