# Kwalificatiedossier Kruistabel Generator

📊 Streamlit-app om een kruistabel te genereren van uitspraken over vakkennis en vaardigheden per kerntaak of profielkerntaak in een Nederlands mbo-kwalificatiedossier (PDF).

## 🔧 Functionaliteit

- Upload een kwalificatiedossier in PDF-formaat (zoals Allround betonreparateur)
- App zoekt per kerntaak/profielkerntaak naar "Vakkennis en vaardigheden"
- Uitspraken worden exact en letterlijk overgenomen (geen interpretatie)
- Uitspraken beginnend met: _heeft_, _kan_, _kent_, _weet_, _past toe_
- Output is een kruistabel met kolommen: `Uitspraak`, `B1-K1`, `B1-K2`, `P2-K1`, ...
- Download als Excelbestand

## ▶️ Starten (lokaal)

1. Clone deze repo
2. Installeer de vereisten:

```bash
pip install -r requirements.txt
