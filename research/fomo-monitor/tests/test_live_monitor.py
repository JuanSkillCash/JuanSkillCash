#!/usr/bin/env python3
"""
Tests para live_monitor.py (prueba live final): parseo de wallets.txt y
grabacion de operaciones detectadas. 100% offline -- no abre conexiones
de red (eso se prueba solo con acceso real a Internet, ver
FASE_4_VALIDACION_REAL.md).
"""

import asyncio
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prototype"))

import live_monitor as lm  # noqa: E402
from models.normalized_trade import NormalizedTrade  # noqa: E402


class TestParseWalletsFile(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = ROOT / "tests" / "_tmp_live_monitor"
        self.tmp_dir.mkdir(exist_ok=True)

    def tearDown(self):
        for f in self.tmp_dir.glob("*.txt"):
            f.unlink()
        self.tmp_dir.rmdir()

    def _write(self, name: str, content: str) -> Path:
        path = self.tmp_dir / name
        path.write_text(content)
        return path

    def test_parses_valid_mixed_chains_case_insensitive(self):
        path = self._write(
            "ok.txt",
            "# comentario\n"
            "\n"
            "SOLANA,7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU\n"
            "solana,BQ72nSv9f3PRyRKCBnHLVrerrv37CYTHm5h3s9VSGQDV\n"
            "Robinhood,0x1234567890ABCDEF1234567890abcdef12345678\n",
        )
        sol, rob = lm.parse_wallets_file(path)
        self.assertEqual(sol, [
            "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "BQ72nSv9f3PRyRKCBnHLVrerrv37CYTHm5h3s9VSGQDV",
        ])
        # Robinhood se normaliza a minusculas.
        self.assertEqual(rob, ["0x1234567890abcdef1234567890abcdef12345678"])

    def test_rejects_unknown_chain(self):
        path = self._write("bad.txt", "ETHEREUM,0x1234567890abcdef1234567890abcdef12345678\n")
        with self.assertRaises(SystemExit):
            lm.parse_wallets_file(path)

    def test_rejects_malformed_solana_address(self):
        path = self._write("bad.txt", "SOLANA,0OIl-not-base58\n")
        with self.assertRaises(SystemExit):
            lm.parse_wallets_file(path)

    def test_rejects_malformed_robinhood_address(self):
        path = self._write("bad.txt", "ROBINHOOD,not-a-hex-address\n")
        with self.assertRaises(SystemExit):
            lm.parse_wallets_file(path)

    def test_rejects_missing_comma(self):
        path = self._write("bad.txt", "SOLANA\n")
        with self.assertRaises(SystemExit):
            lm.parse_wallets_file(path)

    def test_missing_file_exits_cleanly(self):
        with self.assertRaises(SystemExit):
            lm.parse_wallets_file(self.tmp_dir / "does_not_exist.txt")

    def test_only_comments_returns_empty_lists_without_crashing(self):
        path = self._write("comments_only.txt", "# solo comentarios\n\n# otra\n")
        sol, rob = lm.parse_wallets_file(path)
        self.assertEqual(sol, [])
        self.assertEqual(rob, [])


class TestTradeRecorder(unittest.TestCase):
    def setUp(self):
        self.out_path = Path(__file__).resolve().parent / "_tmp_live_monitor_out.jsonl"
        self.out_path.unlink(missing_ok=True)

    def tearDown(self):
        self.out_path.unlink(missing_ok=True)

    def test_records_trade_to_jsonl_with_all_requested_fields(self):
        recorder = lm.TradeRecorder(self.out_path)
        trade = NormalizedTrade(
            chain="solana", wallet="WalletXYZ", signature="Sig123",
            timestamp="2026-09-11T00:00:00Z", action="BUY",
            token_in="So11111111111111111111111111111111111111112", token_in_symbol="SOL",
            token_in_amount=1.5, token_out="TokenABC", token_out_symbol=None,
            token_out_amount=1000.0, price=0.0015, usd_value=None,
            protocol="Jupiter Aggregator v6", confidence=0.95,
        )
        asyncio.run(recorder(trade))

        self.assertEqual(recorder.count, 1)
        lines = self.out_path.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        saved = json.loads(lines[0])
        for field in (
            "chain", "wallet", "action", "token_in", "token_in_amount",
            "token_out", "token_out_amount", "price", "usd_value",
            "protocol", "timestamp", "signature", "confidence",
        ):
            self.assertIn(field, saved)
        self.assertEqual(saved["action"], "BUY")
        self.assertEqual(saved["chain"], "solana")
        self.assertEqual(saved["confidence"], 0.95)

    def test_multiple_trades_append_as_separate_lines(self):
        recorder = lm.TradeRecorder(self.out_path)
        for i in range(3):
            trade = NormalizedTrade(
                chain="robinhood", wallet=f"W{i}", signature=f"S{i}", timestamp=None,
                action="UNKNOWN", token_in=None, token_in_symbol=None, token_in_amount=None,
                token_out=None, token_out_symbol=None, token_out_amount=None,
                price=None, usd_value=None, protocol=None, confidence=0.0,
            )
            asyncio.run(recorder(trade))
        lines = self.out_path.read_text().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(recorder.count, 3)

    def test_creates_parent_directory_if_missing(self):
        nested = Path(__file__).resolve().parent / "_tmp_live_monitor_dir" / "out.jsonl"
        try:
            recorder = lm.TradeRecorder(nested)
            self.assertTrue(nested.parent.exists())
        finally:
            if nested.exists():
                nested.unlink()
            if nested.parent.exists():
                nested.parent.rmdir()


if __name__ == "__main__":
    unittest.main()
