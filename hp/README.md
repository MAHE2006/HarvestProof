# HarvestProof

Check a leaf, check a pesticide pack, choose a spray that fits your harvest date, and give buyers a signed harvest passport.

- **Backend:** FastAPI + SQLModel (SQLite by default, PostgreSQL via `DATABASE_URL`), JWT login, HMAC-signed pack codes.
- **AI (`engine/`):** no neural network. Photo analysis measures spots and colour, a gradient-boosted model turns the measurements into
  calibrated probabilities, simple questions are fused in as evidence (asked in order of information gain), and the app says "uncertain" instead of guessing.
- **Frontend (`web/`):** plain HTML/JS served by the backend, with a guided four-step flow, a one-click demo and sample photos.

## Run it (VS Code terminal)
```bash
python -m venv .venv
.venv\Scripts\activate                 # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
set HP_SECRET=put-a-long-random-string-here        # Mac/Linux: export HP_SECRET=...
python -m uvicorn api.main:app --reload
```
Open http://localhost:8000 and press **Start the demo**. It comes with sample photos and sample pack codes (a genuine one, an expired one, a forged one and a cloned one) so every step works at once.
Tests: `python -m pytest tests -q` (12 tests: leaf features, training pipeline, waiting-period logic, planner, login, forged/cloned/expired packs, passport tamper check, data isolation).
The first account you create becomes the admin. Admins and issuers can create signed pack codes (below).

## What each step does
1. **Check the leaf.** Optional photo plus a few yes/no questions, each chosen because it removes the most doubt. It says "not sure" or "uncertain" rather than guess.
2. **Check the pack.** Shows a checklist: code format, registered batch, signature, expiry, and scan pattern (the same code scanned in many districts within hours suggests copies).
3. **Choose the spray.** Lists only products whose official label names your problem on your crop. Sprays that would make you wait past your harvest date, or repeat your last mode of action, are set aside with the reason.
4. **Passport.** Earliest safe harvest date per field, a timeline of sprays, EU-limit warnings, a print/PDF button, and a share link with a QR code and a signature that shows if the page was altered.

## What is real, and what is not
| Part | Status |
|---|---|
| Photo model, **tea** (6 classes) | Trained on public photos. On 822 held-out photos: **76.5% right**, well calibrated. Called "confident" for 60% of photos, and right **88.5%** of those. |
| Photo model, **chilli** (5 classes) | Trained on only 532 photos. On 79 held-out photos: **56% right**. A chilli photo alone is never treated as confident, so the app asks questions. |
| **Rice and grapes** | No photo model (no usable public photos). They work from your answers only. |
| Products, doses, waiting days (26 fungicides) | **Real** CIB&RC rows, transcribed by hand, see `DATA_SOURCES.md`. Verify against the official list and the product label. |
| EU residue limits | Only for 4 chilli products (APEDA list). Others show "not recorded". |
| Residue decay model | Switched off: needs measured residue data I could not find. Dates use the label waiting period. |
| Symptom probabilities (`question_likelihoods.csv`) | **My estimates.** They shape the questions for every crop. Replace with survey data. |
| Pack registry | Codes you issue are fully verified. A manufacturer's registry needs their data (below). |

Photos in the datasets are clear and on plain backgrounds. Expect lower accuracy on field photos until you add your own and retrain.
Nothing here has been field-tested with an agronomist.

## Pack codes
```bash
python -m scripts.issue TRICY75 B2603 --count 100        # product codes are in data/products.csv; prints signed codes
python -m scripts.import_batches registry.csv            # columns: batch_code,product_code,mfg,exp
```
Imported batches are checked by registry lookup only (no signature); write their codes as `BATCH-SERIAL-NA`. I could not obtain any manufacturer's batch data because it is not public: you need an agreement with them or the regulator.
Demo batches exist only while `HP_DEMO=1`. **Set `HP_DEMO=0` in production.**

## Retrain with your own photos
```bash
python -m scripts.fetch_data                  # public tea + chilli photos into data/images/<class_id>/
# add your own photos to the same folders, with the diagnosis confirmed by an agronomist
python -m engine.train --data data/images --workers 4     # about 8 minutes for 6,400 photos
```
Read `models/report.json` (accuracy, calibration, per-class recall, confusion matrix) before trusting a new model, then restart the server.
To add a crop or disease: add rows to `data/classes.csv`, `data/question_likelihoods.csv` and `data/efficacy.csv`, and a photo folder named after the class id. A crop needs photos for all its classes or none.
`models/image_model.joblib` can run code when loaded, so only load files you trained yourself.

## Deploy
Set `HP_SECRET` (long and random), `HP_DEMO=0` and `DATABASE_URL` (PostgreSQL recommended). `docker build -t harvestproof . && docker run -p 8000:8000 -e HP_SECRET=... -e HP_DEMO=0 harvestproof`.
Use HTTPS (camera and QR scanning need it), rate-limit `/api/login` and `/api/verify`, and back up the database.
Delete `harvestproof.db` after editing the label CSVs, which are only read when the database is first created.

## Limits
Advice, not a laboratory certificate. Have an agronomist confirm diagnoses on your farms, and have a lab test residues, before using a passport as proof with buyers.
