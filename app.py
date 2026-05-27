import streamlit as st
import pandas as pd
from lxml import etree as ET
import zipfile
import io

# =========================
# CONFIG PAGINA
# =========================
st.set_page_config(layout="wide")

# =========================
# CSS
# =========================
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
# TITULO
# =========================
st.title("📄 Leitor Fiscal NF-e + Auditor DIFAL")

st.info("⚠️ Sistema suporta XML e ZIP contendo XMLs")

# =========================
# NAMESPACE
# =========================
ns = {
    "nfe": "http://www.portalfiscal.inf.br/nfe"
}

# =========================
# FUNÇÕES AUXILIARES
# =========================
def txt(elemento, tag):
    if elemento is None:
        return ""
    achou = elemento.find(tag, ns)
    return achou.text if achou is not None else ""

# =========================
# DIFAL BASE DUPLA
# =========================
def calcular_difal_base_dupla(valor, aliq_interestadual=0.12, aliq_interna=0.18):
    icms_origem = valor * aliq_interestadual
    base1 = valor - icms_origem
    base2 = base1 / (1 - aliq_interna)
    icms_interno = base2 * aliq_interna
    difal = icms_interno - icms_origem

    return round(difal, 2)

# =========================
# UPLOAD
# =========================
arquivos = st.file_uploader(
    "Envie XML ou ZIP",
    type=["xml", "zip"],
    accept_multiple_files=True
)

xmls = []

if arquivos:
    for arq in arquivos:

        if arq.name.lower().endswith(".xml"):
            xmls.append(arq)

        elif arq.name.lower().endswith(".zip"):
            zip_file = zipfile.ZipFile(arq)

            for nome in zip_file.namelist():
                if nome.lower().endswith(".xml"):
                    xml_bytes = zip_file.read(nome)
                    xmls.append(io.BytesIO(xml_bytes))

# =========================
# PROCESSAMENTO
# =========================
dados = []

if xmls:

    st.success(f"📦 {len(xmls)} XMLs carregados")

    for arq in xmls:

        try:
            arq.seek(0)
            conteudo = arq.read()

            root = ET.fromstring(conteudo)

            ide = root.find('.//nfe:ide', ns)
            emit = root.find('.//nfe:emit', ns)
            dest = root.find('.//nfe:dest', ns)

            uf_origem = txt(emit.find('nfe:enderEmit', ns) if emit is not None else None, 'nfe:UF')
            uf_destino = txt(dest.find('nfe:enderDest', ns) if dest is not None else None, 'nfe:UF')

            itens = root.findall('.//nfe:det', ns)

            for item in itens:

                prod = item.find('nfe:prod', ns)
                imposto = item.find('nfe:imposto', ns)

                icms = imposto.find('.//nfe:ICMS/*', ns) if imposto is not None else None
                icms_ufdest = imposto.find('.//nfe:ICMSUFDest', ns) if imposto is not None else None

                ncm = txt(prod, 'nfe:NCM')
                cfop = txt(prod, 'nfe:CFOP')
                produto = txt(prod, 'nfe:xProd')

                valor_bruto = float(txt(prod, 'nfe:vProd') or 0)
                valor_desc = float(txt(prod, 'nfe:vDesc') or 0)
                valor_final = valor_bruto - valor_desc

                # =========================
                # DIFAL XML
                # =========================
                difal_xml = float(txt(icms_ufdest, 'nfe:vICMSUFDest') or 0)

                # =========================
                # DIFAL CALCULADO
                # =========================
                difal_calc = calcular_difal_base_dupla(valor_final)

                # =========================
                # COMPARAÇÃO
                # =========================
                diferenca = round(difal_xml - difal_calc, 2)

                status = "OK" if abs(diferenca) <= 0.01 else "DIVERGENTE"

                dados.append({

                    "Produto": produto,
                    "NCM": ncm,
                    "CFOP": cfop,
                    "Valor Produto": round(valor_final, 2),

                    # DIFAL XML (SEFAZ)
                    "DIFAL XML": difal_xml,

                    # DIFAL calculado (nosso sistema)
                    "DIFAL Calculado": difal_calc,

                    # diferença
                    "Diferença DIFAL": diferenca,

                    # status auditoria
                    "Status DIFAL": status
                })

        except Exception as e:
            st.error(f"Erro no XML: {e}")

# =========================
# RESULTADO
# =========================
if dados:

    df = pd.DataFrame(dados)

    st.success(f"✅ {len(df)} itens processados")

    # destaque divergências
    def cor_status(val):
        return "background-color: #ffcccc" if val == "DIVERGENTE" else ""

    st.dataframe(
        df.style.applymap(cor_status, subset=["Status DIFAL"]),
        use_container_width=True
    )

    st.download_button(
        "⬇️ Baixar Excel",
        df.to_csv(index=False).encode("utf-8"),
        file_name="auditoria_difal.csv",
        mime="text/csv"
    )

else:
    st.info("Envie XML ou ZIP para iniciar.")