import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import gc
import zipfile
import io

# =========================
# CONFIG PAGINA
# =========================
st.set_page_config(layout="wide")

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
# REGRAS (IGUAL AO SEU ORIGINAL)
# =========================
@st.cache_data
def carregar_regras():

    regras = pd.read_excel(
        "conf_fiscais.xlsx",
        sheet_name="Config Fiscal"
    )

    regras_st = pd.read_excel(
        "conf_fiscais.xlsx",
        sheet_name="Config ST"
    )

    return regras, regras_st


regras, regras_st = carregar_regras()

# =========================
# XML SAFE
# =========================
def get_text(element, tag, ns):

    if element is None:
        return ""

    found = element.find(tag, ns)

    return found.text if found is not None else ""

# =========================
# DIFAL BASE DUPLA
# =========================
def calcular_difal(valor, aliq_inter=0.12, aliq_interna=0.18):

    icms_origem = valor * aliq_inter
    base1 = valor - icms_origem
    base2 = base1 / (1 - aliq_interna)
    icms_interno = base2 * aliq_interna

    return round(icms_interno - icms_origem, 2)

# =========================
# INTERFACE
# =========================
st.title("📄 Leitor Fiscal NF-e + Auditor Completo")

st.info("XML + ZIP | Validação Fiscal + DIFAL + ST")

uploads = st.file_uploader(
    "Envie XML ou ZIP",
    type=["xml", "zip"],
    accept_multiple_files=True
)

arquivos = []

if uploads:

    for upload in uploads:

        if upload.name.lower().endswith(".xml"):
            arquivos.append(upload)

        elif upload.name.lower().endswith(".zip"):

            try:
                with zipfile.ZipFile(upload, 'r') as zip_ref:

                    for nome in zip_ref.namelist():

                        if nome.lower().endswith(".xml"):

                            xml_file = io.BytesIO(zip_ref.read(nome))
                            xml_file.name = nome
                            arquivos.append(xml_file)

            except Exception as e:
                st.error(f"Erro ZIP: {e}")

dados = []

# =========================
# PROCESSAMENTO
# =========================
if arquivos:

    st.write(f"📦 Total arquivos: {len(arquivos)}")

    barra = st.progress(0)

    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

    for i, arq in enumerate(arquivos):

        try:

            arq.seek(0)

            tree = ET.parse(arq)
            root = tree.getroot()

            ide = root.find('.//nfe:ide', ns)
            emit = root.find('.//nfe:emit', ns)
            dest = root.find('.//nfe:dest', ns)

            ender_emit = emit.find('nfe:enderEmit', ns) if emit is not None else None
            ender_dest = dest.find('nfe:enderDest', ns) if dest is not None else None

            uf_origem = get_text(ender_emit, 'nfe:UF', ns)
            uf_destino = get_text(ender_dest, 'nfe:UF', ns)

            cnpj = get_text(dest, 'nfe:CNPJ', ns)
            cpf = get_text(dest, 'nfe:CPF', ns)

            tipo_cliente = "PJ" if cnpj else "PF"
            documento = cnpj if cnpj else cpf

            ie_dest = ""
            if dest is not None:
                ie_tag = dest.find('.//nfe:IE', ns)
                ie_dest = ie_tag.text if ie_tag is not None else ""

            itens = root.findall('.//nfe:det', ns)

            for item in itens:

                prod = item.find('nfe:prod', ns)
                imposto = item.find('nfe:imposto', ns)

                icms = imposto.find('.//nfe:ICMS/*', ns) if imposto is not None else None
                icms_ufdest = imposto.find('.//nfe:ICMSUFDest', ns) if imposto is not None else None

                ncm_xml = get_text(prod, 'nfe:NCM', ns)
                cfop_xml = get_text(prod, 'nfe:CFOP', ns)
                produto = get_text(prod, 'nfe:xProd', ns)
                codigo = get_text(prod, 'nfe:cProd', ns)
                qtd = get_text(prod, 'nfe:qCom', ns)

                cst_xml = ""
                if icms is not None:
                    cst_xml = get_text(icms, 'nfe:CST', ns) or get_text(icms, 'nfe:CSOSN', ns)

                aliquota_xml = get_text(icms, 'nfe:pICMS', ns)

                valor_prod = float(get_text(prod, 'nfe:vProd', ns) or 0)
                valor_desc = float(get_text(prod, 'nfe:vDesc', ns) or 0)
                valor_total = valor_prod - valor_desc

                # =========================
                # DIFAL
                # =========================
                difal_xml = float(get_text(icms_ufdest, 'nfe:vICMSUFDest', ns) or 0)
                fcp_xml = float(get_text(icms_ufdest, 'nfe:vFCPUFDest', ns) or 0)

                difal_calc = calcular_difal(valor_total)
                difal_diff = round(difal_xml - difal_calc, 2)

                status_difal = "OK" if abs(difal_diff) <= 0.01 else "DIVERGENTE"

                # =========================
                # 🔥 VALIDAÇÃO ORIGINAL (IGUAL SEU CÓDIGO QUE FUNCIONAVA)
                # =========================
                filtro = regras[
                    (regras["ncm"]
                        .astype(str)
                        .str.replace(".0", "", regex=False)
                        .str.strip() == str(ncm_xml).replace(".0", "").strip())

                    &

                    (regras["origem"]
                        .astype(str)
                        .str.upper()
                        .str.strip() == uf_origem.upper().strip())

                    &

                    (regras["destino"]
                        .astype(str)
                        .str.upper()
                        .str.strip() == uf_destino.upper().strip())
                ]

                regra = filtro.iloc[0] if not filtro.empty else None

                # =========================
                # ST (MESMA LÓGICA ORIGINAL)
                # =========================
                filtro_st = regras_st[
                    (regras_st["ncm"]
                        .astype(str)
                        .str.replace(".0", "", regex=False)
                        .str.strip() == str(ncm_xml).replace(".0", "").strip())

                    &

                    (regras_st["origem"]
                        .astype(str)
                        .str.upper()
                        .str.strip() == uf_origem.upper().strip())

                    &

                    (regras_st["destino"]
                        .astype(str)
                        .str.upper()
                        .str.strip() == uf_destino.upper().strip())
                ]

                regra_st = filtro_st.iloc[0] if not filtro_st.empty else None

                divergencias = []

                if regra is None:
                    divergencias.append("SEM REGRA FISCAL")

                csts_st = ["10", "30", "60", "70"]
                tem_st = cst_xml in csts_st

                if regra_st is not None and not tem_st:
                    divergencias.append("DEVERIA TER ST")

                if regra_st is None and tem_st:
                    divergencias.append("ST SEM REGRA")

                validacao = "OK" if len(divergencias) == 0 else "DIVERGENTE"

                dados.append({

                    "Numero NF": get_text(ide, 'nfe:nNF', ns),
                    "Serie": get_text(ide, 'nfe:serie', ns),

                    "Chave": root.find('.//nfe:infNFe', ns).attrib.get("Id", "").replace("NFe", ""),

                    "CPF/CNPJ": documento,
                    "IE": ie_dest,

                    "UF Origem": uf_origem,
                    "UF Destino": uf_destino,

                    "Produto": produto,
                    "Codigo": codigo,
                    "Quantidade": qtd,

                    "NCM": ncm_xml,
                    "CFOP": cfop_xml,
                    "CST": cst_xml,
                    "Aliquota ICMS XML": aliquota_xml,

                    "Valor Produto": round(valor_total, 2),

                    # DIFAL
                    "DIFAL XML": difal_xml,
                    "DIFAL Calculado": difal_calc,
                    "Diferença DIFAL": difal_diff,
                    "Status DIFAL": status_difal,

                    "FCP XML": fcp_xml,

                    # REGRAS
                    "Tem Regra ST": "SIM" if regra_st is not None else "NAO",
                    "Validação Fiscal": validacao,
                    "Divergências": " | ".join(divergencias)

                })

            del tree
            del root
            gc.collect()

            barra.progress((i + 1) / len(arquivos))

        except Exception as e:
            st.error(f"Erro XML: {e}")

# =========================
# RESULTADO
# =========================
df = pd.DataFrame(dados)

if not df.empty:

    st.success(f"✅ {len(df)} registros")

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False, sep=';').encode('utf-8-sig')

    st.download_button(
        "⬇️ Baixar CSV",
        csv,
        "relatorio_fiscal.csv",
        "text/csv"
    )

else:
    st.info("Envie XML ou ZIP")