import streamlit as st
import requests
from datetime import date, datetime
from fpdf import FPDF


def _s(text):
    return (str(text)
            .replace("—", "-").replace("–", "-")
            .replace("’", "'").replace("‘", "'")
            .encode("latin-1", "replace").decode("latin-1"))


BASE_ID = "applwqIv7LwaRxL5g"
TABLE_ESTOQUE = "tblfC2RBL11zdy4rW"
TABLE_BAIXAS = "tblslIocty9hf5j3k"

F_DESC        = "fldPkkISGo4U3iom6"
F_UNID        = "fld1KRLnffGU4xwYm"
F_QTD_SALDO   = "fldHAS3B7uhLyG5uh"
F_QTD_ENVIADA = "fld8MOkhlQwM1QQdt"
F_PRECO       = "fldD8TPKvWqZb7jTn"
F_VALOR_TOTAL = "fldj62HwucOtwYO43"
F_SALDO_PAGAR = "fld3YQZOJfD4nNGIl"

F_B_ID    = "fldyVDJW1goPjHTzd"
F_B_DATA  = "fldC1FcuBy8QBiJxQ"
F_B_ITEM  = "fld1NYniZQTZuZsaU"
F_B_QTD   = "fldhQcrqVkfupJAhR"
F_B_VALOR = "fld74Zi6zyyBcB6Yd"
F_B_OBS   = "fldPIj7S6DcHF723o"


def get_token():
    return st.secrets["AIRTABLE_TOKEN"]


@st.cache_data(ttl=120)
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


def carregar_produtos():
    produtos = []
    for rec in _fetch_estoque():
        f = rec.get("fields", {})
        enviada = f.get(F_QTD_ENVIADA, 0) or 0
        raw_saldo = f.get(F_QTD_SALDO)
        saldo = raw_saldo if raw_saldo is not None else enviada
        if saldo <= 0:
            continue
        preco = f.get(F_PRECO, 0) or 0
        saldo_pagar = f.get(F_SALDO_PAGAR, 0) or 0
        produtos.append({
            "id": rec["id"],
            "descricao": f.get(F_DESC, ""),
            "unidade": f.get(F_UNID, "UN"),
            "saldo": saldo,
            "enviada": enviada,
            "preco": preco,
            "valor_unit": preco,
            "valor_saldo": round(saldo * preco, 2),
            "saldo_pagar": saldo_pagar,
        })
    return sorted(produtos, key=lambda x: x["descricao"])


def carregar_relatorio():
    itens = []
    for rec in _fetch_estoque():
        f = rec.get("fields", {})
        enviada = f.get(F_QTD_ENVIADA, 0) or 0
        if enviada <= 0:
            continue
        preco = f.get(F_PRECO, 0) or 0
        raw_saldo = f.get(F_QTD_SALDO)
        saldo = max(0, (raw_saldo if raw_saldo is not None else enviada) or 0)
        valor_total = f.get(F_VALOR_TOTAL, 0) or round(enviada * preco, 2)
        raw_sp = f.get(F_SALDO_PAGAR)
        saldo_pagar = max(0, (raw_sp if raw_sp is not None else valor_total) or 0)
        recebido = round(valor_total - saldo_pagar, 2)
        itens.append({
            "descricao": f.get(F_DESC, ""),
            "unidade": f.get(F_UNID, "UN"),
            "enviada": enviada,
            "vendida": round(enviada - saldo, 2),
            "saldo": saldo,
            "preco": preco,
            "valor_total": valor_total,
            "recebido": recebido,
            "saldo_pagar": saldo_pagar,
        })
    return sorted(itens, key=lambda x: x["descricao"])


def registrar_baixas(cart):
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }
    hoje = date.today().isoformat()
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_BAIXAS}"
    for item in cart:
        body = {
            "records": [{
                "fields": {
                    F_B_ID:    f"B-{hoje}-{item['id'][:6]}",
                    F_B_DATA:  hoje,
                    F_B_ITEM:  [item["id"]],
                    F_B_QTD:   item["qtd"],
                    F_B_VALOR: item["valor"],
                    F_B_OBS:   item.get("obs", ""),
                }
            }]
        }
        r = requests.post(url, headers=headers, json=body)
        r.raise_for_status()


# ── PDF ────────────────────────────────────────────────────────────────────────

def gerar_recibo_pdf(cart, hoje, numero):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    ew = pdf.epw

    # Cabeçalho estilo pedido de venda
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, _s("FERRAGEM AGÁPÈ"), ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, _s("Consignação de produtos"), ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, _s(f"Recibo de Pagamento N° {numero}"), ln=True, align="C")
    pdf.ln(5)

    # Info cliente / data
    cw_label = 40
    cw_val = (ew - cw_label * 2 - 4) / 2

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(cw_label, 7, "Cliente", border=1, fill=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(cw_val, 7, "TAIS", border=1)
    pdf.cell(4, 7, "", border=0)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(cw_label, 7, "Data", border=1, fill=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 7, hoje, border=1, ln=True)
    pdf.ln(6)

    # Tabela itens
    cw = [ew - 88, 15, 20, 26, 27]
    hdrs = ["Item", "Un", "Qtd", _s("Preço un"), "Total"]
    alns = ["L", "C", "R", "R", "R"]

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(60, 60, 60)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(hdrs):
        pdf.cell(cw[i], 7, h, border=1, fill=True, align=alns[i])
    pdf.ln()
    pdf.set_text_color(0, 0, 0)

    total_geral = 0.0
    pdf.set_font("Helvetica", "", 9)
    fill = False
    for item in cart:
        pdf.set_fill_color(245, 245, 245) if fill else pdf.set_fill_color(255, 255, 255)
        row = [
            _s(item["descricao"]),
            _s(item["unidade"]),
            f"{item['qtd']:.2f}",
            f"R$ {item['preco']:.2f}",
            f"R$ {item['valor']:.2f}",
        ]
        for i, v in enumerate(row):
            pdf.cell(cw[i], 7, v, border=1, fill=True, align=alns[i])
        pdf.ln()
        total_geral += item["valor"]
        fill = not fill

    # Total
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(sum(cw[:4]), 8, "TOTAL RECEBIDO", border=1, fill=True, align="R")
    pdf.cell(cw[4], 8, f"R$ {total_geral:.2f}", border=1, fill=True, align="R")
    pdf.ln()

    return bytes(pdf.output())


def gerar_relatorio_pdf(itens, hoje):
    pdf = FPDF(orientation="L")
    pdf.add_page()
    pdf.set_margins(10, 10, 10)
    ew = pdf.epw

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, _s("FERRAGEM AGÁPÈ - CONSIGNAÇÃO"), ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, _s(f"Relatorio de Estoque - {hoje}"), ln=True, align="C")
    pdf.ln(5)

    cw = [ew - 174, 12, 16, 16, 16, 22, 30, 30, 32]
    hdrs = ["Item", "Un", "Env", "Vend", "Saldo", _s("Preço un"),
            "Total env", "Recebido", "A Pagar"]
    alns = ["L", "C", "R", "R", "R", "R", "R", "R", "R"]

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(60, 60, 60)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(hdrs):
        pdf.cell(cw[i], 7, h, border=1, fill=True, align=alns[i])
    pdf.ln()
    pdf.set_text_color(0, 0, 0)

    tot_total = tot_recebido = tot_saldo_pagar = 0.0
    pdf.set_font("Helvetica", "", 7)
    fill = False
    for p in itens:
        pdf.set_fill_color(245, 245, 245) if fill else pdf.set_fill_color(255, 255, 255)
        row = [
            _s(p["descricao"])[:50],
            _s(p["unidade"]),
            f"{p['enviada']:.0f}",
            f"{p['vendida']:.0f}",
            f"{p['saldo']:.0f}",
            f"{p['preco']:.2f}",
            f"{p['valor_total']:.2f}",
            f"{p['recebido']:.2f}",
            f"{p['saldo_pagar']:.2f}",
        ]
        for i, v in enumerate(row):
            pdf.cell(cw[i], 6, v, border=1, fill=True, align=alns[i])
        pdf.ln()
        tot_total += p["valor_total"]
        tot_recebido += p["recebido"]
        tot_saldo_pagar += p["saldo_pagar"]
        fill = not fill

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(sum(cw[:5]), 7, _s(f"TOTAL  ({len(itens)} itens)"), border=1, fill=True, align="R")
    pdf.cell(cw[5], 7, "", border=1, fill=True)
    pdf.cell(cw[6], 7, f"{tot_total:.2f}", border=1, fill=True, align="R")
    pdf.cell(cw[7], 7, f"{tot_recebido:.2f}", border=1, fill=True, align="R")
    pdf.cell(cw[8], 7, f"{tot_saldo_pagar:.2f}", border=1, fill=True, align="R")
    pdf.ln()

    return bytes(pdf.output())


# ── Estilo ─────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Ferragem Agápè — Consignação",
    page_icon="💰",
    layout="centered",
)

st.markdown("""
<style>
    .stSelectbox label, .stNumberInput label, .stTextArea label {
        font-size: 1.05rem !important; font-weight: 600 !important;
    }
    .produto-info {
        background: #f0f7ff; border-radius: 10px;
        padding: 12px 16px; margin: 8px 0 14px 0; font-size: 0.95rem;
    }
    .cart-table { font-size: 0.93rem; }
    div[data-testid="stMetricValue"] { font-size: 1.3rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("💰 Ferragem Agápè — Consignação")
st.divider()

# Session state
if "cart" not in st.session_state:
    st.session_state.cart = []
if "registrado" not in st.session_state:
    st.session_state.registrado = False
if "pdf_recibo" not in st.session_state:
    st.session_state.pdf_recibo = None
if "numero_pedido" not in st.session_state:
    st.session_state.numero_pedido = datetime.now().strftime("%Y%m%d%H%M")

aba_pag, aba_rel = st.tabs(["Registrar Pagamento", "Relatório de Estoque"])

# ── Aba: Registrar Pagamento ───────────────────────────────────────────────────

with aba_pag:
    try:
        produtos = carregar_produtos()
    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")
        st.stop()

    ids_no_cart = {i["id"] for i in st.session_state.cart}
    disponiveis = [p for p in produtos if p["id"] not in ids_no_cart]

    # ── Seleção de produto ──

    if disponiveis and not st.session_state.registrado:
        opcoes = {
            f"{p['descricao']}  ({p['saldo']} {p['unidade']} · R$ {p['preco']:.2f}/un)": p
            for p in disponiveis
        }
        escolha = st.selectbox(
            "🔍 Produto",
            [""] + list(opcoes.keys()),
            format_func=lambda x: x or "Selecione o produto...",
            key="produto_sel",
        )

        if escolha:
            prod = opcoes[escolha]
            valor_unit = prod["preco"]
            saldo_pagar = prod["saldo_pagar"]

            st.markdown(f"""
            <div class='produto-info'>
                <b>{prod['descricao']}</b><br>
                Saldo em estoque: <b>{prod['saldo']} {prod['unidade']}</b> &nbsp;·&nbsp;
                Preço unitário: <b>R$ {valor_unit:.2f}</b><br>
                Valor do saldo: <b>R$ {prod['valor_saldo']:.2f}</b> &nbsp;·&nbsp;
                A pagar: <b>R$ {saldo_pagar:.2f}</b>
            </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                qtd = st.number_input(
                    f"Quantidade ({prod['unidade']})",
                    min_value=0.0,
                    max_value=float(prod["saldo"]),
                    step=1.0,
                    value=float(prod["saldo"]),
                )
            with col2:
                valor_auto = round(qtd * valor_unit, 2)
                valor = st.number_input(
                    "Valor (R$)",
                    min_value=0.0,
                    step=0.01,
                    value=float(valor_auto),
                )

            obs = st.text_input(
                "Observação (opcional)",
                placeholder="Ex: parcela 1/2",
                key="obs_input",
            )

            if st.button("➕  Adicionar ao Pedido", use_container_width=True):
                if qtd <= 0 or valor <= 0:
                    st.warning("Preencha quantidade e valor.")
                else:
                    st.session_state.cart.append({
                        "id": prod["id"],
                        "descricao": prod["descricao"],
                        "unidade": prod["unidade"],
                        "qtd": qtd,
                        "preco": valor_unit,
                        "valor": valor,
                        "obs": obs,
                    })
                    st.rerun()

    elif not disponiveis and not st.session_state.cart and not st.session_state.registrado:
        st.success("✅ Todos os itens já foram pagos!")

    # ── Carrinho ──

    if st.session_state.cart and not st.session_state.registrado:
        st.divider()
        st.subheader(f"🛒 Pedido de Pagamento — {len(st.session_state.cart)} item(ns)")

        total_pedido = 0.0
        for idx, item in enumerate(st.session_state.cart):
            cols = st.columns([5, 1, 1, 1, 0.5])
            cols[0].write(f"**{item['descricao']}**")
            cols[1].write(f"{item['qtd']:.0f} {item['unidade']}")
            cols[2].write(f"R$ {item['preco']:.2f}/un")
            cols[3].write(f"**R$ {item['valor']:.2f}**")
            if cols[4].button("✕", key=f"rm_{idx}"):
                st.session_state.cart.pop(idx)
                st.rerun()
            total_pedido += item["valor"]

        st.divider()
        col_t, col_b = st.columns([2, 3])
        col_t.metric("Total do Pedido", f"R$ {total_pedido:.2f}")

        with col_b:
            if st.button("✅  REGISTRAR PAGAMENTO", use_container_width=True):
                with st.spinner("Registrando..."):
                    try:
                        registrar_baixas(st.session_state.cart)
                        st.cache_data.clear()
                        hoje = date.today().strftime("%d/%m/%Y")
                        pdf_bytes = gerar_recibo_pdf(
                            st.session_state.cart, hoje,
                            st.session_state.numero_pedido,
                        )
                        st.session_state.pdf_recibo = pdf_bytes
                        st.session_state.registrado = True
                        st.session_state.show_balloons = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao registrar: {e}")

    # ── Pós-registro ──

    if st.session_state.registrado:
        st.success(f"✅ Pagamento registrado com sucesso!")
        if st.session_state.get("show_balloons"):
            st.balloons()
            st.session_state.show_balloons = False
        st.download_button(
            label="📄 Baixar Recibo PDF",
            data=st.session_state.pdf_recibo,
            file_name=f"recibo_{date.today().isoformat()}.pdf",
            mime="application/pdf",
        )
        if st.button("🆕  Novo Pedido"):
            st.session_state.cart = []
            st.session_state.registrado = False
            st.session_state.pdf_recibo = None
            st.session_state.numero_pedido = datetime.now().strftime("%Y%m%d%H%M")
            st.rerun()

# ── Aba: Relatório de Estoque ─────────────────────────────────────────────────

with aba_rel:
    st.subheader("📊 Estoque Consignação")
    if st.button("🔄 Atualizar dados", key="btn_atualizar"):
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

    c1, c2, c3 = st.columns(3)
    c1.metric("Total consignado", f"R$ {tot_total:,.2f}")
    c2.metric("Recebido", f"R$ {tot_recebido:,.2f}")
    c3.metric("A receber", f"R$ {tot_saldo:,.2f}")

    st.divider()
    hoje_rel = date.today().strftime("%d/%m/%Y")
    try:
        pdf_rel = gerar_relatorio_pdf(itens, hoje_rel)
        st.download_button(
            label="📄 Baixar Relatório PDF",
            data=pdf_rel,
            file_name=f"estoque_consignacao_{date.today().isoformat()}.pdf",
            mime="application/pdf",
        )
    except Exception as e:
        st.warning(f"PDF indisponível: {e}")

    st.dataframe(
        [{
            "Item": i["descricao"],
            "Un": i["unidade"],
            "Env": i["enviada"],
            "Vend": i["vendida"],
            "Saldo": i["saldo"],
            "Preço un": f"R$ {i['preco']:.2f}",
            "Total env": f"R$ {i['valor_total']:.2f}",
            "Recebido": f"R$ {i['recebido']:.2f}",
            "A Pagar": f"R$ {i['saldo_pagar']:.2f}",
        } for i in itens],
        use_container_width=True,
        height=500,
    )
