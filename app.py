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
# DIFAL BASE DUPLA
# =========================
def calcular_difal_base_dupla(valor, aliq_interestadual=0.12, aliq_interna=0.18):
    icms_origem = valor * aliq_interestadual
    base1 = valor - icms_origem
    base2 = base1 / (1 - aliq_interna)
    icms_interno = base2 * aliq_interna
    difal = icms_interno - icms_origem

    return icms_origem, base2, icms_interno, difal

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

            ie_dest = ""
            if dest is not None:
                ie_tag = dest.find('.//nfe:IE', ns)
                ie_dest = ie_tag.text if ie_tag is not None else ""

            documento = cnpj if cnpj else cpf
            tipo_cliente = "PJ" if cnpj else "PF"

            itens = root.findall('.//nfe:det', ns)

            for item in itens:

                prod = item.find('nfe:prod', ns)
                imposto = item.find('nfe:imposto', ns)

                icms = (
                    imposto.find('.//nfe:ICMS/*', ns)
                    if imposto is not None else None
                )

                ncm = txt(prod, 'nfe:NCM')
                cfop = txt(prod, 'nfe:CFOP')
                produto = txt(prod, 'nfe:xProd')
                codigo = txt(prod, 'nfe:cProd')
                quantidade = txt(prod, 'nfe:qCom')

                cst = txt(icms, 'nfe:CST') or txt(icms, 'nfe:CSOSN')
                aliquota = float(txt(icms, 'nfe:pICMS') or 0)
                valor_icms_xml = float(txt(icms, 'nfe:vICMS') or 0)

                valor_bruto = float(txt(prod, 'nfe:vProd') or 0)
                valor_desc = float(txt(prod, 'nfe:vDesc') or 0)
                valor_final = valor_bruto - valor_desc

                regra = buscar_regra(regras_dict, ncm, uf_origem, uf_destino)
                regra_st = buscar_regra(regras_st_dict, ncm, uf_origem, uf_destino)

                divergencias = []

                if regra is None:
                    divergencias.append("SEM REGRA FISCAL")

                csts_st = ["10", "30", "60", "70"]
                tem_st = cst in csts_st

                if regra_st is not None and not tem_st:
                    divergencias.append("Produto deveria ter ST")

                if regra_st is None and tem_st:
                    divergencias.append("Produto possui ST sem regra")

                # =========================
                # DIFAL AUDITOR
                # =========================
                icms_origem, base2, icms_interno, difal = calcular_difal_base_dupla(valor_final)

                diferenca_difal = valor_icms_xml - icms_interno

                dados.append({

                    "Numero NF": txt(ide, 'nfe:nNF'),
                    "Serie": txt(ide, 'nfe:serie'),
                    "Emissao": txt(ide, 'nfe:dhEmi'),
                    "Chave Acesso": f"'{chave}",

                    "CPF/CNPJ": documento,
                    "IE": str(ie_dest or ""),

                    "Status": status,
                    "Destinatario": txt(dest, 'nfe:xNome'),

                    "UF Origem": uf_origem,
                    "UF Destino": uf_destino,

                    "Produto": produto,
                    "Codigo": codigo,
                    "Quantidade": quantidade,

                    "NCM": ncm,
                    "CFOP XML": cfop,
                    "CST XML": cst,
                    "Aliquota ICMS XML": aliquota,
                    "Valor ICMS XML": valor_icms_xml,

                    "ICMS Origem Calc": round(icms_origem, 2),
                    "ICMS Interno Calc": round(icms_interno, 2),
                    "DIFAL Calc": round(difal, 2),
                    "Diferença ICMS vs Calc": round(diferenca_difal, 2),

                    "Valor DIFAL XML": txt(imposto.find('.//nfe:ICMSUFDest', ns) if imposto is not None else None, 'nfe:vICMSUFDest'),
                    "Valor FCP": txt(imposto.find('.//nfe:ICMSUFDest', ns) if imposto is not None else None, 'nfe:vFCPUFDest'),

                    "Tem Regra ST": "SIM" if regra_st else "NAO",
                    "Validacao": "OK" if len(divergencias) == 0 else "DIVERGENTE",
                    "Divergencias": " | ".join(divergencias),

                    "Valor Produto Total": round(valor_final, 2)

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

    st.success(f"✅ {len(df)} registros processados")

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

    st.dataframe(df.head(500))

else:
    st.info("Envie XMLs ou ZIPs para iniciar.")