NS = {
    "nfe": "http://www.portalfiscal.inf.br/nfe"
}

def get_text(element, tag, ns=NS):

    if element is None:
        return ""

        found = element.find(tag, ns)

        return found.text if found is not None else ""