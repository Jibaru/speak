# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["wordfreq"]
# ///
from wordfreq import zipf_frequency

WORDS = "hice el deploy del hook en TypeScript y los tests pasan, el bug del useEffect está arreglado, revisa el pull request y el endpoint de la API, error tabla commit build feature branch merge listener componente staging cache token prompt plugin script framework".replace(",", "").split()
for w in WORDS:
    en, es = zipf_frequency(w, "en"), zipf_frequency(w, "es")
    print(f"{w:12} en={en:4.1f} es={es:4.1f} diff={en-es:+4.1f}")
