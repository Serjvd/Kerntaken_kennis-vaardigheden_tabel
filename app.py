import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Functie om "Vakkennis en vaardigheden" en werkprocessen te extraheren
def extract_vakkennis_en_werkprocessen(pdf_file):
    vakkennis_dict = {}  # Voor kennis/vaardigheden per kerntaak
    werkprocessen_dict = {}  # Voor werkprocessen per kerntaak
    werkprocessen_beschrijvingen = {}  # Voor beschrijvingen van werkprocessen
    current_kerntaak = None
    in_vakkennis_block = False
    in_werkproces_block = False
    aanvullend_block = False
    raw_text = []  # Voor debugging
    current_uitspraak = ""  # Voor uitspraken die over meerdere regels lopen
    current_werkproces = None  # Huidig werkproces
    current_werkproces_beschrijving = ""  # Beschrijving van het huidige werkproces
    debug_log = []  # Voor extra debugging-informatie
    kerntaak_history = []  # Lijst om alle gedetecteerde kerntaken en hun posities bij te houden
    current_section = None  # Houd bij of we in "Basisdeel" of "Profieldeel" zitten

    # Regex voor kerntaken (zoals B1-K1, P2-K1)
    kerntaak_pattern = re.compile(r"(B\d+-K\d+|P\d+-K\d+):")
    # Regex voor werkprocessen (zoals B1-K1-W1)
    werkproces_pattern = re.compile(r"(B\d+-K\d+-W\d+|P\d+-K\d+-W\d+):")
    # Regex om ongewenste tekst (zoals "7 van 18" of "P2-K1 Organiseert...") te verwijderen
    cleanup_pattern = re.compile(r"\d+ van \d+|(?:B|P)\d+-K\d+(?:-W\d+)?(?:[^\n]*Organiseert[^\n]*)?$")
    target_words = ["heeft", "kan", "kent", "weet", "past", "bezit"]  # Aangepast om "bezit" toe te voegen
    # Indicatoren om het einde van een "Vakkennis en vaardigheden"-blok te detecteren
    end_block_indicators = [
        "Complexiteit", "Verantwoordelijkheid en zelfstandigheid", "Omschrijving",
        "Profieldeel", "Mbo-niveau", "Typering van het beroep", "Beroepsvereisten",
        "Generieke onderdelen", "Inhoudsopgave", "Leeswijzer", "Overzicht van het kwalificatiedossier",
        "Basisdeel", "Resultaat", "Gedrag"
    ]
    # Indicatoren om het einde van een werkprocesbeschrijving te detecteren
    werkproces_end_indicators = [
        "Complexiteit", "Verantwoordelijkheid en zelfstandigheid", "Omschrijving",
        "Profieldeel", "Mbo-niveau", "Typering van het beroep", "Beroepsvereisten",
        "Generieke onderdelen", "Inhoudsopgave", "Leeswijzer", "Overzicht van het kwalificatiedossier",
        "Basisdeel", "Resultaat", "Gedrag", "Vakkennis en vaardigheden",
        "Voor Metselaar geldt aanvullend:"
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
                return {}, {}, {}, raw_text, debug_log

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
                            cleaned_uitspraak = cleanup_pattern.sub("", current_uitspraak).strip()
                            if cleaned_uitspraak not in vakkennis_dict[current_kerntaak]:
                                vakkennis_dict[current_kerntaak].append(cleaned_uitspraak)
                                debug_log.append(f"Uitspraak toegevoegd aan {current_kerntaak}: {cleaned_uitspraak}")
                    # Sla de huidige werkprocesbeschrijving op (indien aanwezig)
                    if current_werkproces and current_werkproces_beschrijving:
                        werkprocessen_beschrijvingen[current_werkproces] = current_werkproces_beschrijving.strip()
                        debug_log.append(f"Werkprocesbeschrijving toegevoegd aan {current_werkproces}: {current_werkproces_beschrijving}")
                        if not current_werkproces_beschrijving.strip():
                            debug_log.append(f"Waarschuwing: Geen beschrijving gevonden voor {current_werkproces}, gebruik titel als fallback")
                            werkprocessen_beschrijvingen[current_werkproces] = current_werkproces
                    current_uitspraak = ""
                    current_werkproces = None
                    current_werkproces_beschrijving = ""
                    current_kerntaak = kerntaak_match.group(1)
                    kerntaak_history.append((current_kerntaak, line_idx, current_section))
                    if current_kerntaak not in vakkennis_dict:
                        vakkennis_dict[current_kerntaak] = []
                    if current_kerntaak not in werkprocessen_dict:
                        werkprocessen_dict[current_kerntaak] = []
                    debug_log.append(f"Nieuwe kerntaak gedetecteerd: {current_kerntaak} (sectie: {current_section})")
                    in_vakkennis_block = False
                    in_werkproces_block = False
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
                        in_werkproces_block = False
                        debug_log.append(f"Vakkennis en vaardigheden-blok gestart voor {current_kerntaak} (sectie: {current_section})")
                    else:
                        debug_log.append("Vakkennis en vaardigheden-blok gedetecteerd, maar geen relevante kerntaak gevonden")
                    continue

                # Detecteer werkproces
                werkproces_match = werkproces_pattern.search(line)
                if werkproces_match and current_kerntaak:
                    # Sla de huidige werkprocesbeschrijving op (indien aanwezig)
                    if current_werkproces and current_werkproces_beschrijving:
                        werkprocessen_beschrijvingen[current_werkproces] = current_werkproces_beschrijving.strip()
                        debug_log.append(f"Werkprocesbeschrijving toegevoegd aan {current_werkproces}: {current_werkproces_beschrijving}")
                        if not current_werkproces_beschrijving.strip():
                            debug_log.append(f"Waarschuwing: Geen beschrijving gevonden voor {current_werkproces}, gebruik titel als fallback")
                            werkprocessen_beschrijvingen[current_werkproces] = current_werkproces
                    current_werkproces_beschrijving = ""
                    current_werkproces = werkproces_match.group(1)
                    if current_kerntaak not in werkprocessen_dict:
                        werkprocessen_dict[current_kerntaak] = []
                    if current_werkproces not in werkprocessen_dict[current_kerntaak]:
                        werkprocessen_dict[current_kerntaak].append(current_werkproces)
                    in_werkproces_block = True
                    in_vakkennis_block = False
                    debug_log.append(f"Werkproces gedetecteerd: {current_werkproces} onder {current_kerntaak}")
                    # Voeg de huidige regel (minus de ID) toe aan de beschrijving
                    werkproces_title = line.replace(current_werkproces + ":", "").strip()
                    if werkproces_title:
                        current_werkproces_beschrijving += werkproces_title + " "
                    continue

                # Detecteer aanvullend blok
                if "Voor Metselaar geldt aanvullend:" in line and current_kerntaak:
                    aanvullend_block = True
                    debug_log.append("Aanvullend blok voor Metselaar gestart")
                    continue

                # Detecteer einde van "Vakkennis en vaardigheden"-blok
                if any(indicator in line for indicator in end_block_indicators):
                    if current_uitspraak and current_kerntaak and in_vakkennis_block:
                        if any(current_uitspraak.startswith(word + " ") for word in target_words):
                            cleaned_uitspraak = cleanup_pattern.sub("", current_uitspraak).strip()
                            if cleaned_uitspraak not in vakkennis_dict[current_kerntaak]:
                                vakkennis_dict[current_kerntaak].append(cleaned_uitspraak)
                                debug_log.append(f"Uitspraak toegevoegd aan {current_kerntaak}: {cleaned_uitspraak}")
                    current_uitspraak = ""
                    in_vakkennis_block = False
                    aanvullend_block = False
                    debug_log.append(f"Vakkennis en vaardigheden-blok beëindigd door indicator: {line}")
                    continue

                # Detecteer einde van werkprocesbeschrijving
                if in_werkproces_block and any(indicator in line for indicator in werkproces_end_indicators):
                    if current_werkproces and current_werkproces_beschrijving:
                        werkprocessen_beschrijvingen[current_werkproces] = current_werkproces_beschrijving.strip()
                        debug_log.append(f"Werkprocesbeschrijving toegevoegd aan {current_werkproces}: {current_werkproces_beschrijving}")
                        if not current_werkproces_beschrijving.strip():
                            debug_log.append(f"Waarschuwing: Geen beschrijving gevonden voor {current_werkproces}, gebruik titel als fallback")
                            werkprocessen_beschrijvingen[current_werkproces] = current_werkproces
                    current_werkproces_beschrijving = ""
                    in_werkproces_block = False
                    continue

                # Verwerk werkprocesbeschrijving
                if in_werkproces_block and current_werkproces:
                    if line and not line.isspace():  # Alleen niet-lege regels toevoegen
                        current_werkproces_beschrijving += " " + line

                # Verwerk kennis/vaardigheden
                if in_vakkennis_block and current_kerntaak:
                    cleaned_line = line.lstrip("-§ ").strip()
                    if not cleaned_line:  # Lege regel, sla op en reset
                        if current_uitspraak:
                            if any(current_uitspraak.startswith(word + " ") for word in target_words):
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
                    cleaned_uitspraak = cleanup_pattern.sub("", current_uitspraak).strip()
                    if cleaned_uitspraak not in vakkennis_dict[current_kerntaak]:
                        vakkennis_dict[current_kerntaak].append(cleaned_uitspraak)
                        debug_log.append(f"Laatste uitspraak toegevoegd aan {current_kerntaak}: {cleaned_uitspraak}")

            # Sla de laatste werkprocesbeschrijving op
            if current_werkproces and current_werkproces_beschrijving:
                werkprocessen_beschrijvingen[current_werkproces] = current_werkproces_beschrijving.strip()
                debug_log.append(f"Laatste werkprocesbeschrijving toegevoegd aan {current_werkproces}: {current_werkproces_beschrijving}")
                if not current_werkproces_beschrijving.strip():
                    debug_log.append(f"Waarschuwing: Geen beschrijving gevonden voor {current_werkproces}, gebruik titel als fallback")
                    werkprocessen_beschrijvingen[current_werkproces] = current_werkproces

    except Exception as e:
        st.error(f"Fout bij het verwerken van de PDF: {e}")
        return {}, {}, {}, raw_text, debug_log

    return vakkennis_dict, werkprocessen_dict, werkprocessen_beschrijvingen, raw_text, debug_log

# Functie om kruistabel te maken, inclusief werkprocessen
def create_kruistabel(vakkennis_dict, werkprocessen_dict, werkprocessen_beschrijvingen):
    if not vakkennis_dict:
        return None, None, ["Geen vakkennis_dict beschikbaar"]

    # Verzamel alle kerntaken en werkprocessen
    kerntaken = list(vakkennis_dict.keys())
    alle_werkprocessen = []
    for kerntaak in werkprocessen_dict:
        alle_werkprocessen.extend(werkprocessen_dict[kerntaak])
    alle_werkprocessen = sorted(list(set(alle_werkprocessen)))  # Unieke werkprocessen, gesorteerd

    # Verzamel alle unieke uitspraken
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

    # Voeg kolommen toe voor kerntaken
    for kerntaak in kerntaken:
        display_data[kerntaak] = ["×" if uitspraak in vakkennis_dict[kerntaak] else "" for uitspraak in uitspraken]
        sort_data[kerntaak] = [1 if uitspraak in vakkennis_dict[kerntaak] else 0 for uitspraak in uitspraken]

    # Voeg kolommen toe voor werkprocessen
    for werkproces in alle_werkprocessen:
        display_data[werkproces] = [""] * len(uitspraken)
        sort_data[werkproces] = [0] * len(uitspraken)

    # Lijst om koppelingen op te slaan voor debugging
    koppelingen_log = []
    # Dictionary om fallback-koppelingen bij te houden: {uitspraak: werkproces}
    fallback_koppelingen = {}

    # Dynamische stopwoorden genereren op basis van werkproces-ID's
    stopwoorden = {"en", "de", "het", "een", "voor", "met", "in", "op", "aan", "van", "bij", "is", "zijn"}
    for wp in alle_werkprocessen:
        stopwoorden.add(wp.lower())  # Voeg werkproces-ID's toe als stopwoorden
        stopwoorden.add(wp.lower().replace("-", ""))  # Voeg ook zonder streepjes toe (bijv. "b1k1w1")

    # Extraheer trefwoorden uit werkprocesbeschrijvingen voor de fallback
    werkproces_trefwoorden = {}
    for werkproces in alle_werkprocessen:
        beschrijving = werkprocessen_beschrijvingen.get(werkproces, werkproces)
        woorden = beschrijving.lower().split()
        trefwoorden = [woord for woord in woorden if woord not in stopwoorden and len(woord) > 3]
        werkproces_trefwoorden[werkproces] = trefwoorden

    # Koppel uitspraken aan werkprocessen
    vectorizer = TfidfVectorizer(stop_words=list(stopwoorden), min_df=1)
    for kerntaak in kerntaken:
        if kerntaak not in werkprocessen_dict or not werkprocessen_dict[kerntaak]:
            koppelingen_log.append(f"Geen werkprocessen voor kerntaak {kerntaak}")
            continue  # Geen werkprocessen voor deze kerntaak

        # Verzamel alle uitspraken voor deze kerntaak
        kerntaak_uitspraken = vakkennis_dict[kerntaak]
        # Verzamel alle werkprocessen voor deze kerntaak
        kerntaak_werkprocessen = werkprocessen_dict[kerntaak]
        # Verzamel de beschrijvingen van de werkprocessen
        werkproces_texts = [werkprocessen_beschrijvingen.get(wp, wp) for wp in kerntaak_werkprocessen]

        for uitspraak in kerntaak_uitspraken:
            # Maak een lijst van teksten: de uitspraak + alle werkprocesbeschrijvingen
            texts = [uitspraak] + werkproces_texts
            best_werkproces = None
            used_fallback = False

            # Probeer tekstanalyse
            try:
                tfidf_matrix = vectorizer.fit_transform(texts)
                similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])[0]
                max_similarity = max(similarities)
                if max_similarity > 0.2:  # Drempelwaarde voor een goede match
                    best_match_idx = similarities.argmax()
                    best_werkproces = kerntaak_werkprocessen[best_match_idx]
                    koppelingen_log.append(f"Koppel {uitspraak} aan {best_werkproces} (similarity: {max_similarity})")
                else:
                    # Geen goede match, gebruik fallback
                    used_fallback = True
            except ValueError:
                # Tekstanalyse mislukt (bijvoorbeeld door lege teksten), gebruik fallback
                used_fallback = True

            # Fallback: gebruik trefwoorden om een werkproces te kiezen
            if used_fallback:
                uitspraak_woorden = [woord for woord in uitspraak.lower().split() if woord not in stopwoorden and len(woord) > 3]
                beste_score = 0
                for wp in kerntaak_werkprocessen:
                    trefwoorden = werkproces_trefwoorden.get(wp, [])
                    score = sum(1 for woord in uitspraak_woorden if woord in trefwoorden)
                    if score > beste_score:
                        beste_score = score
                        best_werkproces = wp
                if not best_werkproces or beste_score == 0:
                    # Als er geen match is, kies het werkproces met de meeste trefwoorden
                    trefwoord_counts = {wp: len(werkproces_trefwoorden.get(wp, [])) for wp in kerntaak_werkprocessen}
                    best_werkproces = max(trefwoord_counts, key=trefwoord_counts.get)
                koppelingen_log.append(f"Koppel {uitspraak} aan {best_werkproces} (fallback, score: {beste_score})")
                fallback_koppelingen[uitspraak] = best_werkproces

            # Markeer de uitspraak in de kolom van het beste werkproces
            uitspraak_idx = uitspraken.index(uitspraak)
            display_data[best_werkproces][uitspraak_idx] = "×"
            sort_data[best_werkproces][uitspraak_idx] = 1

    # Maak DataFrames
    display_df = pd.DataFrame(display_data)
    sort_df = pd.DataFrame(sort_data)

    # Maak een stijltoepassing om fallback-koppelingen geel te markeren
    def highlight_fallback(val, row_idx, col_name):
        uitspraak = display_df.iloc[row_idx]["Uitspraak"]
        if val == "×" and col_name in alle_werkprocessen:  # Controleer alleen werkproceskolommen
            if uitspraak in fallback_koppelingen and fallback_koppelingen[uitspraak] == col_name:
                return "background-color: yellow"
        return ""

    # Pas de stijl toe op de DataFrame
    styled_df = display_df.style.apply(
        lambda x: [highlight_fallback(x[col], idx, col) for idx, col in enumerate(display_df.columns)],
        axis=1
    )

    return styled_df, sort_df, koppelingen_log

# Streamlit-interface
def main():
    st.title("Kwalificatiedossier Analyse")
    st.write("Upload een PDF-bestand van een kwalificatiedossier om een kruistabel te genereren.")

    # Bestandsupload
    uploaded_file = st.file_uploader("Kies een PDF-bestand", type="pdf")

    if uploaded_file is not None:
        # Verwerk het geüploade bestand
        vakkennis_dict, werkprocessen_dict, werkprocessen_beschrijvingen, raw_text, debug_log = extract_vakkennis_en_werkprocessen(uploaded_file)

        if vakkennis_dict:
            styled_df, sort_df, koppelingen_log = create_kruistabel(vakkennis_dict, werkprocessen_dict, werkprocessen_beschrijvingen)
            if styled_df is not None and not styled_df.data.empty:
                # Toon de kruistabel
                st.write("### Kruistabel")
                st.write("Klik op een kolomkop om te sorteren (oplopend/aflopend). Gele cellen geven aan dat de koppeling via een fallback is gemaakt (geen sterke tekstmatch).")
                st.dataframe(
                    styled_df,
                    use_container_width=True,
                    column_config={
                        col: st.column_config.Column(
                            help=f"Klik om te sorteren op {col}" if col != "Uitspraak" else None
                        ) for col in styled_df.data.columns
                    }
                )

                # Downloadknop voor Excel
                output = BytesIO()
                styled_df.data.to_excel(output, index=False)
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
