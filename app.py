import streamlit as st
import pandas as pd
from lxml import etree as ET
import zipfile
import io

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")

st.title("📄 Leitor Fiscal NF-e + Auditor Completo")

st.info("⚠️ XML + ZIP | DIFAL + Regras Fiscais + ST")

# =========================
# XML NS
# =========================
ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

# =========================
# REGRAS
# =========================
@st.cache_data
def carregar_regras():

    regras = pd.read_excel("conf_fiscais.xlsx", sheet_name="Config Fiscal")
    regras_st = pd.read_excel("conf_fiscais.xlsx", sheet_name="Config ST")

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
# XML SAFE
# =========================
def txt(el, tag):
    if el is None:
        return ""
    x = el.find(tag, ns)
    return x.text if x is not None else ""

# =========================
# DIFAL
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

    for arq in xmls:

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
                difal_calc = calcular_difal(total)

                difal_diff = round(difal_xml - difal_calc, 2)
                difal_status = "OK" if abs(difal_diff) <= 0.01 else "DIVERGENTE"

                # =========================
                # REGRAS FISCAIS
                # =========================
                chave = (ncm, uf_origem, uf_destino)

                regra = regras_dict.get(chave)
                regra_st = regras_st_dict.get(chave)

                divergencias = []

                if regra is None:
                    divergencias.append("SEM REGRA FISCAL")

                st_list = ["10", "30", "60", "70"]
                tem_st = cst in st_list

                if regra_st and not tem_st:
                    divergencias.append("DEVERIA TER ST")

                if not regra_st and tem_st:
                    divergencias.append("ST SEM REGRA")

                validacao_geral = "OK" if len(divergencias) == 0 else "DIVERGENTE"

                dados.append({

                    # NF
                    "Numero NF": txt(ide, 'nfe:nNF'),
                    "Serie": txt(ide, 'nfe:serie'),
                    "Emissao": txt(ide, 'nfe:dhEmi'),
                    "Chave": root.find('.//nfe:infNFe', ns).attrib.get("Id", "").replace("NFe", ""),

                    # CLIENTE
                    "CPF/CNPJ": documento,

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
                    "Status DIFAL": difal_status,

                    # REGRAS
                    "Tem Regra ST": "SIM" if regra_st else "NAO",
                    "Validação Fiscal": validacao_geral,
                    "Divergências": " | ".join(divergencias),

                    # VALOR
                    "Valor Produto": round(total, 2)
                })

        except Exception as e:
            st.error(f"Erro XML: {e}")

# =========================
# RESULTADO
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