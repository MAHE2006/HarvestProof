"""Download the public tea and chilli leaf datasets (CC BY 4.0) and lay them out as data/images/<class_id>/.
    python -m scripts.fetch_data
Sources and attribution: see DATA_SOURCES.md"""
import io, pathlib, shutil, urllib.request, zipfile

BASE = "https://codeload.github.com/ai-agriculture-circuits-and-systems/{}/zip/refs/heads/main"
SETS = {"tea_leaf_disease_classification": ("tea_leaves", {"gray_blight": "tea_greyblight", "brown_blight": "tea_brownblight", "algal_spot": "tea_algalspot",
                                                           "red_spot": "tea_redspot", "helopeltis": "tea_helopeltis", "healthy": "tea_healthy"}),
        "chilli_leaf_classification": ("chillies", {"cercospora": "chilli_cercospora", "powdery_mildew": "chilli_powdery", "murda_complex_mites_trips": "chilli_murda",
                                                    "nutritional": "chilli_nutritional", "healthy": "chilli_healthy"})}
out = pathlib.Path("data/images")
for repo, (folder, mp) in SETS.items():
    print("downloading", repo)
    z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(BASE.format(repo), timeout=600).read()))
    n = 0
    for name in z.namelist():
        parts = name.split("/")
        if len(parts) >= 5 and parts[1] == folder and parts[3] == "images" and parts[2] in mp and name.lower().endswith((".jpg", ".jpeg", ".png")):
            d = out / mp[parts[2]]
            d.mkdir(parents=True, exist_ok=True)
            with z.open(name) as src, open(d / parts[-1], "wb") as dst:
                shutil.copyfileobj(src, dst)
            n += 1
    print(f"  {n} images")
