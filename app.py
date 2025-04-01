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
    current_uitspraak = ""  # Voor uitspraken die over meerdere regels lopen
    debug_log = []  # Voor extra debugging-informatie
    kerntaak_history = []  # Lijst om alle gedetecteerde kerntaken en hun posities bij te houden
    current_section = None  # Houd bij of we in "Basisdeel" of "Profieldeel" zitten

    # Regex voor kerntaken (zoals B1-K1, P2-K1)
    kerntaak_pattern = re.compile(r"(B\d+-K\d+|P\d+-K\d+):")
    # Regex om ongewenste tekst (zoals "7 van 20" of "P2-K1 Organiseert...") te verwijderen
    cleanup_pattern = re.compile(r"\d+ van \d+|(?:B|P)\d+-K\d+(?:-W\d+)?(?:[^\n]*Organiseert[^\n]*)?$")
    target_words = ["heeft", "kan", "kent", "weet", "past toe"]
    # Indicatoren om het einde van een "Vakkennis en vaardigheden"-blok te detecteren
    end_block_indicators = [
        "Complexiteit", "Verantwoordelijkheid en zelfstandigheid", "Omschrijving",
        "Profieldeel", "Mbo-niveau", "Typering van het beroep", "Beroepsvereisten",
        "Generieke onderdelen", "Inhoudsopgave", "Leeswijzer", "Overzicht van het kwalificatiedossier",
        "Basisdeel", "Resultaat", "Gedrag"
    ]

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
                return {}, raw_text, debug_log

            # Splits de tekst in regels en verwerk ze
            lines = full_text.split("\n")
            for line_idx, line in enumerate(lines):
                line = line.strip()
                debug_log.append(f"Verwerk regel: {line}")

                # Detecteer secties (Basisdeel of Profieldeel)
                if "Basisdeel" in line:
                    current_section = "Basisdeel"
                    debug_log.append("Sectie gedetecteerd: Basisdeel")
                    continue
                if "Profieldeel" in line:
                    current_section = "Profieldeel"
                    debug_log.append("Sectie gedetecteerd: Profieldeel")
                    continue

                # Detecteer kerntaak
                kerntaak_match = kerntaak_pattern.search(line)
                if kerntaak_match:
                    # Sla de huidige uitspraak op (indien aanwezig)
                    if current_uitspraak and current_kerntaak and in_vakkennis_block:
                        if any(current_uitspraak.startswith(word + " ") for word in target_words):
                            # Schoon de uitspraak op
                            cleaned_uitspraak = cleanup_pattern.sub("", current_uitspraak).strip()
                            if cleaned_uitspraak not in vakkennis_dict[current_kerntaak]:
                                vakkennis_dict[current_kerntaak].append(cleaned_uitspraak)
                                debug_log.append(f"Uitspraak toegevoegd aan {current_kerntaak}: {cleaned_uitspraak}")
                    current_uitspraak = ""
                    current_kerntaak = kerntaak_match.group(1)
                    kerntaak_history.append((current_kerntaak, line_idx, current_section))  # Voeg kerntaak toe aan geschiedenis
                    if current_kerntaak not in vakkennis_dict:
                        vakkennis_dict[current_kerntaak] = []
                    debug_log.append(f"Nieuwe kerntaak gedetecteerd: {current_kerntaak} (sectie: {current_section})")
                    in_vakkennis_block = False  # Reset bij nieuwe kerntaak
                    aanvullend_block = False
                    continue

                # Detecteer start van "Vakkennis en vaardigheden"
                if "Vakkennis en vaardigheden" in line:
                    # Zoek de meest recente kerntaak vóór deze regel
                    relevant_kerntaak = None
                    for kerntaak, idx, section in reversed(kerntaak_history):
                        if idx < line_idx and section == current_section:
                            relevant_kerntaak = kerntaak
                            break
                    if relevant_kerntaak:
                        current_kerntaak = relevant_kerntaak
                        in_vakkennis_block = True
                        debug_log.append(f"Vakkennis en vaardigheden-blok gestart voor {current_kerntaak} (sectie: {current_section})")
                    else:
                        debug_log.append("Vakkennis en vaardigheden-blok gedetecteerd, maar geen relevante kerntaak gevonden")
                    continue

                # Detecteer aanvullend blok
                if "Voor Allround betonreparateur geldt aanvullend:" in line and current_kerntaak:
                    aanvullend_block = True
                    debug_log.append("Aanvullend blok voor Allround betonreparateur gestart")
                    continue

                # Detecteer einde van "Vakkennis en vaardigheden"-blok
                if any(indicator in line for indicator in end_block_indicators):
                    if current_uitspraak and current_kerntaak and in_vakkennis_block:
                        if any(current_uitspraak.startswith(word + " ") for word in target_words):
                            # Schoon de uitspraak op
                            cleaned_uitspraak = cleanup_pattern.sub("", current_uitspraak).strip()
                            if cleaned_uitspraak not in vakkennis_dict[current_kerntaak]:
                                vakkennis_dict[current_kerntaak].append(cleaned_uitspraak)
                                debug_log.append(f"Uitspraak toegevoegd aan {current_kerntaak}: {cleaned_uitspraak}")
                    current_uitspraak = ""
                    in_vakkennis_block = False
                    aanvullend_block = False
                    debug_log.append(f"Vakkennis en vaardigheden-blok beëindigd door indicator: {line}")
                    continue

                if in_vakkennis_block and current_kerntaak:
                    cleaned_line = line.lstrip("-§ ").strip()
                    if not cleaned_line:  # Lege regel, sla op en reset
                        if current_uitspraak:
                            if any(current_uitspraak.startswith(word + " ") for word in target_words):
                                # Schoon de uitspraak op
                                cleaned_uitspraak = cleanup_pattern.sub("", current_uitspraak).strip()
                                if cleaned_uitspraak not in vakkennis_dict[current_kerntaak]:
                                    vakkennis_dict[current_kerntaak].append(cleaned_uitspraak)
                                    debug_log.append(f"Uitspraak toegevoegd aan {current_kerntaak}: {cleaned_uitspraak}")
                            current_uitspraak = ""
                        continue

                    # Controleer of de regel begint met een target-woord
                    if any(cleaned_line.startswith(word + " ") for word in target_words):
                        # Sla de vorige uitspraak op (indien aanwezig)
                        if current_uitspraak:
                            if any(current_uitspraak.startswith(word + " ") for word in target_words):
                                # Schoon de uitspraak op
                                cleaned_uitspraak = cleanup_pattern.sub("", current_uitspraak).strip()
                                if cleaned_uitspraak not in vakkennis_dict[current_kerntaak]:
                                    vakkennis_dict[current_kerntaak].append(cleaned_uitspraak)
                                    debug_log.append(f"Uitspraak toegevoegd aan {current_kerntaak}: {cleaned_uitspraak}")
                        current_uitspraak = cleaned_line
                    else:
                        # Voeg toe aan de huidige uitspraak (voor meerregelige uitspraken)
                        if current_uitspraak:
                            current_uitspraak += " " + cleaned_line

            # Sla de laatste uitspraak op
            if current_uitspraak and current_kerntaak and in_vakkennis_block:
                if any(current_uitspraak.startswith(word + " ") for word in target_words):
                    # Schoon de uitspraak op
                    cleaned_uitspraak = cleanup_pattern.sub("", current_uitspraak).strip()
                    if cleaned_uitspraak not in vakkennis_dict[current_kerntaak]:
                        vakkennis_dict[current_kerntaak].append(cleaned_uitspraak)
                        debug_log.append(f"Laatste uitspraak toegevoegd aan {current_kerntaak}: {cleaned_uitspraak}")

    except Exception as e:
        st.error(f"Fout bij het verwerken van de PDF: {e}")
        return {}, raw_text, debug_log

    return vakkennis_dict, raw_text, debug_log

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

    # Sorteer de uitspraken alfabetisch
    uitspraken.sort()

    # Maak een DataFrame met zowel weergave- als sorteerdata
    display_data = {"Uitspraak": uitspraken}
    sort_data = {"Uitspraak": uitspraken}  # Voor sortering

    for kerntaak in kerntaken:
        # Weergave: "×" of leeg
        display_data[kerntaak] = ["×" if uitspraak in vakkennis_dict[kerntaak] else "" for uitspraak in uitspraken]
        # Sorteerdata: 1 voor "×", 0 voor leeg
        sort_data[kerntaak] = [1 if uitspraak in vakkennis_dict[kerntaak] else 0 for uitspraak in uitspraken]

    # Maak twee DataFrames: een voor weergave en een voor sortering
    display_df = pd.DataFrame(display_data)
    sort_df = pd.DataFrame(sort_data)

    return display_df, sort_df

# Streamlit-interface
def main():
    st.title("Kwalificatiedossier Analyse")
    st.write("Upload een PDF-bestand van een kwalificatiedossier om een kruistabel te genereren.")

    # Bestandsupload
    uploaded_file = st.file_uploader("Kies een PDF-bestand", type="pdf")

    if uploaded_file is not None:
        # Verwerk het geüploade bestand
        vakkennis_dict, raw_text, debug_log = extract_vakkennis_en_vaardigheden(uploaded_file)

        # Debug: toon ruwe tekst en debug-log
        with st.expander("Toon ruwe geëxtraheerde tekst (voor debugging)"):
            st.text_area("Ruwe tekst", "\n".join(raw_text), height=300)

        with st.expander("Toon debug-log"):
            st.text_area("Debug-log", "\n".join(debug_log), height=300)

        if vakkennis_dict:
            display_df, sort_df = create_kruistabel(vakkennis_dict)
            if display_df is not None and not display_df.empty:
                # Toon de kruistabel
                st.write("### Kruistabel")
                # Gebruik st.dataframe met de sorteerdata, maar toon de weergavedata
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    column_config={
                        col: st.column_config.Column(
                            help=f"Klik om te sorteren op {col}" if col != "Uitspraak" else None
                        ) for col in display_df.columns
                    }
                )

                # Downloadknop voor Excel
                output = BytesIO()
                display_df.to_excel(output, index=False)
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
