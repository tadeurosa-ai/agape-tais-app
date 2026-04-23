import streamlit as st
import requests
from datetime import date
from fpdf import FPDF

st.set_page_config(
    page_title="Ferragem Agápè — Consignação",
    page_icon="💰",
    layout="centered",
)

BASE_ID = "applwqIv7LwaRxL5g"
TABLE_ESTOQUE = "tblfC2RBL11zdy4rW"
TABLE_BAIXAS = "tblslIocty9hf5j3k"

F_DESC        = "fldPkkISGo4U3iom6"
F_UNID        = "fld1KRLnffGU4xwYm"
F_QTD_SALDO   = "fldHAS3B7uhLyG5uh"
F_QTD_ENVIADA = "fld8MOkhlQwM1QQdt"
F_QTD_VENDIDA = "fldX3NyGIIIHQ81ZA"
F_PRECO       = "fldD8TPKvWqZb7jTn"
F_VALOR_TOTAL = "fldj62HwucOtwYO43"
F_RECEBIDO    = "fldIa5SHRUQUqh6lb"
F_SALDO_PAGAR = "fld3YQZOJfD4nNGIl"

F_B_ID    = "fldyVDJW1goPjHTzd"
F_B_DATA  = "fldC1FcuBy8QBiJxQ"
F_B_ITEM  = "fld1NYniZQTZuZsaU"
F_B_QTD   = "fldhQcrqVkfupJAhR"
F_B_VALOR = "fld74Zi6zyyBcB6Yd"
F_B_OBS   = "fldPIj7S6DcHF723o"


def get_token():
    return st.secrets["AIRTABLE_TOKEN"]


def _fetch_estoque():
    headers = {"Authorization": f"Bearer {get_token()}"}
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ESTOQUE}"
    records, params = [], {"returnFieldsByFieldId": "true"}
    while True:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        records.extend(data.get("records", []))
        if not data.get("offset"):
            break
        params["offset"] = data["offset"]
    return records


@st.cache_data(ttl=120)
def carregar_produtos():
    produtos = []
    for rec in _fetch_estoque():
        f = rec.get("fields", {})
        enviada = f.get(F_QTD_ENVIADA, 0) or 0
        saldo = f.get(F_QTD_SALDO, 0) or 0
        if saldo <= 0:
            saldo = enviada
        if saldo <= 0:
            continue
        preco = f.get(F_PRECO, 0) or 0
        produtos.append({
            "id": rec["id"],
            "descricao": f.get(F_DESC, ""),
            "unidade": f.get(F_UNID, "UN"),
            "saldo": saldo,
            "enviada": enviada,
            "preco": preco,
            "valor_saldo": round(saldo * preco, 2),
            "saldo_pagar": f.get(F_SALDO_PAGAR, 0) or 0,
        })
    return sorted(produtos, key=lambda x: x["descricao"])


@st.cache_data(ttl=120)
def carregar_relatorio():
    itens = []
    for rec in _fetch_estoque():
        f = rec.get("fields", {})
        enviada = f.get(F_QTD_ENVIADA, 0) or 0
        if enviada <= 0:
            continue
        preco = f.get(F_PRECO, 0) or 0
        saldo = f.get(F_QTD_SALDO, 0) or 0
        if saldo <= 0:
            saldo = enviada
        valor_total = f.get(F_VALOR_TOTAL, 0) or round(enviada * preco, 2)
        saldo_pagar = f.get(F_SALDO_PAGAR, 0) or valor_total
        recebido = round(valor_total - saldo_pagar, 2)
        vendida = round(enviada - saldo, 2)
        itens.append({
            "descricao": f.get(F_DESC, ""),
            "unidade": f.get(F_UNID, "UN"),
            "enviada": enviada,
            "vendida": vendida,
            "saldo": saldo,
            "preco": preco,
            "valor_total": valor_total,
            "recebido": recebido,
            "saldo_pagar": saldo_pagar,
        })
    return sorted(itens, key=lambda x: x["descricao"])


def registrar_baixa(item_id, qtd, valor, obs):
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }
    hoje = date.today().isoformat()
    body = {
        "records": [{
            "fields": {
                F_B_ID:   f"B-{hoje}-{item_id[:6]}",
                F_B_DATA: hoje,
                F_B_ITEM: [item_id],
                F_B_QTD:  qtd,
                F_B_VALOR: valor,
                F_B_OBS:  obs or "",
            }
        }]
    }
    r = requests.post(
        f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_BAIXAS}",
        headers=headers, json=body,
    )
    r.raise_for_status()


# ── PDF helpers ────────────────────────────────────────────────────────────────

def _header_pdf(pdf, titulo):
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "FERRAGEM AGÁPÈ — CONSIGNAÇÃO", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, titulo, ln=True, align="C")
    pdf.ln(5)


def gerar_recibo_pdf(prod, qtd, valor, obs, hoje):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    ew = pdf.epw
    _header_pdf(pdf, f"Recibo de Pagamento — {hoje}")

    # Info
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(35, 7, "Data", border=1, fill=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 7, hoje, border=1, ln=True)
    pdf.ln(5)

    # Tabela itens
    cw = [ew - 90, 15, 22, 26, 27]
    hdrs = ["Item", "Un", "Qtd", "Preço un", "Total"]
    alns = ["L", "C", "R", "R", "R"]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(200, 200, 200)
    for i, h in enumerate(hdrs):
        pdf.cell(cw[i], 7, h, border=1, fill=True, align=alns[i])
    pdf.ln()

    total_item = round(qtd * prod["preco"], 2)
    pdf.set_font("Helvetica", "", 9)
    row = [prod["descricao"], prod["unidade"], f"{qtd:.2f}",
           f"R$ {prod['preco']:.2f}", f"R$ {total_item:.2f}"]
    for i, v in enumerate(row):
        pdf.cell(cw[i], 7, v, border=1, align=alns[i])
    pdf.ln()

    # Total recebido
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(sum(cw[:4]), 7, "Valor recebido", border=1, fill=True, align="R")
    pdf.cell(cw[4], 7, f"R$ {valor:.2f}", border=1, fill=True, align="R")
    pdf.ln()

    if obs:
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, f"Observação: {obs}")

    return bytes(pdf.output())


def gerar_relatorio_pdf(itens, hoje):
    pdf = FPDF(orientation="L")
    pdf.add_page()
    pdf.set_margins(10, 10, 10)
    ew = pdf.epw
    _header_pdf(pdf, f"Relatório de Estoque — {hoje}")

    cw = [ew - 174, 12, 16, 16, 16, 22, 30, 30, 32]
    hdrs = ["Item", "Un", "Env", "Vend", "Saldo", "Preço un",
            "Total env", "Recebido", "A Pagar"]
    alns = ["L", "C", "R", "R", "R", "R", "R", "R", "R"]

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(200, 200, 200)
    for i, h in enumerate(hdrs):
        pdf.cell(cw[i], 7, h, border=1, fill=True, align=alns[i])
    pdf.ln()

    tot_total = tot_recebido = tot_saldo_pagar = 0.0
    pdf.set_font("Helvetica", "", 7)
    for p in itens:
        row = [
            p["descricao"][:50],
            p["unidade"],
            f"{p['enviada']:.0f}",
            f"{p['vendida']:.0f}",
            f"{p['saldo']:.0f}",
            f"{p['preco']:.2f}",
            f"{p['valor_total']:.2f}",
            f"{p['recebido']:.2f}",
            f"{p['saldo_pagar']:.2f}",
        ]
        for i, v in enumerate(row):
            pdf.cell(cw[i], 6, v, border=1, align=alns[i])
        pdf.ln()
        tot_total += p["valor_total"]
        tot_recebido += p["recebido"]
        tot_saldo_pagar += p["saldo_pagar"]

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(sum(cw[:5]), 7, f"TOTAL  ({len(itens)} itens)", border=1, fill=True, align="R")
    pdf.cell(cw[5], 7, "", border=1, fill=True)
    pdf.cell(cw[6], 7, f"{tot_total:.2f}", border=1, fill=True, align="R")
    pdf.cell(cw[7], 7, f"{tot_recebido:.2f}", border=1, fill=True, align="R")
    pdf.cell(cw[8], 7, f"{tot_saldo_pagar:.2f}", border=1, fill=True, align="R")
    pdf.ln()

    return bytes(pdf.output())


# ── Estilo ─────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .stSelectbox label, .stNumberInput label, .stTextArea label {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
    }
    .produto-info {
        background: #f0f7ff;
        border-radius: 10px;
        padding: 14px 18px;
        margin: 10px 0 18px 0;
        font-size: 1rem;
    }
    .stButton > button {
        width: 100%;
        height: 3.2rem;
        font-size: 1.2rem !important;
        font-weight: 700 !important;
        background-color: #1a7f37 !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("💰 Ferragem Agápè — Consignação")
st.divider()

aba_pag, aba_rel = st.tabs(["Registrar Pagamento", "Relatório de Estoque"])

# ── Aba: Registrar Pagamento ───────────────────────────────────────────────────

with aba_pag:
    try:
        produtos = carregar_produtos()
    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")
        st.stop()

    if not produtos:
        st.success("✅ Todos os itens já foram pagos!")
        st.stop()

    opcoes = {
        f"{p['descricao']}  —  saldo: {p['saldo']} {p['unidade']}": p
        for p in produtos
    }
    escolha = st.selectbox(
        "🔍 Produto",
        [""] + list(opcoes.keys()),
        format_func=lambda x: x or "Selecione o produto...",
    )

    if escolha:
        prod = opcoes[escolha]

        st.markdown(f"""
        <div class='produto-info'>
            <b>{prod['descricao']}</b><br>
            Saldo em estoque: <b>{prod['saldo']} {prod['unidade']}</b> &nbsp;|&nbsp;
            Preço unitário: <b>R$ {prod['preco']:.2f}</b> &nbsp;|&nbsp;
            Valor do saldo: <b>R$ {prod['valor_saldo']:.2f}</b><br>
            A pagar: <b>R$ {prod['saldo_pagar']:.2f}</b>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            qtd = st.number_input(
                f"Quantidade vendida ({prod['unidade']})",
                min_value=0.0,
                max_value=float(prod["saldo"]),
                step=1.0,
                value=float(prod["saldo"]),
            )
        with col2:
            valor = st.number_input(
                "Valor recebido (R$)",
                min_value=0.0,
                step=0.01,
                value=float(prod["saldo_pagar"]) if prod["saldo_pagar"] > 0 else 0.0,
            )

        obs = st.text_area(
            "Observação (opcional)", height=80,
            placeholder="Ex: parcela 1/2, devolução, etc.",
        )

        st.write("")
        if st.button("✅  REGISTRAR PAGAMENTO"):
            if qtd <= 0 or valor <= 0:
                st.warning("Preencha quantidade e valor antes de registrar.")
            else:
                with st.spinner("Registrando..."):
                    try:
                        registrar_baixa(prod["id"], qtd, valor, obs)
                        st.cache_data.clear()
                        hoje = date.today().strftime("%d/%m/%Y")
                        st.success(
                            f"✅ Registrado! {qtd} {prod['unidade']} · R$ {valor:.2f}"
                        )
                        st.balloons()
                        pdf_bytes = gerar_recibo_pdf(prod, qtd, valor, obs, hoje)
                        st.download_button(
                            label="📄 Baixar Recibo PDF",
                            data=pdf_bytes,
                            file_name=f"recibo_{date.today().isoformat()}_{prod['descricao'][:20].replace(' ','_')}.pdf",
                            mime="application/pdf",
                        )
                    except Exception as e:
                        st.error(f"Erro ao registrar: {e}")
    else:
        st.info("👆 Selecione um produto para começar.")

# ── Aba: Relatório de Estoque ─────────────────────────────────────────────────

with aba_rel:
    st.subheader("📊 Estoque Consignação")
    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()
        st.rerun()

    try:
        itens = carregar_relatorio()
    except Exception as e:
        st.error(f"Erro ao carregar estoque: {e}")
        st.stop()

    tot_total = sum(i["valor_total"] for i in itens)
    tot_recebido = sum(i["recebido"] for i in itens)
    tot_saldo = sum(i["saldo_pagar"] for i in itens)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total consignado", f"R$ {tot_total:,.2f}")
    col2.metric("Recebido", f"R$ {tot_recebido:,.2f}")
    col3.metric("A receber", f"R$ {tot_saldo:,.2f}")

    st.divider()

    hoje = date.today().strftime("%d/%m/%Y")
    pdf_bytes = gerar_relatorio_pdf(itens, hoje)
    st.download_button(
        label="📄 Baixar Relatório PDF",
        data=pdf_bytes,
        file_name=f"estoque_consignacao_{date.today().isoformat()}.pdf",
        mime="application/pdf",
    )

    st.dataframe(
        [
            {
                "Item": i["descricao"],
                "Un": i["unidade"],
                "Env": i["enviada"],
                "Vend": i["vendida"],
                "Saldo": i["saldo"],
                "Preço un": f"R$ {i['preco']:.2f}",
                "Total env": f"R$ {i['valor_total']:.2f}",
                "Recebido": f"R$ {i['recebido']:.2f}",
                "A Pagar": f"R$ {i['saldo_pagar']:.2f}",
            }
            for i in itens
        ],
        use_container_width=True,
        height=500,
    )
