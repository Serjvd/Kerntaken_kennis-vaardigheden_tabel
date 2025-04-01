# app.py

import streamlit as st
import pandas as pd
import re
from io import BytesIO
from PyPDF2 import PdfReader
from collections import defaultdict

st.set_page_config(page_title="Kruistabel Kwalificatiedossier", layout="wide")
st.title("📊 Kruistabel Vakkennis en Vaardigheden")

st.markdown("Upload een PDF-bestand van een kwalificatiedossier (zoals Allround betonreparateur).")

uploaded_file = st.file_uploader("📥 Upload PDF", type="pdf")

if uploaded_file:
    pdf = PdfReader(uploaded_file)
    text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    # Zoek alle kerntaken (zoals B1-K1 of P2-K1)
    kerntaak_pattern = re.compile(r"(B\d-K\d|P\d-K\d)\b")
    kerntaken_blokken = {m.group(): m.start() for m in kerntaak_pattern.finditer(text)}
    kerntaken = sorted(kerntaken_blokken.keys(), key=lambda k: kerntaken_blokken[k])

    uitspraken_dict = defaultdict(set)
    all_uitspraken = []

    for i, code in enumerate(kerntaken):
        start = kerntaken_blokken[code]
        end = kerntaken_blokken[kerntaken[i + 1]] if i + 1 < len(kerntaken) else len(text)
        blok = text[start:end]

        # Vind blok 'Vakkennis en vaardigheden'
        match = re.search(r"Vakkennis en vaardigheden\n(.*?)\n(?:\S|$)", blok, re.DOTALL)
        if match:
            inhoud = match.group(1)

            # Voeg ook eventuele “Voor Allround beroep geldt aanvullend” toe
            aanvullend = re.findall(r"Voor Allround.*?:\n(.*?)(?=\n\S|$)", blok, re.DOTALL)
            if aanvullend:
                inhoud += "\n" + "\n".join(aanvullend)

            # Haal regels die beginnen met de juiste werkwoorden
            regels = re.findall(r"(?m)^\s*(heeft|kan|kent|weet|past toe)\b.*", inhoud)
            for regel in regels:
                regel = regel.strip()
                uitspraken_dict[regel].add(code)
                if regel not in all_uitspraken:
                    all_uitspraken.append(regel)

    # Kruistabel genereren
    data = []
    for u in all_uitspraken:
        row = {"Uitspraak": u}
        for k in kerntaken:
            row[k] = "×" if k in uitspraken_dict[u] else ""
        data.append(row)

    df = pd.DataFrame(data)

    st.success("✅ Kruistabel gegenereerd")
    st.dataframe(df, use_container_width=True)

    # Excel-download
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    st.download_button("💾 Download als Excel", buffer, file_name="kruistabel.xlsx")
