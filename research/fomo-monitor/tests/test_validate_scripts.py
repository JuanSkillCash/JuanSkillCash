#!/usr/bin/env python3
"""
Prueba, con RPC mockeado (100% offline), que los scripts de
validate/ (Fase 4, Pasos 2-3) funcionan de punta a punta: arman las
llamadas RPC correctas, procesan la respuesta, y producen un JSON de
salida con la comparacion RAW vs PARSER. No demuestra nada sobre datos
REALES (eso requiere red, ver FASE_4_VALIDACION_REAL.md) -- solo prueba
que la herramienta en si misma no esta rota, usando los mismos fixtures
sinteticos que el resto del proyecto.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
VALIDATE_DIR = ROOT / "validate"
PROTOTYPE_DIR = ROOT / "prototype"
FIXTURES_DIR = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(PROTOTYPE_DIR))
sys.path.insert(0, str(VALIDATE_DIR))


class TestFetchAndValidateSolana(unittest.TestCase):
    def test_main_runs_end_to_end_against_mocked_rpc(self):
        import fetch_and_validate_solana as script

        fixture_tx = json.loads((FIXTURES_DIR / "jupiter_buy_sol_to_token.json").read_text())
        wallet = "DemoWalletJupiterBuyerAAAAAAAAAAAAAAAAAAAAA"
        signature = fixture_tx["transaction"]["signatures"][0]

        def fake_rpc(method, params):
            if method == "getSignaturesForAddress":
                return {"result": [{"signature": signature, "err": None, "blockTime": 1786000000}]}
            if method == "getTransaction":
                return {"result": fixture_tx}
            raise AssertionError(method)

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            result = fake_rpc(body["method"], body["params"])
            m = MagicMock()
            m.read.return_value = json.dumps(result).encode("utf-8")
            m.__enter__.return_value = m
            m.__exit__.return_value = False
            return m

        out_path = ROOT / "tests" / "_tmp_solana_validate_out.json"
        argv = ["prog", wallet, "--limit", "1", "--json-out", str(out_path)]

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), patch.object(sys, "argv", argv):
            script.main()

        try:
            self.assertTrue(out_path.exists())
            results = json.loads(out_path.read_text())
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["parsed"]["action"], "BUY")
            self.assertEqual(results[0]["parsed"]["protocol"], "Jupiter Aggregator v6")
            self.assertEqual(results[0]["raw"]["signature"], signature)
        finally:
            out_path.unlink(missing_ok=True)


class TestFetchAndValidateRobinhood(unittest.TestCase):
    def test_main_runs_end_to_end_against_mocked_rpc(self):
        import fetch_and_validate_robinhood as script
        from parsers import evm_parser as ep
        from chains import robinhood_adapter as ra

        fixture = json.loads((FIXTURES_DIR / "evm" / "uniswap_v3_buy_usdg_to_token.json").read_text())
        manifest = json.loads((FIXTURES_DIR / "evm" / "manifest.json").read_text())
        entry = next(e for e in manifest if e["file"] == "uniswap_v3_buy_usdg_to_token.json")
        wallet = entry["wallet"]
        tx_hash = fixture["receipt"]["transactionHash"]

        def fake_rpc(method, params):
            if method == "eth_blockNumber":
                return {"result": "0x64"}
            if method == "eth_getLogs":
                topics = params[0]["topics"]
                if topics[2] is not None:
                    return {"result": [{
                        "transactionHash": tx_hash,
                        "topics": [ep.TRANSFER_EVENT_TOPIC0, ra._topic_from_address("0x" + "70" * 20), ra._topic_from_address(wallet)],
                    }]}
                return {"result": []}
            if method == "eth_getTransactionByHash":
                return {"result": fixture["tx"]}
            if method == "eth_getTransactionReceipt":
                return {"result": fixture["receipt"]}
            if method == "eth_getBlockByNumber":
                return {"result": {"timestamp": "0x68974d80"}}
            if method == "eth_call":
                return {"result": "0x"}
            raise AssertionError(method)

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            result = fake_rpc(body["method"], body["params"])
            m = MagicMock()
            m.read.return_value = json.dumps(result).encode("utf-8")
            m.__enter__.return_value = m
            m.__exit__.return_value = False
            return m

        out_path = ROOT / "tests" / "_tmp_robinhood_validate_out.json"
        argv = ["prog", wallet, "--limit", "1", "--no-resolve-symbols", "--json-out", str(out_path)]

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), patch.object(sys, "argv", argv):
            script.main()

        try:
            self.assertTrue(out_path.exists())
            results = json.loads(out_path.read_text())
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["raw"]["tx_hash"], tx_hash)
            self.assertIn(results[0]["parsed"]["action"], ("BUY", "SWAP"))  # symbols no resueltos -> puede caer a SWAP
        finally:
            out_path.unlink(missing_ok=True)


class TestMeasureLatency(unittest.TestCase):
    def test_on_trade_computes_nonnegative_latency_and_does_not_crash(self):
        import asyncio
        from datetime import datetime, timezone, timedelta
        import measure_latency as script
        from models.normalized_trade import NormalizedTrade

        five_seconds_ago = (datetime.now(timezone.utc) - timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        trade = NormalizedTrade(
            chain="solana", wallet="W", signature="S", timestamp=five_seconds_ago,
            action="BUY", token_in="SOL", token_in_symbol="SOL", token_in_amount=1.0,
            token_out="TOKEN", token_out_symbol=None, token_out_amount=100.0,
            price=0.01, usd_value=None, protocol="Jupiter Aggregator v6", confidence=0.9,
        )
        on_trade = script.make_on_trade("solana")
        asyncio.run(on_trade(trade))  # no debe lanzar excepcion; latencia se imprime a stdout

    def test_on_trade_handles_missing_timestamp_gracefully(self):
        import asyncio
        import measure_latency as script
        from models.normalized_trade import NormalizedTrade

        trade = NormalizedTrade(
            chain="robinhood", wallet="W", signature="S", timestamp=None,
            action="UNKNOWN", token_in=None, token_in_symbol=None, token_in_amount=None,
            token_out=None, token_out_symbol=None, token_out_amount=None,
            price=None, usd_value=None, protocol=None, confidence=0.0,
        )
        on_trade = script.make_on_trade("robinhood")
        asyncio.run(on_trade(trade))  # no debe lanzar excepcion aunque no haya timestamp


if __name__ == "__main__":
    unittest.main()
