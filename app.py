import streamlit as st
import hashlib, json, time, os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime

# -----------------------
# Simple Blockchain Model
# -----------------------
@dataclass
class Transaction:
    product_id: str
    role: str
    actor_name: str
    location: str
    status: str
    extra_info: str
    timestamp: float

@dataclass
class Block:
    index: int
    timestamp: float
    transactions: List[Dict[str, Any]]
    previous_hash: str
    nonce: int
    hash: str

class SimpleBlockchain:
    def __init__(self, storage_file="chain_store.json"):
        self.chain: List[Block] = []
        self.current_transactions: List[Transaction] = []
        self.storage_file = storage_file
        if os.path.exists(self.storage_file):
            self._load()
        else:
            self._create_genesis()

    def _create_genesis(self):
        genesis_block = self._create_block(previous_hash="1", nonce=0)
        self.chain.append(genesis_block)
        self._persist()

    def _create_block(self, previous_hash, nonce) -> Block:
        index = len(self.chain) + 1
        timestamp = time.time()
        txs = [asdict(t) for t in self.current_transactions]
        block_string = json.dumps({
            "index": index,
            "timestamp": timestamp,
            "transactions": txs,
            "previous_hash": previous_hash,
            "nonce": nonce
        }, sort_keys=True)
        block_hash = hashlib.sha256(block_string.encode()).hexdigest()
        block = Block(index=index, timestamp=timestamp, transactions=txs,
                      previous_hash=previous_hash, nonce=nonce, hash=block_hash)
        self.current_transactions = []
        return block

    def add_transaction(self, tx: Transaction):
        self.current_transactions.append(tx)
        return self.mine_block()

    def mine_block(self):
        previous_hash = self.chain[-1].hash if self.chain else "1"
        nonce = 0
        while True:
            candidate = json.dumps({
                "index": len(self.chain) + 1,
                "timestamp": time.time(),
                "transactions": [asdict(t) for t in self.current_transactions],
                "previous_hash": previous_hash,
                "nonce": nonce
            }, sort_keys=True)
            h = hashlib.sha256(candidate.encode()).hexdigest()
            if h.startswith("00"):
                timestamp = time.time()
                txs = [asdict(t) for t in self.current_transactions]
                block = Block(index=len(self.chain)+1, timestamp=timestamp,
                              transactions=txs, previous_hash=previous_hash,
                              nonce=nonce, hash=h)
                self.chain.append(block)
                self.current_transactions = []
                self._persist()
                return block
            nonce += 1

    def get_product_history(self, product_id: str) -> List[Dict[str, Any]]:
        history = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("product_id") == product_id:
                    entry = dict(tx)
                    entry["_block_index"] = block.index
                    entry["_block_hash"] = block.hash
                    entry["_block_timestamp"] = block.timestamp
                    history.append(entry)
        history.sort(key=lambda e: e["timestamp"])
        return history

    def all_transactions_table(self) -> pd.DataFrame:
        rows = []
        for block in self.chain:
            for tx in block.transactions:
                r = dict(tx)
                r["block_index"] = block.index
                r["block_time"] = datetime.fromtimestamp(block.timestamp).isoformat()
                rows.append(r)
        if not rows:
            return pd.DataFrame(columns=["product_id","role","actor_name","location","status","extra_info","timestamp","block_index","block_time"])
        df = pd.DataFrame(rows)
        df["readable_time"] = df["timestamp"].apply(lambda t: datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"))
        return df

    def raw_chain(self) -> List[Dict[str, Any]]:
        return [asdict(b) for b in self.chain]

    def _persist(self):
        data = {"chain": [asdict(b) for b in self.chain]}
        with open(self.storage_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        with open(self.storage_file, "r") as f:
            data = json.load(f)
        self.chain = []
        for b in data.get("chain", []):
            block = Block(index=b["index"], timestamp=b["timestamp"],
                          transactions=b["transactions"], previous_hash=b["previous_hash"],
                          nonce=b["nonce"], hash=b["hash"])
            self.chain.append(block)

# -----------------------
# Streamlit UI
# -----------------------
st.set_page_config(page_title="Supply Chain Blockchain Tracker", layout="wide")
st.title("🚚 Blockchain Supply Chain Tracker")

BC = SimpleBlockchain(storage_file="chain_store.json")

with st.sidebar:
    st.header("Log a new step")
    roles = ["Farmer", "Wholesaler", "Distributor", "Retailer", "Customer"]
    product_id = st.text_input("Product ID", value="PROD-001")
    role = st.selectbox("Role", roles)
    actor_name = st.text_input("Actor name", value="Anonymous")
    location = st.text_input("Location", value="Unknown")
    status = st.text_input("Status", value="Shipped")
    extra_info = st.text_area("Notes", value="")
    submit = st.button("📥 Submit transaction")

if submit:
    if not product_id.strip():
        st.sidebar.error("Product ID can't be empty.")
    else:
        tx = Transaction(
            product_id=product_id.strip(),
            role=role,
            actor_name=actor_name.strip(),
            location=location.strip(),
            status=status.strip(),
            extra_info=extra_info.strip(),
            timestamp=time.time()
        )
        with st.spinner("Adding transaction and mining block..."):
            block = BC.add_transaction(tx)
        st.sidebar.success(f"Added in block #{block.index} (hash {block.hash[:10]}...)")

col1, col2 = st.columns([2,1])

with col1:
    st.subheader("Search product journey")
    q = st.text_input("Enter Product ID to view journey", value=product_id)
    if st.button("🔎 View journey") or q:
        q = q.strip()
        if not q:
            st.warning("Enter a product ID first.")
        else:
            hist = BC.get_product_history(q)
            if not hist:
                st.info(f"No records found for `{q}`.")
            else:
                df = pd.DataFrame(hist)
                df["timestamp_readable"] = df["timestamp"].apply(lambda t: datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"))
                display_cols = ["timestamp_readable", "product_id", "role", "actor_name", "location", "status", "extra_info", "_block_index"]
                st.dataframe(df[display_cols].rename(columns={
                    "timestamp_readable":"Time",
                    "actor_name":"Actor",
                    "_block_index":"Block #",
                    "extra_info":"Notes"
                }))
                st.json(hist)

with col2:
    st.subheader("Blockchain overview")
    if st.checkbox("Show all transactions"):
        st.dataframe(BC.all_transactions_table())
    if st.checkbox("Show raw blockchain"):
        st.json(BC.raw_chain())

st.markdown("---")
st.caption("Classroom demo — not a production blockchain")
