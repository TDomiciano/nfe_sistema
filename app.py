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
st.title("📄 Leitor Fiscal NF-e")

st.info("⚠️ O sistema suporta XML e ZIP contendo XMLs.")

# =========================
# NAMESPACE XML
# =========================
ns = {
    "nfe": "http://www.portalfiscal.inf.br/nfe"
}

# =========================
# CARREGA REGRAS
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

    regras_dict = {}
    regras_st_dict = {}

    for _, row in regras.iterrows():
        chave = (
            str(row["ncm"]).replace(".0", "").strip(),
            str(row["origem"]).upper().strip(),
            str(row["destino"]).upper().strip()
        )
        regras_dict[chave] = row.to_dict()

    for _, row in regras_st.iterrows():
        chave = (
            str(row["ncm"]).replace(".0", "").strip(),
            str(row["origem"]).upper().strip(),
            str(row["destino"]).upper().strip()
        )
        regras_st_dict[chave] = row.to_dict()

    return regras_dict, regras_st_dict


regras_dict, regras_st_dict = carregar_regras()

# =========================
# FUNÇÃO SEGURA XML
# =========================
def txt(elemento, tag):
    if elemento is None:
        return ""
    achou = elemento.find(tag, ns)
    return achou.text if achou is not None else ""

# =========================
# BUSCA REGRA
# =========================
def buscar_regra(dicionario, ncm, origem, destino):
    chave = (
        str(ncm).replace(".0", "").strip(),
        str(origem).upper().strip(),
        str(destino).upper().strip()
    )
    return dicionario.get(chave)

# =========================
# DIFAL BASE DUPLA (CALCULADO)
# =========================
def calcular_difal(valor, aliq_interestadual=0.12, aliq_interna=0.18):
    icms_origem = valor * aliq_interestadual
    base1 = valor - icms_origem
    base2 = base1 / (1 - aliq_interna)
    icms_interno = base2 * aliq_interna
    return round(icms_interno - icms_origem, 2)

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

            try:
                zip_file = zipfile.ZipFile(arq)

                for nome in zip_file.namelist():
                    if nome.lower().endswith(".xml"):
                        xml_bytes = zip_file.read(nome)
                        xmls.append(io.BytesIO(xml_bytes))

            except Exception as e:
                st.error(f"Erro ao abrir ZIP {arq.name}: {e}")

# =========================
# PROCESSAMENTO
# =========================
dados = []
canceladas = set()

if xmls:

    total = len(xmls)
    st.success(f"📦 {total} XMLs encontrados")
    barra = st.progress(0)

    # =========================
    # CANCELADAS
    # =========================
    for i, arq in enumerate(xmls):

        try:
            arq.seek(0)
            conteudo = arq.read()

            texto = conteudo.decode("utf-8", errors="ignore").upper()

            if "CANCELAMENTO" in texto and "110111" in texto:

                root = ET.fromstring(conteudo)

                inf_evento = root.find(".//nfe:infEvento", ns)

                chave = txt(inf_evento, "nfe:chNFe")

                if chave:
                    canceladas.add(chave)

            barra.progress((i + 1) / total)

        except:
            pass

    # =========================
    # PROCESSA XML
    # =========================
    for i, arq in enumerate(xmls):

        try:
            arq.seek(0)
            conteudo = arq.read()

            texto = conteudo.decode("utf-8", errors="ignore").upper()

            root = ET.fromstring(conteudo)

            if root.find('.//nfe:infEvento', ns) is not None:
                continue

            ide = root.find('.//nfe:ide', ns)
            emit = root.find('.//nfe:emit', ns)
            dest = root.find('.//nfe:dest', ns)

            emit_end = emit.find('nfe:enderEmit', ns) if emit is not None else None
            dest_end = dest.find('nfe:enderDest', ns) if dest is not None else None

            uf_origem = txt(emit_end, 'nfe:UF')
            uf_destino = txt(dest_end, 'nfe:UF')

            inf_nfe = root.find('.//nfe:infNFe', ns)

            chave = ""
            if inf_nfe is not None:
                chave = inf_nfe.attrib.get("Id", "").replace("NFe", "")

            status = "AUTORIZADA"

            if chave in canceladas:
                status = "CANCELADA"
            elif "DENEGADO" in texto:
                status = "DENEGADA"
            elif "REJEICAO" in texto:
                status = "REJEITADA"

            cnpj = txt(dest, 'nfe:CNPJ')
            cpf = txt(dest, 'nfe:CPF')

            documento = cnpj if cnpj else cpf

            itens = root.findall('.//nfe:det', ns)

            for item in itens:

                prod = item.find('nfe:prod', ns)
                imposto = item.find('nfe:imposto', ns)

                icms = (
                    imposto.find('.//nfe:ICMS/*', ns)
                    if imposto is not None else None
                )

                icms_ufdest = imposto.find('.//nfe:ICMSUFDest', ns) if imposto is not None else None

                ncm = txt(prod, 'nfe:NCM')
                cfop = txt(prod, 'nfe:CFOP')
                produto = txt(prod, 'nfe:xProd')
                codigo = txt(prod, 'nfe:cProd')
                quantidade = txt(prod, 'nfe:qCom')

                cst = txt(icms, 'nfe:CST') or txt(icms, 'nfe:CSOSN')

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
                difal_calc = calcular_difal(valor_final)

                # =========================
                # COMPARAÇÃO
                # =========================
                diferenca_difal = round(difal_xml - difal_calc, 2)

                status_difal = "OK" if abs(diferenca_difal) <= 0.01 else "DIVERGENTE"

                dados.append({

                    "Numero NF": txt(ide, 'nfe:nNF'),
                    "Serie": txt(ide, 'nfe:serie'),
                    "Emissao": txt(ide, 'nfe:dhEmi'),
                    "Chave Acesso": f"'{chave}",

                    "CPF/CNPJ": documento,

                    "UF Origem": uf_origem,
                    "UF Destino": uf_destino,

                    "Produto": produto,
                    "Codigo": codigo,
                    "Quantidade": quantidade,

                    "NCM": ncm,
                    "CFOP XML": cfop,
                    "CST XML": cst,

                    "Valor Produto": round(valor_final, 2),

                    # =========================
                    # DIFAL
                    # =========================
                    "DIFAL XML": difal_xml,
                    "DIFAL Calculado": difal_calc,
                    "Diferença DIFAL": diferenca_difal,
                    "Status DIFAL": status_difal,

                    "Status NF": status
                })

            barra.progress((i + 1) / total)

        except Exception as e:
            st.error(f"Erro no arquivo: {e}")

# =========================
# RESULTADO
# =========================
if dados:

    df = pd.DataFrame(dados)
    df = df.fillna("")

    st.success(f"✅ {len(df)} itens processados")

    st.dataframe(df, use_container_width=True)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    output.seek(0)

    st.download_button(
        "⬇️ Baixar Excel",
        output,
        file_name="relatorio_fiscal.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Envie XMLs ou ZIPs para iniciar.")