import os
import re
import streamlit as st
from agents.data_agent import DataAgent
from agents.personalization_agent import PersonalizationAgent
from agents.merge_agent import MergeAgent
from agents.validation_agent import ValidationAgent
from agents.output_agent import OutputAgent
from tools.pdf_converter import convert_to_pdf

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXCEL = os.path.join(BASE, "input", "data.xlsx")
DEFAULT_TEMPLATE = os.path.join(BASE, "input", "certificate_template.docx")
OUTPUT = os.path.join(BASE, "output")

st.set_page_config(page_title="Agentic AI Mail Merge", page_icon="📜", layout="centered")
st.title("📜 Agentic AI Mail Merge")
st.write("Generate personalized certificates from an Excel recipient list and a Word certificate template.")

with st.expander("How the agents work"):
    st.markdown("""
    1. **Data Agent** – finds and validates the `Names` column.
    2. **Personalization Agent** – cleans each recipient name.
    3. **Merge Agent** – replaces the sample name in the certificate.
    4. **Validation Agent** – checks every generated certificate.
    5. **Output Agent** – creates one ZIP containing the certificates.
    """)

excel_upload = st.file_uploader("Upload Excel file (.xlsx)", type=["xlsx"])
template_upload = st.file_uploader("Upload certificate template (.docx)", type=["docx"])
make_pdf = st.checkbox("Also create PDF files (requires LibreOffice)", value=False)

if st.button("🚀 Generate Certificates", type="primary"):
    os.makedirs(OUTPUT, exist_ok=True)
    for filename in os.listdir(OUTPUT):
        path = os.path.join(OUTPUT, filename)
        if os.path.isfile(path):
            os.remove(path)

    excel_path = DEFAULT_EXCEL
    template_path = DEFAULT_TEMPLATE

    if excel_upload:
        excel_path = os.path.join(BASE, "input", "uploaded_data.xlsx")
        with open(excel_path, "wb") as file:
            file.write(excel_upload.getbuffer())

    if template_upload:
        template_path = os.path.join(BASE, "input", "uploaded_template.docx")
        with open(template_path, "wb") as file:
            file.write(template_upload.getbuffer())

    try:
        recipients = DataAgent().run(excel_path)
        st.info(f"Data Agent found {len(recipients)} recipient records.")

        personalizer = PersonalizationAgent()
        merger = MergeAgent()
        validator = ValidationAgent()
        progress = st.progress(0)
        valid = 0
        errors = []
        used_names = set()

        for index, (_, row) in enumerate(recipients.iterrows(), start=1):
            values = personalizer.run(row)
            display_name = values["display_name"]
            safe_name = re.sub(r"[^A-Za-z0-9 _-]", "_", display_name).strip() or f"recipient_{index}"
            # Prevent accidental overwriting if two recipients have the same name.
            base_name = safe_name
            suffix = 2
            while safe_name.lower() in used_names:
                safe_name = f"{base_name}_{suffix}"
                suffix += 1
            used_names.add(safe_name.lower())

            out_docx = os.path.join(OUTPUT, f"{safe_name}.docx")
            merger.run(template_path, out_docx, display_name)
            ok, message = validator.run(out_docx, display_name)
            if ok:
                valid += 1
            else:
                errors.append(message)

            if make_pdf:
                pdf = convert_to_pdf(out_docx, OUTPUT)
                if pdf is None and index == 1:
                    st.warning("LibreOffice was not found. DOCX certificates will still be generated.")
            progress.progress(index / len(recipients))

        zip_path = os.path.join(BASE, "Mail_Merge_Output.zip")
        OutputAgent().package(OUTPUT, zip_path)
        st.success(f"Completed: {valid}/{len(recipients)} certificates validated.")
        if errors:
            st.warning("\n".join(errors[:5]))
        with open(zip_path, "rb") as file:
            st.download_button(
                "⬇️ Download Mail_Merge_Output.zip",
                file,
                file_name="Mail_Merge_Output.zip",
                mime="application/zip"
            )
    except Exception as error:
        st.error(f"Generation failed: {type(error).__name__}: {error}")
