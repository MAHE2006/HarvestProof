# Data sources and attribution

## Leaf photos (used to train and to demo the photo model)
- **Tea leaf diseases** (gray blight, brown blight, algal spot, red spot, Helopeltis damage, healthy): github.com/ai-agriculture-circuits-and-systems/tea_leaf_disease_classification. Licence stated by the repository: CC BY 4.0.
- **Chilli leaf diseases** (cercospora, powdery mildew, murda complex, nutrient deficiency, healthy): github.com/ai-agriculture-circuits-and-systems/chilli_leaf_classification. Licence stated by the repository: CC BY 4.0.
- Download them with `python -m scripts.fetch_data`. Please read each repository's README for the original authors and citation, and credit them wherever you publish results.
- No usable public photos were found for **rice blast** or **grape downy mildew**, so those crops work from your answers only. The only rice blast set found was behind a non-GitHub link and restricted to academic use.

## Pesticide labels (doses and waiting periods in `data/labels.csv`)
- Central Insecticides Board and Registration Committee (CIB&RC), Government of India, *Major Uses of Pesticides: Fungicides* (as on 31-03-2025). Rows were transcribed by hand from a public mirror of that list. **Verify every row against the official list at ppqs.gov.in and the printed product label before relying on it.**
- Mode-of-action codes (FRAC) in `data/products.csv` come from general knowledge. Verify against the FRAC code list.

## EU residue limits (`eu_mrl` column)
- APEDA / NRCG "List of chemicals with CIB&RC label claim for green chilli" (March 2026). Only chilli products on that list have a value. Everything else is blank and shown as "not recorded".

## Not from any source
- `data/question_likelihoods.csv` (how often each symptom appears with each problem) is **my estimate**, not survey data. Replace it with frequencies from a field survey checked by an agronomist.
- The efficacy value 0.8 means only that the CIB&RC list names that problem on that crop. It is not a measured efficacy.
