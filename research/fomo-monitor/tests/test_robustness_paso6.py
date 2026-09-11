#!/usr/bin/env python3
"""
Tests de robustez explicitos para la Fase 4, Paso 6: el sistema NO debe
confundir una aprobacion/delegacion (SPL Token 'approve' en Solana,
ERC-20 'Approval' en EVM) con una compra o venta. Ambos casos ya estaban
cubiertos implicitamente por los tests parametrizados de manifest.json
(TestManifestFixtures), pero se les da aqui un test dedicado y explicito
porque el encargo de la Fase 4 los pide como caso de robustez propio.

100% offline, sin red, sin credenciales.
"""

import json
import sys
import unittest
from pathlib import Path

PROTOTYPE_DIR = Path(__file__).resolve().parent.parent / "prototype"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(PROTOTYPE_DIR))

import transaction_parser as solana_tp  # noqa: E402
from parsers import evm_parser as ep  # noqa: E402


class TestSolanaApproveIsNotATrade(unittest.TestCase):
    def test_delegate_approval_without_transfer_is_unknown(self):
        tx = json.loads((FIXTURES_DIR / "spl_token_approve_no_transfer.json").read_text())
        event = solana_tp.interpret_transaction(
            tx, "DemoWalletApproverHHHHHHHHHHHHHHHHHHHHHHHHH"
        )
        self.assertEqual(event.action, "UNKNOWN")
        self.assertEqual(event.confidence, 0.0)
        self.assertIsNone(event.token_in)
        self.assertIsNone(event.token_out)
        self.assertIn("Sin cambios de balance", event.notes)


class TestEvmApprovalIsNotATrade(unittest.TestCase):
    def test_erc20_approval_without_transfer_is_unknown(self):
        fixture = json.loads((FIXTURES_DIR / "evm" / "erc20_approve_no_transfer.json").read_text())
        manifest = json.loads((FIXTURES_DIR / "evm" / "manifest.json").read_text())
        entry = next(e for e in manifest if e["file"] == "erc20_approve_no_transfer.json")

        event = ep.interpret_transaction(
            fixture["tx"], fixture["receipt"], entry["wallet"],
            block_timestamp=fixture.get("block_timestamp"),
        )
        self.assertEqual(event.action, "UNKNOWN")
        self.assertEqual(event.confidence, 0.0)
        self.assertIsNone(event.token_in)
        self.assertIsNone(event.token_out)
        self.assertEqual(event.protocol, None)

    def test_approval_topic0_is_never_mistaken_for_transfer(self):
        # Verificacion directa de la pieza de logica que hace esto seguro:
        # _decode_transfer_log debe ignorar cualquier log cuyo topic0 no sea
        # exactamente el de Transfer, Approval incluido.
        log = {
            "address": "0x" + "aa" * 20,
            "topics": [
                ep.APPROVAL_TOPIC0 if hasattr(ep, "APPROVAL_TOPIC0") else
                "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925",
                "0x" + "00" * 12 + "11" * 20,
                "0x" + "00" * 12 + "22" * 20,
            ],
            "data": "0x64",
        }
        self.assertIsNone(ep._decode_transfer_log(log))


if __name__ == "__main__":
    unittest.main()
