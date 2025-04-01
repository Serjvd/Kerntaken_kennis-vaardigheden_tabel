import streamlit as st
import pandas as pd
import re
from io import BytesIO
import pdfplumber
from collections import defaultdict

st.set_page_config(page_title="Kruistabel Kwalificatiedossier", layout="wide")
st.title("📊 Kruistabel Kennis & Vaardigheden per Kerntaak")

st.markdown("Upload een kwalificatiedossier in PDF-formaat van SBB. De app genereert een kruistabel van uitspraken per kerntaak.")

uploaded_file = st.file_uploader("📥 Upload PDF", type="pdf")

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    kerntaak_pattern = re.compile(r"(B\d-K\d|P\d-K\d)\b")
    kerntaken_blokken = {m.group(): m.start() for m in kerntaak_pattern.finditer(text)}
    kerntaken = sorted(kerntaken_blokken.keys(), key=lambda k: kerntaken_blokken[k])

    uitspraken_dict = defaultdict(set)
    all_uitspraken = []

    for i, code in enumerate(kerntaken):
        start = kerntaken_blokken[code]
        end = kerntaken_blokken[kerntaken[i + 1]] if i + 1 < len(kerntaken) else len(text)
        blok = text[start:end]

        # Zoek 'Vakkennis en vaardigheden'
        match = re.search(r"Vakkennis en vaardigheden\n(.*?)(?=\n\S|\Z)", blok, re.DOTALL)
        if match:
            inhoud = match.group(1)

            # Voeg aanvullingen toe
            aanvullend = re.findall(r"Voor Allround.*?:\n(.*?)(?=\n\S|$)", blok, re.DOTALL)
            if aanvullend:
                inhoud += "\n" + "\n".join(aanvullend)

            # Zoek uitspraken
            regels = re.findall(r"(?m)^\s*(heeft|kan|kent|weet|past toe)\b.*", inhoud)
            for regel in regels:
                regel = regel.strip()
                uitspraken_dict[regel].add(code)
                if regel not in all_uitspraken:
                    all_uitspraken.append(regel)

    if not all_uitspraken:
        st.error("⚠️ Er zijn geen uitspraken gevonden volgens het gevraagde format.")
    else:
        data = []
        for u in all_uitspraken:
            row = {"Uitspraak": u}
            for k in kerntaken:
                row[k] = "×" if k in uitspraken_dict[u] else ""
            data.append(row)

        df = pd.DataFrame(data)
        st.success("✅ Kruistabel gegenereerd")
        st.dataframe(df, use_container_width=True)

        buffer = BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)
        st.download_button("💾 Download als Excel", buffer, file_name="kruistabel.xlsx")
