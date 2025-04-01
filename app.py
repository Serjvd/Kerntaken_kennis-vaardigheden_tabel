import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

# Functie om "Vakkennis en vaardigheden"-blokken te extraheren
def extract_vakkennis_en_vaardigheden(pdf_file):
    vakkennis_dict = {}
    current_kerntaak = None
    in_vakkennis_block = False
    aanvullend_block = False
    raw_text = []  # Voor debugging

    kerntaak_pattern = re.compile(r"(B\d+-K\d+|P\d+-K\d+):")
    target_words = ["heeft", "kan", "kent", "weet", "past toe"]

    try:
        with pdfplumber.open(pdf_file) as pdf:
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
                    raw_text.append(page_text)

            if not full_text.strip():
                st.warning("Geen tekst gevonden in de PDF. Is het bestand leeg of gescand?")
                return {}, raw_text

            for line in full_text.split("\n"):
                line = line.strip()
                kerntaak_match = kerntaak_pattern.search(line)
                if kerntaak_match:
                    current_kerntaak = kerntaak_match.group(1)
                    in_vakkennis_block = False
                    aanvullend_block = False
                    if current_kerntaak not in vakkennis_dict:
                        vakkennis_dict[current_kerntaak] = []
                    continue

                if "Vakkennis en vaardigheden" in line:
                    in_vakkennis_block = True
                    continue

                if "Voor Allround betonreparateur geldt aanvullend:" in line and current_kerntaak:
                    aanvullend_block = True
                    continue

                if in_vakkennis_block and current_kerntaak:
                    # Verwijder zowel "-" als "§" en strip whitespace
                    cleaned_line = line.lstrip("-§ ").strip()
                    if any(cleaned_line.startswith(word + " ") for word in target_words):
                        uitspraak = cleaned_line
                        if uitspraak and uitspraak not in vakkennis_dict[current_kerntaak]:
                            vakkennis_dict[current_kerntaak].append(uitspraak)

    except Exception as e:
        st.error(f"Fout bij het verwerken van de PDF: {e}")
        return {}, raw_text

    return vakkennis_dict, raw_text

# Functie om kruistabel te maken
def create_kruistabel(vakkennis_dict):
    if not vakkennis_dict:
        return None

    kerntaken = list(vakkennis_dict.keys())
    uitspraken = []
    for kerntaak in vakkennis_dict:
        for uitspraak in vakkennis_dict[kerntaak]:
            if uitspraak not in uitspraken:
                uitspraken.append(uitspraak)

    data = {"Uitspraak": uitspraken}
    for kerntaak in kerntaken:
        data[kerntaak] = ["×" if uitspraak in vakkennis_dict[kerntaak] else "" for uitspraak in uitspraken]

    return pd.DataFrame(data)

# Streamlit-interface
def main():
    st.title("Kwalificatiedossier Analyse")
    st.write("Upload een PDF-bestand van een kwalificatiedossier om een kruistabel te genereren.")

    # Bestandsupload
    uploaded_file = st.file_uploader("Kies een PDF-bestand", type="pdf")

    if uploaded_file is not None:
        # Verwerk het geüploade bestand
        vakkennis_dict, raw_text = extract_vakkennis_en_vaardigheden(uploaded_file)

        # Debug: toon ruwe tekst
        with st.expander("Toon ruwe geëxtraheerde tekst (voor debugging)"):
            st.text_area("Ruwe tekst", "\n".join(raw_text), height=300)

        if vakkennis_dict:
            df = create_kruistabel(vakkennis_dict)
            if df is not None and not df.empty:
                # Toon de kruistabel
                st.write("### Kruistabel")
                st.dataframe(df)

                # Downloadknop voor Excel
                output = BytesIO()
                df.to_excel(output, index=False)
                output.seek(0)
                st.download_button(
                    label="Download Excel-bestand",
                    data=output,
                    file_name="kruistabel_kwalificatiedossier.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Geen geldige gegevens gevonden in het PDF-bestand.")
        else:
            st.warning("Geen 'Vakkennis en vaardigheden'-blokken gevonden in de PDF.")

if __name__ == "__main__":
    main()
