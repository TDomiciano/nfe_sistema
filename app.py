import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import gc
import zipfile
import io

# =========================
# CONFIG
# =========================
st.set_page_config(
    layout="wide",
    page_title="Domiciano Auditor Fiscal"
)

st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-left: 3rem;
    padding-right: 3rem;
    max-width: 100%;
}
</style>
""", unsafe_allow_html=True)

# =========================
# REGRAS
# =========================
@st.cache_data
def carregar_regras():
    regras = pd.read_excel("conf_fiscais.xlsx", sheet_name="Config Fiscal")
    regras_st = pd.read_excel("conf_fiscais.xlsx", sheet_name="Config ST")
    return regras, regras_st

regras, regras_st = carregar_regras()

# =========================
# PRÉ-OTIMIZAÇÃO (MUITO IMPORTANTE)
# =========================
regras["ncm_str"] = regras["ncm"].astype(str).str.replace(".0", "", regex=False).str.strip()
regras["origem_str"] = regras["origem"].astype(str).str.upper().str.strip()
regras["destino_str"] = regras["destino"].astype(str).str.upper().str.strip()

regras_st["ncm_str"] = regras_st["ncm"].astype(str).str.replace(".0", "", regex=False).str.strip()
regras_st["origem_str"] = regras_st["origem"].astype(str).str.upper().str.strip()
regras_st["destino_str"] = regras_st["destino"].astype(str).str.upper().str.strip()

# =========================
# XML SAFE
# =========================
def get_text(element, tag, ns):
    if element is None:
        return ""
    found = element.find(tag, ns)
    return found.text if found is not None else ""

# =========================
# DIFAL (SUA LÓGICA MANTIDA)
# =========================
def calcular_difal(valor, aliq_inter=0.12, aliq_interna=0.18):
    icms_origem = valor * aliq_inter
    base1 = valor - icms_origem
    base2 = base1 / (1 - aliq_interna)
    icms_interno = base2 * aliq_interna
    return round(icms_interno - icms_origem, 2)
dados = []
chaves_canceladas = set()

uploads = st.file_uploader(
    "Envie XML ou ZIP",
    type=["xml", "zip"],
    accept_multiple_files=True
)

arquivos = []

if uploads:
    for upload in uploads:
        if upload.name.endswith(".xml"):
            arquivos.append(upload)

        elif upload.name.endswith(".zip"):
            with zipfile.ZipFile(upload, "r") as z:
                for nome in z.namelist():
                    if nome.endswith(".xml"):
                        xml_file = io.BytesIO(z.read(nome))
                        xml_file.name = nome
                        arquivos.append(xml_file)

# =========================
# PROCESSAMENTO
# =========================
if arquivos:

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    barra = st.progress(0)

    for i, arq in enumerate(arquivos):

        try:
            arq.seek(0)
            root = ET.parse(arq).getroot()

            if root.find(".//nfe:infEvento", ns) is not None:
                continue

            ide = root.find(".//nfe:ide", ns)
            emit = root.find(".//nfe:emit", ns)
            dest = root.find(".//nfe:dest", ns)

            uf_origem = get_text(emit.find("nfe:enderEmit", ns) if emit else None, "nfe:UF", ns)
            uf_destino = get_text(dest.find("nfe:enderDest", ns) if dest else None, "nfe:UF", ns)

            cnpj = get_text(dest, "nfe:CNPJ", ns)
            cpf = get_text(dest, "nfe:CPF", ns)
            documento = cnpj if cnpj else cpf

            tipo_cliente = "PJ" if cnpj else "PF"

            ie_dest = ""
            if dest is not None:
                ie_tag = dest.find(".//nfe:IE", ns)
                ie_dest = ie_tag.text if ie_tag is not None else ""

            chave = ""
            inf_nfe = root.find(".//nfe:infNFe", ns)
            if inf_nfe is not None:
                chave = inf_nfe.attrib.get("Id", "").replace("NFe", "")

            status = "AUTORIZADA"
            if chave in chaves_canceladas:
                status = "CANCELADA"

            itens = root.findall(".//nfe:det", ns)

            for item in itens:

                prod = item.find("nfe:prod", ns)
                imposto = item.find("nfe:imposto", ns)

                icms = None
                icms_ufdest = None

                if imposto is not None:
                    for child in imposto:
                        tag = child.tag.split("}")[-1]
                        if "ICMSUFDest" in tag:
                            icms_ufdest = child
                        elif "ICMS" in tag:
                            icms = child

                ncm = get_text(prod, "nfe:NCM", ns)
                cfop_xml = get_text(prod, "nfe:CFOP", ns)
                produto = get_text(prod, "nfe:xProd", ns)
                codigo = get_text(prod, "nfe:cProd", ns)
                qtd = get_text(prod, "nfe:qCom", ns)

                valor_prod = float(get_text(prod, "nfe:vProd", ns) or 0)
                valor_desc = float(get_text(prod, "nfe:vDesc", ns) or 0)
                valor_total = valor_prod - valor_desc

                # =========================
                # DIFAL (OTIMIZADO)
                # =========================
                difal_xml = float(get_text(icms_ufdest, "nfe:vICMSUFDest", ns) or 0)

                difal_calc = calcular_difal(valor_total)

                difal_diff = round(difal_xml - difal_calc, 2)

                status_difal = (
                    "OK"
                    if abs(difal_diff) <= 0.01
                    else "DIVERGENTE"
                )

                # =========================
                # REGRA FISCAL (RÁPIDO)
                # =========================
                filtro = regras[
                    (regras["ncm_str"] == str(ncm).replace(".0","").strip()) &
                    (regras["origem_str"] == uf_origem.upper().strip()) &
                    (regras["destino_str"] == uf_destino.upper().strip())
                ]

                regra = filtro.iloc[0] if not filtro.empty else None

                divergencias = []

                if regra is None:
                    divergencias.append("SEM REGRA FISCAL")

                dados.append({
                    "NF": get_text(ide, "nfe:nNF", ns),
                    "Serie": get_text(ide, "nfe:serie", ns),
                    "Status": status,
                    "Chave": chave,
                    "CPF/CNPJ": documento,
                    "IE": ie_dest,
                    "Destinatario": get_text(dest, "nfe:xNome", ns),
                    "UF Origem": uf_origem,
                    "UF Destino": uf_destino,
                    "Produto": produto,
                    "Codigo": codigo,
                    "Qtd": qtd,
                    "NCM": ncm,
                    "CFOP": cfop_xml,
                    "Valor Produto Total": valor_total,
                    "DIFAL XML": difal_xml,
                    "DIFAL Calculado": difal_calc,
                    "Diferença DIFAL": difal_diff,
                    "Status DIFAL": status_difal,
                    "Divergências": " | ".join(divergencias)
                })

            barra.progress((i + 1) / len(arquivos))

        except Exception as e:
            st.error(f"Erro XML {arq.name}: {e}")