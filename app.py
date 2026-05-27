import streamlit as st
import pandas as pd
from lxml import etree as ET
import zipfile
import io

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")

st.title("📄 Leitor Fiscal NF-e + Auditor DIFAL")

st.info("XML + ZIP | Regras fiscais + ST + DIFAL")

# =========================
# XML NS
# =========================
ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

# =========================
# LEITURA DAS REGRAS
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
# BUSCA REGRA FISCAL (SEU MODELO)
# =========================
def buscar_regra(ncm, origem, destino):

    ncm = str(ncm).replace(".0", "").strip()

    filtro = regras[
        (regras["ncm"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip() == ncm)

        &

        (regras["origem"]
            .astype(str)
            .str.upper()
            .str.strip() == str(origem).upper().strip())

        &

        (regras["destino"]
            .astype(str)
            .str.upper()
            .str.strip() == str(destino).upper().strip())
    ]

    if not filtro.empty:
        return filtro.iloc[0]

    return None


# =========================
# BUSCA REGRA ST (SEU MODELO)
# =========================
def buscar_regra_st(ncm, origem, destino):

    ncm = str(ncm).replace(".0", "").strip()

    filtro = regras_st[
        (regras_st["ncm"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip() == ncm)

        &

        (regras_st["origem"]
            .astype(str)
            .str.upper()
            .str.strip() == str(origem).upper().strip())

        &

        (regras_st["destino"]
            .astype(str)
            .str.upper()
            .str.strip() == str(destino).upper().strip())
    ]

    if not filtro.empty:
        return filtro.iloc[0]

    return None


# =========================
# XML SAFE
# =========================
def txt(el, tag):
    if el is None:
        return ""
    x = el.find(tag, ns)
    return x.text if x is not None else ""

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

        if arq.name.endswith(".xml"):
            xmls.append(arq)

        elif arq.name.endswith(".zip"):
            z = zipfile.ZipFile(arq)

            for n in z.namelist():
                if n.endswith(".xml"):
                    xmls.append(io.BytesIO(z.read(n)))


# =========================
# PROCESSAMENTO
# =========================
dados = []

if xmls:

    st.success(f"📦 {len(xmls)} XMLs carregados")

    barra = st.progress(0)

    for i, arq in enumerate(xmls):

        try:
            arq.seek(0)
            root = ET.fromstring(arq.read())

            ide = root.find('.//nfe:ide', ns)
            emit = root.find('.//nfe:emit', ns)
            dest = root.find('.//nfe:dest', ns)

            emit_end = emit.find('nfe:enderEmit', ns) if emit is not None else None
            dest_end = dest.find('nfe:enderDest', ns) if dest is not None else None

            uf_origem = txt(emit_end, 'nfe:UF')
            uf_destino = txt(dest_end, 'nfe:UF')

            cnpj = txt(dest, 'nfe:CNPJ')
            cpf = txt(dest, 'nfe:CPF')
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

                ncm = txt(prod, 'nfe:NCM')
                cfop = txt(prod, 'nfe:CFOP')
                produto = txt(prod, 'nfe:xProd')
                codigo = txt(prod, 'nfe:cProd')
                qtd = txt(prod, 'nfe:qCom')

                cst = txt(icms, 'nfe:CST') or txt(icms, 'nfe:CSOSN')

                valor = float(txt(prod, 'nfe:vProd') or 0)
                desc = float(txt(prod, 'nfe:vDesc') or 0)
                total = valor - desc

                # =========================
                # DIFAL
                # =========================
                difal_xml = float(txt(icms_ufdest, 'nfe:vICMSUFDest') or 0)
                fcp_xml = float(txt(icms_ufdest, 'nfe:vFCPUFDest') or 0)

                difal_calc = calcular_difal(total)
                difal_diff = round(difal_xml - difal_calc, 2)

                status_difal = "OK" if abs(difal_diff) <= 0.01 else "DIVERGENTE"

                # =========================
                # REGRAS FISCAIS
                # =========================
                regra = buscar_regra(ncm, uf_origem, uf_destino)
                regra_st = buscar_regra_st(ncm, uf_origem, uf_destino)

                divergencias = []

                if regra is None:
                    divergencias.append("SEM REGRA FISCAL")

                st_list = ["10", "30", "60", "70"]
                tem_st = cst in st_list

                if regra_st is not None and not tem_st:
                    divergencias.append("DEVERIA TER ST")

                if regra_st is None and tem_st:
                    divergencias.append("ST SEM REGRA")

                validacao = "OK" if len(divergencias) == 0 else "DIVERGENTE"

                dados.append({

                    # NF
                    "Numero NF": txt(ide, 'nfe:nNF'),
                    "Serie": txt(ide, 'nfe:serie'),
                    "Emissao": txt(ide, 'nfe:dhEmi'),
                    "Chave": root.find('.//nfe:infNFe', ns).attrib.get("Id", "").replace("NFe", ""),

                    # CLIENTE
                    "CPF/CNPJ": documento,
                    "IE": ie_dest,

                    # LOCAL
                    "UF Origem": uf_origem,
                    "UF Destino": uf_destino,

                    # PRODUTO
                    "Produto": produto,
                    "Codigo": codigo,
                    "Quantidade": qtd,

                    # TRIBUTOS
                    "NCM": ncm,
                    "CFOP": cfop,
                    "CST": cst,

                    # DIFAL
                    "DIFAL XML": difal_xml,
                    "DIFAL Calculado": difal_calc,
                    "Diferença DIFAL": difal_diff,
                    "Status DIFAL": status_difal,

                    # FCP
                    "FCP XML": fcp_xml,

                    # REGRAS
                    "Tem Regra ST": "SIM" if regra_st is not None else "NAO",
                    "Validação Fiscal": validacao,
                    "Divergências": " | ".join(divergencias),

                    # VALOR
                    "Valor Produto": round(total, 2)
                })

            barra.progress((i + 1) / len(xmls))

        except Exception as e:
            st.error(f"Erro XML: {e}")


# =========================
# RESULTADO FINAL
# =========================
if dados:

    df = pd.DataFrame(dados).fillna("")

    st.success(f"✅ {len(df)} itens processados")

    st.dataframe(df, use_container_width=True)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    output.seek(0)

    st.download_button(
        "⬇️ Baixar Excel Fiscal Completo",
        output,
        file_name="auditoria_fiscal.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Envie XML ou ZIP para iniciar.")