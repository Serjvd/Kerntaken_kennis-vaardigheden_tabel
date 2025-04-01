import pdfplumber
import pandas as pd
import re

# Functie om "Vakkennis en vaardigheden"-blokken te extraheren uit een PDF
def extract_vakkennis_en_vaardigheden(pdf_path):
    vakkennis_dict = {}
    current_kerntaak = None
    in_vakkennis_block = False
    aanvullend_block = False

    # Regex om kerntaken te herkennen (zoals B1-K1, B1-K2, P2-K1)
    kerntaak_pattern = re.compile(r"(B\d+-K\d+|P\d+-K\d+):")
    # Woorden om uitspraken te filteren
    target_words = ["heeft", "kan", "kent", "weet", "past toe"]

    # Open en lees de PDF met pdfplumber
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"

            # Verwerk de tekst regel voor regel
            for line in full_text.split("\n"):
                line = line.strip()

                # Detecteer kerntaak
                kerntaak_match = kerntaak_pattern.search(line)
                if kerntaak_match:
                    current_kerntaak = kerntaak_match.group(1)
                    in_vakkennis_block = False
                    aanvullend_block = False
                    if current_kerntaak not in vakkennis_dict:
                        vakkennis_dict[current_kerntaak] = []
                    continue

                # Detecteer start van "Vakkennis en vaardigheden"
                if "Vakkennis en vaardigheden" in line:
                    in_vakkennis_block = True
                    continue

                # Detecteer aanvullend blok voor Allround betonreparateur
                if "Voor Allround betonreparateur geldt aanvullend:" in line and current_kerntaak:
                    aanvullend_block = True
                    continue

                # Extraheer uitspraken als we in het juiste blok zitten
                if in_vakkennis_block and current_kerntaak:
                    # Controleer of de regel begint met een target-woord (met of zonder opsommingsteken)
                    cleaned_line = line.lstrip("- ").strip()
                    if any(cleaned_line.startswith(word + " ") for word in target_words):
                        uitspraak = cleaned_line
                        if uitspraak not in vakkennis_dict[current_kerntaak]:
                            vakkennis_dict[current_kerntaak].append(uitspraak)

    except FileNotFoundError:
        print(f"Fout: Het bestand '{pdf_path}' is niet gevonden.")
        return {}
    except Exception as e:
        print(f"Fout bij het verwerken van de PDF: {e}")
        return {}

    return vakkennis_dict

# Hoofdprogramma
def main(pdf_path):
    # Extraheer vakkennis en vaardigheden
    vakkennis_dict = extract_vakkennis_en_vaardigheden(pdf_path)
    
    if not vakkennis_dict:
        print("Geen gegevens gevonden om te verwerken. Controleer het PDF-bestand.")
        return

    kerntaken = list(vakkennis_dict.keys())

    # Verzamel alle unieke uitspraken in oorspronkelijke volgorde
    uitspraken = []
    for kerntaak in vakkennis_dict:
        for uitspraak in vakkennis_dict[kerntaak]:
            if uitspraak not in uitspraken:
                uitspraken.append(uitspraak)

    # Maak kruistabel
    data = {"Uitspraak": uitspraken}
    for kerntaak in kerntaken:
        data[kerntaak] = ["×" if uitspraak in vakkennis_dict[kerntaak] else "" for uitspraak in uitspraken]

    # Maak DataFrame
    df = pd.DataFrame(data)

    # Toon de tabel
    print(df.to_string(index=False))

    # Exporteer naar Excel
    output_file = "kruistabel_kwalificatiedossier.xlsx"
    df.to_excel(output_file, index=False)
    print(f"\nDe kruistabel is opgeslagen als '{output_file}'.")

# Start het programma
if __name__ == "__main__":
    # Geef het pad naar je PDF-bestand op
    pdf_file = "path/to/your/kwalificatiedossier.pdf"  # Vervang dit door het echte pad
    main(pdf_file)
