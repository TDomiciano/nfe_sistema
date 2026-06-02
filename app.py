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
# HEADER
# =========================
col_logo, col_titulo = st.columns([0.5, 6], gap="small")

with col_logo:
    st.image("logo.png", width=90)

with col_titulo:
    st.markdown("""
    <div style="
        display:flex;
        align-items:center;
        height:90px;
        margin-left:-30px;
    ">
        <h1 style="
            margin:0;
            font-size:52px;
        ">
            Domiciano - Auditor Fiscal
        </h1>
    </div>
    """, unsafe_allow_html=True)

# =========================
# SESSION STATE
# =========================
if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0
# =========================
# BOTÃO NOVA AUDITORIA
# =========================
col1, col2 = st.columns([1, 5])

with col1:

    if st.button("🔄 Nova Auditoria"):

        st.session_state.upload_key += 1

        st.rerun()

st.divider()

# =========================
# REGRAS (PLANILHA)
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
def calcular_difal(
    valor,
    aliq_inter=0.12,
    aliq_interna=0.18
):

    icms_origem = valor * aliq_inter

    base1 = valor - icms_origem

    base2 = base1 / (1 - aliq_interna)

    icms_interno = base2 * aliq_interna

    return round(
        icms_interno - icms_origem,
        2
    )

# =========================
# UPLOAD
# =========================
uploads = st.file_uploader(
    "Envie XML ou ZIP",
    type=["xml", "zip"],
    accept_multiple_files=True,
    key=f"upload_xmls_{st.session_state.upload_key}"
)

arquivos = []

if uploads:

    for upload in uploads:

        # XML
        if upload.name.lower().endswith(".xml"):

            arquivos.append(upload)

        # ZIP
        elif upload.name.lower().endswith(".zip"):

            try:

                with zipfile.ZipFile(upload, "r") as zip_ref:

                    for nome in zip_ref.namelist():

                        if nome.lower().endswith(".xml"):

                            xml_file = io.BytesIO(
                                zip_ref.read(nome)
                            )

                            xml_file.name = nome

                            arquivos.append(xml_file)

            except Exception as e:

                st.error(
                    f"Erro ao abrir ZIP {upload.name}: {e}"
                )

dados = []

# =========================
# CHAVES CANCELADAS
# =========================
chaves_canceladas = set()

# =========================
# PROCESSAMENTO
# =========================
if arquivos:

    st.write(f"📦 Total XMLs: {len(arquivos)}")

    barra = st.progress(0)

    ns = {
        "nfe": "http://www.portalfiscal.inf.br/nfe"
    }

    # =========================
    # BUSCA CANCELADAS
    # =========================
    for i, arq in enumerate(arquivos):

        try:

            arq.seek(0)

            tree = ET.parse(arq)

            root = tree.getroot()

            xml_str = ET.tostring(
                root,
                encoding="unicode"
            ).upper()

            if (
                "CANCELAMENTO" in xml_str
                and
                "110111" in xml_str
            ):

                chave_evento = ""

                ret_evento = root.find(
                    ".//nfe:retEvento/nfe:infEvento",
                    ns
                )

                if ret_evento is not None:

                    chave_evento = get_text(
                        ret_evento,
                        "nfe:chNFe",
                        ns
                    )

                if chave_evento == "":

                    inf_evento = root.find(
                        ".//nfe:infEvento",
                        ns
                    )

                    chave_evento = get_text(
                        inf_evento,
                        "nfe:chNFe",
                        ns
                    )

                if chave_evento != "":

                    chaves_canceladas.add(
                        chave_evento
                    )

        except:
            pass

    # =========================
    # LOOP XMLS
    # =========================
    for i, arq in enumerate(arquivos):

        try:

            arq.seek(0)

            tree = ET.parse(arq)

            root = tree.getroot()

            # IGNORA EVENTOS
            if root.find(
                ".//nfe:infEvento",
                ns
            ) is not None:

                continue

            ide = root.find(".//nfe:ide", ns)

            emit = root.find(".//nfe:emit", ns)

            dest = root.find(".//nfe:dest", ns)

            ender_emit = (
                emit.find("nfe:enderEmit", ns)
                if emit is not None
                else None
            )

            ender_dest = (
                dest.find("nfe:enderDest", ns)
                if dest is not None
                else None
            )

            uf_origem = get_text(
                ender_emit,
                "nfe:UF",
                ns
            )

            uf_destino = get_text(
                ender_dest,
                "nfe:UF",
                ns
            )

            cnpj = get_text(
                dest,
                "nfe:CNPJ",
                ns
            )

            cpf = get_text(
                dest,
                "nfe:CPF",
                ns
            )

            documento = cnpj if cnpj else cpf

            tipo_cliente = (
                "PJ"
                if cnpj
                else "PF"
            )

            ie_dest = ""

            if dest is not None:

                ie_tag = dest.find(
                    ".//nfe:IE",
                    ns
                )

                ie_dest = (
                    ie_tag.text
                    if ie_tag is not None
                    else ""
                )

            # =========================
            # CHAVE
            # =========================
            chave = ""

            inf_nfe = root.find(
                ".//nfe:infNFe",
                ns
            )

            if inf_nfe is not None:

                chave = (
                    inf_nfe.attrib
                    .get("Id", "")
                    .replace("NFe", "")
                )

            # =========================
            # STATUS
            # =========================
            status = "AUTORIZADA"

            if chave in chaves_canceladas:

                status = "CANCELADA"

            xml_str = ET.tostring(
                root,
                encoding="unicode"
            ).upper()

            if "DENEGADO" in xml_str:

                status = "DENEGADA"

            elif "REJEICAO" in xml_str:

                status = "REJEITADA"

            itens = root.findall(
                ".//nfe:det",
                ns
            )

            for item in itens:

                prod = item.find(
                    "nfe:prod",
                    ns
                )

                imposto = item.find(
                    "nfe:imposto",
                    ns
                )

                icms = (
                    imposto.find(
                        ".//nfe:ICMS/*",
                        ns
                    )
                    if imposto is not None
                    else None
                )

                icms_ufdest = (
                    imposto.find(
                        ".//nfe:ICMSUFDest",
                        ns
                    )
                    if imposto is not None
                    else None
                )

                ncm = get_text(
                    prod,
                    "nfe:NCM",
                    ns
                )

                cfop_xml = get_text(
                    prod,
                    "nfe:CFOP",
                    ns
                )

                produto = get_text(
                    prod,
                    "nfe:xProd",
                    ns
                )

                codigo = get_text(
                    prod,
                    "nfe:cProd",
                    ns
                )

                qtd = get_text(
                    prod,
                    "nfe:qCom",
                    ns
                )

                cst_xml = ""

                if icms is not None:

                    cst_xml = (
                        get_text(
                            icms,
                            "nfe:CST",
                            ns
                        )
                        or
                        get_text(
                            icms,
                            "nfe:CSOSN",
                            ns
                        )
                    )

                aliquota_xml = get_text(
                    icms,
                    "nfe:pICMS",
                    ns
                )

                valor_prod = float(
                    get_text(
                        prod,
                        "nfe:vProd",
                        ns
                    ) or 0
                )

                valor_desc = float(
                    get_text(
                        prod,
                        "nfe:vDesc",
                        ns
                    ) or 0
                )

                valor_total = (
                    valor_prod - valor_desc
                )

                # =========================
                # DIFAL
                # =========================
                difal_xml = float(
                    get_text(
                        icms_ufdest,
                        "nfe:vICMSUFDest",
                        ns
                    ) or 0
                )

                fcp_xml = float(
                    get_text(
                        icms_ufdest,
                        "nfe:vFCPUFDest",
                        ns
                    ) or 0
                )

                difal_calc = calcular_difal(
                    valor_total
                )

                difal_diff = round(
                    difal_xml - difal_calc,
                    2
                )

                status_difal = (
                    "OK"
                    if abs(difal_diff) <= 0.01
                    else "DIVERGENTE"
                )

                # =========================
                # REGRA FISCAL
                # =========================
                filtro = regras[

                    (
                        regras["ncm"]
                        .astype(str)
                        .str.replace(".0", "", regex=False)
                        .str.strip()
                        ==
                        str(ncm)
                        .replace(".0", "")
                        .strip()
                    )

                    &

                    (
                        regras["origem"]
                        .astype(str)
                        .str.upper()
                        .str.strip()
                        ==
                        uf_origem.upper().strip()
                    )

                    &

                    (
                        regras["destino"]
                        .astype(str)
                        .str.upper()
                        .str.strip()
                        ==
                        uf_destino.upper().strip()
                    )
                ]

                regra = (
                    filtro.iloc[0]
                    if not filtro.empty
                    else None
                )

                # =========================
                # REGRA ST
                # =========================
                filtro_st = regras_st[

                    (
                        regras_st["ncm"]
                        .astype(str)
                        .str.replace(".0", "", regex=False)
                        .str.strip()
                        ==
                        str(ncm)
                        .replace(".0", "")
                        .strip()
                    )

                    &

                    (
                        regras_st["origem"]
                        .astype(str)
                        .str.upper()
                        .str.strip()
                        ==
                        uf_origem.upper().strip()
                    )

                    &

                    (
                        regras_st["destino"]
                        .astype(str)
                        .str.upper()
                        .str.strip()
                        ==
                        uf_destino.upper().strip()
                    )
                ]

                regra_st = (
                    filtro_st.iloc[0]
                    if not filtro_st.empty
                    else None
                )

                divergencias = []

                # =========================
                # CFOP + ICMS
                # =========================
                if regra is not None:

                    cfop_regra = (

                        str(regra["cfop_pj"])

                        if tipo_cliente == "PJ"

                        else

                        str(regra["cfop_pf"])

                    ).replace(".0", "").strip()

                    aliquota_regra = str(
                        regra["aliquota_icms"]
                    ).replace(".0", "").strip()

                    if cfop_xml != cfop_regra:

                        divergencias.append(
                            f"CFOP XML ({cfop_xml}) diferente da regra ({cfop_regra})"
                        )

                    try:

                        if (
                            aliquota_xml != ""
                            and
                            float(aliquota_xml) != float(aliquota_regra)
                        ):

                            divergencias.append(
                                f"ICMS XML ({aliquota_xml}) diferente da regra ({aliquota_regra})"
                            )

                    except:
                        pass

                else:

                    divergencias.append(
                        "SEM REGRA FISCAL"
                    )

                # =========================
                # ST
                # =========================
                csts_st = [
                    "10",
                    "30",
                    "60",
                    "70"
                ]

                tem_st = (
                    cst_xml in csts_st
                )

                if (
                    regra_st is None
                    and
                    tem_st
                ):

                    divergencias.append(
                        "ST SEM REGRA"
                    )

                if (
                    regra_st is not None
                    and
                    not tem_st
                ):

                    divergencias.append(
                        "DEVERIA TER ST"
                    )

# =========================
# DIFAL
# =========================

pj_com_ie = (
    tipo_cliente == "PJ"
    and ie_dest.strip() != ""
)

if (
    uf_origem != uf_destino
    and not pj_com_ie
):

    aliq_interna = 0.18

    if uf_destino == "RJ":
        aliq_interna = 0.20

    bc_difal_xml = float(
        get_text(
            icms_ufdest,
            "nfe:vBCUFDest",
            ns
        ) or 0
    )

    if bc_difal_xml > 0:

        icms_destino = bc_difal_xml * aliq_interna

        icms_origem = valor_total * 0.12

        difal_calc = round(
            icms_destino - icms_origem,
            2
        )

    else:

        difal_calc = calcular_difal(
            valor_total,
            aliq_inter=0.12,
            aliq_interna=aliq_interna
        )

    difal_diff = round(
        difal_xml - difal_calc,
        2
    )

    status_difal = (
        "OK"
        if abs(difal_diff) <= 0.01
        else "DIVERGENTE"
    )

    if abs(difal_diff) > 0.01:

        divergencias.append(
            f"DIFAL divergente (XML {difal_xml} x Calc {difal_calc})"
        )

else:

    difal_calc = 0
    difal_diff = 0
    status_difal = "NÃO APLICÁVEL"

validacao = (
    "OK"
    if len(divergencias) == 0
    else "DIVERGENTE"
)
                # =========================
                # DADOS
                # =========================
                dados.append({

                    "NF": get_text(
                        ide,
                        "nfe:nNF",
                        ns
                    ),

                    "Serie": get_text(
                        ide,
                        "nfe:serie",
                        ns
                    ),

                    "Status": status,

                    "Chave": chave,

                    "CPF/CNPJ": documento,

                    "IE": ie_dest,

                    "Destinatario": get_text(
                        dest,
                        "nfe:xNome",
                        ns
                    ),

                    "UF Origem": uf_origem,

                    "UF Destino": uf_destino,

                    "Produto": produto,

                    "Codigo": codigo,

                    "Qtd": qtd,

                    "NCM": ncm,

                    "CFOP": cfop_xml,

                    "CST": cst_xml,

                    "Aliquota ICMS": aliquota_xml,

                    "Valor Produto Total": round(
                        valor_total,
                        2
                    ),

                    "DIFAL XML": difal_xml,

                    "DIFAL Calculado": difal_calc,

                    "Diferença DIFAL": difal_diff,

                    "Status DIFAL": status_difal,

                    "FCP XML": fcp_xml,

                    "Tem Regra ST": (
                        "SIM"
                        if regra_st is not None
                        else "NAO"
                    ),

                    "Validação Fiscal": validacao,

                    "Divergências": (
                        " | ".join(divergencias)
                    )

                })

            
            barra.progress(
                (i + 1) / len(arquivos)
            )

        except Exception as e:

            st.error(
                f"Erro XML {arq.name}: {e}"
            )

# =========================
# OUTPUT
# =========================
df = pd.DataFrame(dados)

if not df.empty:

    st.success(
        f"✅ {len(df)} registros"
    )

    # =========================
    # AUDITORIA SEQUÊNCIA
    # =========================
    st.subheader(
        "🔎 Auditoria Sequência NF"
    )

    df_seq = df[
        df["Status"].isin(
            ["AUTORIZADA", "CANCELADA", "DENEGADA"]
        )
    ].copy()

    df_seq["NF"] = pd.to_numeric(
        df_seq["NF"],
        errors="coerce"
    )

    quebras = []

    for serie in df_seq["Serie"].dropna().unique():

        notas = sorted(

            df_seq[
                df_seq["Serie"] == serie
            ]["NF"]

            .dropna()
            .astype(int)
            .unique()
        )

        if len(notas) > 1:

            menor = min(notas)
            maior = max(notas)

            todas = set(
                range(menor, maior + 1)
            )

            existentes = set(notas)

            faltantes = sorted(
                list(todas - existentes)
            )

            if len(faltantes) > 0:

                quebras.append({

                    "Serie": serie,
                    "Menor NF": menor,
                    "Maior NF": maior,
                    "Qtd Quebras": len(faltantes),

                    "Notas Faltantes":
                        ", ".join(
                            map(
                                str,
                                faltantes[:100]
                            )
                        )
                })

    if len(quebras) > 0:

        df_quebras = pd.DataFrame(quebras)

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Séries com Quebra",
            len(df_quebras)
        )

        col2.metric(
            "Total Quebras",
            sum(df_quebras["Qtd Quebras"])
        )

        col3.metric(
            "Status",
            "ALERTA"
        )

        st.warning(
            "⚠️ Quebras de sequência encontradas"
        )

        st.dataframe(
            df_quebras,
            use_container_width=True
        )

    else:

        df_quebras = pd.DataFrame()

        st.success(
            "✅ Nenhuma quebra encontrada"
        )

    # =========================
    # CANCELADAS
    # =========================
    st.subheader(
        "🚫 NF-e Canceladas"
    )

    df_canceladas = df[
        df["Status"] == "CANCELADA"
    ].copy()

    if not df_canceladas.empty:

        st.warning(
            f"⚠️ {len(df_canceladas)} NF canceladas"
        )

        st.dataframe(
            df_canceladas[
                [
                    "NF",
                    "Serie",
                    "CPF/CNPJ",
                    "Destinatario",
                    "Valor Produto Total",
                    "Chave"
                ]
            ],
            use_container_width=True
        )

    else:

        st.success(
            "✅ Nenhuma NF cancelada"
        )

    # =========================
    # HEADER + DOWNLOAD
    # =========================
    col1, col2 = st.columns([4, 1])

    with col1:

        st.subheader(
            "📊 Auditoria Fiscal"
        )

    # =========================
    # EXPORTAÇÃO
    # =========================
    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Auditoria Fiscal"
        )

        if not df_quebras.empty:

            df_quebras.to_excel(
                writer,
                index=False,
                sheet_name="Quebra Sequencia"
            )

        if not df_canceladas.empty:

            df_canceladas.to_excel(
                writer,
                index=False,
                sheet_name="NF Canceladas"
            )

    output.seek(0)

    with col2:

        st.download_button(
            "⬇️ Baixar Excel",
            output,
            file_name="auditoria_fiscal.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # =========================
    # TABELA PRINCIPAL
    # =========================
    st.dataframe(
        df,
        use_container_width=True
    )

else:

    st.info(
        "Envie XML ou ZIP"
    )