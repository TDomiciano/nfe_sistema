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

st.title("📄 Leitor Fiscal NF-e")
st.info("⚠️ O sistema suporta XML e ZIP contendo XMLs.")

# =========================
# NAMESPACE
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
            str(row["destino"]).upper().strip(),
            str(row["tipo_operacao"]).upper().strip()
        )

        regras_dict[chave] = row.to_dict()

    for _, row in regras_st.iterrows():

        chave = (
            str(row["ncm"]).replace(".0", "").strip(),
            str(row["origem"]).upper().strip(),
            str(row["destino"]).upper().strip(),
            str(row["tipo_operacao"]).upper().strip()
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
def buscar_regra(dicionario, ncm, origem, destino, tipo_operacao):

    chave = (
        str(ncm).replace(".0", "").strip(),
        str(origem).upper().strip(),
        str(destino).upper().strip(),
        str(tipo_operacao).upper().strip()
    )

    return dicionario.get(chave)

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

dados = []
canceladas = set()

if xmls:

    st.success(f"📦 {len(xmls)} XMLs encontrados")
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

            barra.progress((i + 1) / len(xmls))

        except:
            pass

    # =========================
    # PROCESSAMENTO
    # =========================
    for i, arq in enumerate(xmls):

        try:
            arq.seek(0)
            conteudo = arq.read()

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

            # =========================
            # TIPO OPERACAO
            # =========================
            if uf_origem == uf_destino:
                tipo_operacao = "INTERNA"
            else:
                tipo_operacao = "INTERESTADUAL"

            cnpj = txt(dest, 'nfe:CNPJ')
            cpf = txt(dest, 'nfe:CPF')

            tipo_cliente = "PJ" if cnpj else "PF"

            inf_nfe = root.find('.//nfe:infNFe', ns)
            chave = inf_nfe.attrib.get("Id", "").replace("NFe", "") if inf_nfe is not None else ""

            status = "CANCELADA" if chave in canceladas else "AUTORIZADA"

            itens = root.findall('.//nfe:det', ns)

            for item in itens:

                prod = item.find('nfe:prod', ns)
                imposto = item.find('nfe:imposto', ns)

                icms = imposto.find('.//nfe:ICMS/*', ns) if imposto is not None else None

                ncm = txt(prod, 'nfe:NCM')
                cfop = txt(prod, 'nfe:CFOP')
                produto = txt(prod, 'nfe:xProd')
                codigo = txt(prod, 'nfe:cProd')
                quantidade = txt(prod, 'nfe:qCom')

                cst = txt(icms, 'nfe:CST') or txt(icms, 'nfe:CSOSN')

                # =========================
                # BUSCA REGRA FISCAL
                # =========================
                regra = buscar_regra(
                    regras_dict,
                    ncm,
                    uf_origem,
                    uf_destino,
                    tipo_operacao
                )

                if regra:
                    aliquota = float(regra.get("aliquota", 0))
                    cfop_final = regra.get("cfop_pf") if tipo_cliente == "PF" else regra.get("cfop_pj")
                    cst_final = regra.get("cst_icms")
                else:
                    aliquota = float(txt(icms, 'nfe:pICMS') or 0)
                    cfop_final = cfop
                    cst_final = cst

                valor_icms = txt(icms, 'nfe:vICMS')

                # =========================
                # PIS / COFINS
                # =========================
                pis_tag = imposto.find('.//nfe:PIS/*', ns) if imposto is not None else None
                cofins_tag = imposto.find('.//nfe:COFINS/*', ns) if imposto is not None else None

                valor_pis = txt(pis_tag, 'nfe:vPIS')
                valor_cofins = txt(cofins_tag, 'nfe:vCOFINS')

                # =========================
                # DIFAL
                # =========================
                icmsufdest = imposto.find('.//nfe:ICMSUFDest', ns) if imposto is not None else None

                try:
                    difal_xml = float(txt(icmsufdest, 'nfe:vICMSUFDest') or 0)
                    icms_inter = float(txt(icmsufdest, 'nfe:vICMSInterestadual') or 0)
                    fcp = float(txt(icmsufdest, 'nfe:vFCPUFDest') or 0)

                    difal_calculado = round(difal_xml - icms_inter + fcp, 2)

                except:
                    difal_calculado = 0

                try:
                    valor_difal = float(difal_xml)
                except:
                    valor_difal = 0

                divergencias = []

                if difal_calculado > 0:
                    if abs(valor_difal - difal_calculado) > 1:
                        divergencias.append(
                            f"DIFAL XML ({valor_difal}) diferente do calculado ({difal_calculado})"
                        )

                valor_final = float(txt(prod, 'nfe:vProd') or 0)

                dados.append({

                    "Numero NF": txt(ide, 'nfe:nNF'),
                    "Serie": txt(ide, 'nfe:serie'),
                    "Emissao": txt(ide, 'nfe:dhEmi'),
                    "Chave": chave,
                    "Status": status,

                    "Destinatario": txt(dest, 'nfe:xNome'),
                    "CPF/CNPJ": cnpj or cpf,
                    "Tipo": tipo_cliente,

                    "UF Origem": uf_origem,
                    "UF Destino": uf_destino,
                    "Tipo Operacao": tipo_operacao,

                    "Produto": produto,
                    "Codigo": codigo,
                    "Quantidade": quantidade,
                    "NCM": ncm,
                    "CFOP": cfop_final,
                    "CST": cst_final,

                    "ICMS": valor_icms,
                    "Aliquota ICMS": aliquota,

                    "PIS": valor_pis,
                    "COFINS": valor_cofins,

                    "DIFAL XML": valor_difal,
                    "DIFAL Calculado": difal_calculado,
                    "FCP": fcp,

                    "Validacao": "OK" if not divergencias else "DIVERGENTE",
                    "Divergencias": " | ".join(divergencias),

                    "Valor Produto": round(valor_final, 2)

                })

            barra.progress((i + 1) / len(xmls))

        except Exception as e:
            st.error(f"Erro no arquivo: {e}")

# =========================
# RESULTADO
# =========================
if dados:

    df = pd.DataFrame(dados)

    st.success(f"✅ {len(df)} registros processados")

    csv = df.to_csv(index=False, sep=";").encode("utf-8-sig")

    st.download_button(
        "⬇️ Baixar CSV",
        csv,
        "relatorio_fiscal.csv",
        "text/csv"
    )

    st.dataframe(df.head(500))

else:
    st.info("Envie XMLs ou ZIPs para iniciar.")