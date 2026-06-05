import xml.etree.ElementTree as ET

from modules.xml_utils import get_text


def localizar_canceladas(
    arquivos,
    ns
):

    chaves_canceladas = set()

    for arq in arquivos:

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

                if chave_evento:

                    chaves_canceladas.add(
                        chave_evento
                    )

        except Exception:

            pass

    return chaves_canceladas