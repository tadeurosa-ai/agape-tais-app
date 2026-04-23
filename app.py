import streamlit as st
import requests
from datetime import date

st.set_page_config(
    page_title="Registrar Pagamento",
    page_icon="💰",
    layout="centered",
)

BASE_ID = "applwqIv7LwaRxL5g"
TABLE_ESTOQUE = "tblfC2RBL11zdy4rW"
TABLE_BAIXAS = "tblslIocty9hf5j3k"

F_DESC = "fldPkkISGo4U3iom6"
F_UNID = "fld1KRLnffGU4xwYm"
F_QTD_SALDO = "fldHAS3B7uhLyG5uh"
F_QTD_ENVIADA = "fld8MOkhlQwM1QQdt"
F_PRECO = "fldD8TPKvWqZb7jTn"
F_SALDO_PAGAR = "fld3YQZOJfD4nNGIl"

F_B_ID = "fldyVDJW1goPjHTzd"
F_B_DATA = "fldC1FcuBy8QBiJxQ"
F_B_ITEM = "fld1NYniZQTZuZsaU"
F_B_QTD = "fldhQcrqVkfupJAhR"
F_B_VALOR = "fld74Zi6zyyBcB6Yd"
F_B_OBS = "fldPIj7S6DcHF723o"


def get_token():
    return st.secrets["AIRTABLE_TOKEN"]


@st.cache_data(ttl=120)
def carregar_produtos():
    headers = {"Authorization": f"Bearer {get_token()}"}
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ESTOQUE}"
    records, params = [], {}
    while True:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset
    produtos = []
    for rec in records:
        f = rec.get("fields", {})
        enviada = f.get(F_QTD_ENVIADA, 0) or 0
        saldo = f.get(F_QTD_SALDO, 0) or 0
        if saldo <= 0:
            saldo = enviada
        if saldo <= 0:
            continue
        produtos.append({
            "id": rec["id"],
            "descricao": f.get(F_DESC, ""),
            "unidade": f.get(F_UNID, "UN"),
            "saldo": saldo,
            "enviada": f.get(F_QTD_ENVIADA, 0) or 0,
            "preco": f.get(F_PRECO, 0) or 0,
            "saldo_pagar": f.get(F_SALDO_PAGAR, 0) or 0,
        })
    return sorted(produtos, key=lambda x: x["descricao"])


def registrar_baixa(item_id, qtd, valor, obs):
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }
    hoje = date.today().isoformat()
    body = {
        "records": [{
            "fields": {
                F_B_ID: f"B-{hoje}-{item_id[:6]}",
                F_B_DATA: hoje,
                F_B_ITEM: [item_id],
                F_B_QTD: qtd,
                F_B_VALOR: valor,
                F_B_OBS: obs or "",
            }
        }]
    }
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_BAIXAS}"
    r = requests.post(url, headers=headers, json=body)
    r.raise_for_status()


# ── UI ────────────────────────────────────────────────────────────────────────

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

st.title("💰 Registrar Pagamento")
st.caption("Ferragem Agápè — Consignação")
st.divider()

try:
    produtos = carregar_produtos()
except Exception as e:
    st.error(f"Erro ao carregar produtos: {e}")
    st.stop()

# DEBUG TEMPORÁRIO — remover após teste
import requests as _req
_dbg_r = _req.get(
    f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ESTOQUE}",
    headers={"Authorization": f"Bearer {get_token()}"},
    params={"maxRecords": 1},
)
st.warning(f"DEBUG — status {_dbg_r.status_code} | registros brutos: {len(_dbg_r.json().get('records',[]))} | primeiro campo: {list(_dbg_r.json().get('records',[{}])[0].get('fields',{}).items())[:3] if _dbg_r.json().get('records') else 'vazio'}")

if not produtos:
    st.success("✅ Todos os itens já foram pagos!")
    st.stop()

opcoes = {f"{p['descricao']}  —  saldo: {p['saldo']} {p['unidade']}": p for p in produtos}
escolha = st.selectbox("🔍 Produto", [""] + list(opcoes.keys()), format_func=lambda x: x or "Selecione o produto...")

if escolha:
    prod = opcoes[escolha]
    valor_sugerido = round(prod["preco"] * prod["saldo"], 2)

    st.markdown(f"""
    <div class='produto-info'>
        <b>{prod['descricao']}</b><br>
        Saldo em estoque: <b>{prod['saldo']} {prod['unidade']}</b><br>
        Preço unitário: <b>R$ {prod['preco']:.2f}</b><br>
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
            value=0.0,
        )
    with col2:
        valor = st.number_input(
            "Valor recebido (R$)",
            min_value=0.0,
            step=0.01,
            value=0.0,
        )

    obs = st.text_area("Observação (opcional)", height=80, placeholder="Ex: parcela 1/2, devolução, etc.")

    st.write("")
    if st.button("✅  REGISTRAR PAGAMENTO"):
        if qtd <= 0 or valor <= 0:
            st.warning("Preencha quantidade e valor antes de registrar.")
        else:
            with st.spinner("Registrando..."):
                try:
                    registrar_baixa(prod["id"], qtd, valor, obs)
                    st.cache_data.clear()
                    st.success(f"✅ Registrado! {qtd} {prod['unidade']} · R$ {valor:.2f}")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erro ao registrar: {e}")
else:
    st.info("👆 Selecione um produto para começar.")
