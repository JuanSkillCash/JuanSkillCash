#!/usr/bin/env python3
"""
Tests de integracion (mockeados, 100% offline) para chains/robinhood_adapter.py
y chains/solana_adapter.py: verifican que el "pegamento" entre el adapter
de cada chain y su parser funciona, sin abrir ninguna conexion real de red.

No se ejecuta ninguna operacion ni se usa ninguna credencial.
"""

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROTOTYPE_DIR = Path(__file__).resolve().parent.parent / "prototype"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(PROTOTYPE_DIR))

from chains import robinhood_adapter as ra  # noqa: E402
from parsers import evm_parser as ep  # noqa: E402


class TestRobinhoodAdapterPolling(unittest.TestCase):
    """Simula un ciclo de polling completo contra el fixture de Uniswap V3
    BUY (Fase 3), mockeando unicamente la capa de transporte RPC
    (urllib.request.urlopen) -- toda la logica real de deteccion,
    deduplicacion e interpretacion se ejercita de verdad."""

    def setUp(self):
        fixture_path = FIXTURES_DIR / "evm" / "uniswap_v3_buy_usdg_to_token.json"
        self.fixture = json.loads(fixture_path.read_text())
        manifest = json.loads((FIXTURES_DIR / "evm" / "manifest.json").read_text())
        self.entry = next(e for e in manifest if e["file"] == "uniswap_v3_buy_usdg_to_token.json")
        self.wallet = self.entry["wallet"]
        self.tx_hash = self.fixture["receipt"]["transactionHash"]
        self.token_registry = {k.lower(): v for k, v in self.entry["token_registry"].items()}

    @staticmethod
    def _encode_abi_string(s: str) -> str:
        """Codifica un string dinamico segun ABI estandar (offset+length+data),
        para simular la respuesta real de un eth_call a symbol()."""
        data = s.encode("utf-8")
        padded_len = (len(data) + 31) // 32 * 32
        body = data.ljust(padded_len, b"\x00")
        offset = (32).to_bytes(32, "big")
        length = len(data).to_bytes(32, "big")
        return "0x" + (offset + length + body).hex()

    def _fake_rpc_response(self, method, params):
        if method == "eth_blockNumber":
            return {"jsonrpc": "2.0", "id": 1, "result": "0x64"}
        if method == "eth_getLogs":
            topics = params[0]["topics"]
            # Solo devolvemos logs en la consulta "como receptor" (topics[2] fijo),
            # que es donde el wallet de prueba efectivamente recibe MEME.
            if topics[2] is not None:
                logs = [
                    {
                        "transactionHash": self.tx_hash,
                        "topics": [
                            ep.TRANSFER_EVENT_TOPIC0,
                            ra._topic_from_address("0x" + "70" * 20),  # pool (irrelevante aqui)
                            ra._topic_from_address(self.wallet),
                        ],
                    }
                ]
            else:
                logs = []
            return {"jsonrpc": "2.0", "id": 1, "result": logs}
        if method == "eth_getTransactionByHash":
            return {"jsonrpc": "2.0", "id": 1, "result": self.fixture["tx"]}
        if method == "eth_getTransactionReceipt":
            return {"jsonrpc": "2.0", "id": 1, "result": self.fixture["receipt"]}
        if method == "eth_getBlockByNumber":
            return {"jsonrpc": "2.0", "id": 1, "result": {"timestamp": "0x68974d80"}}
        if method == "eth_call":
            # Simula symbol()/decimals() real via eth_call, para ejercitar
            # make_rpc_token_resolver() de punta a punta (resolve_symbols_live=True).
            to_addr = params[0]["to"].lower()
            data = params[0]["data"]
            token = self.token_registry.get(to_addr)
            if token is None:
                return {"jsonrpc": "2.0", "id": 1, "result": "0x"}
            if data == "0x95d89b41":  # symbol()
                return {"jsonrpc": "2.0", "id": 1, "result": self._encode_abi_string(token["symbol"])}
            if data == "0x313ce567":  # decimals()
                return {"jsonrpc": "2.0", "id": 1, "result": hex(token["decimals"])}
            return {"jsonrpc": "2.0", "id": 1, "result": "0x"}
        raise AssertionError(f"metodo RPC inesperado en el test: {method}")

    def test_watch_detects_and_interprets_new_transaction(self):
        received = []

        async def on_trade(trade):
            received.append(trade)
            raise _StopWatching()

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            result = self._fake_rpc_response(body["method"], body["params"])
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(result).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.__exit__.return_value = False
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(_StopWatching):
                asyncio.run(
                    ra.watch(
                        [self.wallet], on_trade,
                        rpc_http="https://fake-robinhood-rpc.test",
                        poll_interval=0.001,
                        resolve_symbols_live=True,
                        start_from_current_block=False,
                    )
                )

        self.assertEqual(len(received), 1)
        trade = received[0]
        self.assertEqual(trade.chain, "robinhood")
        self.assertEqual(trade.action, "BUY")
        self.assertEqual(trade.token_in_symbol, "USDG")
        self.assertEqual(trade.token_out_symbol, "MEME")
        self.assertAlmostEqual(trade.token_in_amount, 100.0, places=6)
        self.assertAlmostEqual(trade.token_out_amount, 250000.0, places=6)


class _StopWatching(Exception):
    """Usada para cortar el bucle infinito de watch() despues del primer trade detectado."""


class TestSolanaAdapterBridging(unittest.TestCase):
    """Verifica que chains/solana_adapter.py reenvia correctamente los
    NormalizedTrade a on_trade, sin abrir ninguna conexion real (se
    mockea wallet_monitor.run por completo)."""

    def test_watch_bridges_trades_to_callback(self):
        from chains import solana_adapter as sa
        from models.normalized_trade import NormalizedTrade

        received = []

        async def on_trade(trade):
            received.append(trade)

        fake_trade = NormalizedTrade(
            chain="solana", wallet="W", signature="S", timestamp="2026-01-01T00:00:00Z",
            action="BUY", token_in="SOL", token_in_symbol="SOL", token_in_amount=1.0,
            token_out="TOKEN", token_out_symbol=None, token_out_amount=100.0,
            price=0.01, usd_value=None, protocol="Jupiter Aggregator v6", confidence=0.9,
        )

        def fake_interpret_signature(signature, addr, rpc_url, price):
            # Firma sincrona real: solana_adapter la llama via run_in_executor.
            return fake_trade

        async def fake_run(addresses, rpc_url=None, interpret=None, http_rpc_url=None, sol_usd_price=None):
            # Simula exactamente lo que wallet_monitor.run() hace al detectar
            # una firma nueva: llama a wallet_monitor._interpret_and_alert,
            # que solana_adapter.watch() ya parcheo por su _bridge interno.
            import wallet_monitor as wm
            await wm._interpret_and_alert("W", "S", http_rpc_url, sol_usd_price)

        with patch("chains.solana_adapter.wallet_monitor.run", side_effect=fake_run), \
             patch("chains.solana_adapter.solana_parser.interpret_signature", side_effect=fake_interpret_signature):
            asyncio.run(sa.watch(["W"], on_trade))

        self.assertEqual(len(received), 1)
        self.assertIs(received[0], fake_trade)


if __name__ == "__main__":
    unittest.main()
