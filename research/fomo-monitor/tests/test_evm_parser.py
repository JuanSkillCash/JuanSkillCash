#!/usr/bin/env python3
"""
Tests para parsers/evm_parser.py (Fase 3 — arquitectura multichain).

Corre 100% offline contra los fixtures de tests/fixtures/evm/ — no abre
ninguna conexion de red, no requiere credenciales, no ejecuta operaciones.

Uso:
    python -m unittest discover -s research/fomo-monitor/tests -v
"""

import json
import sys
import unittest
from pathlib import Path

PROTOTYPE_DIR = Path(__file__).resolve().parent.parent / "prototype"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "evm"
sys.path.insert(0, str(PROTOTYPE_DIR))

from parsers import evm_parser as ep  # noqa: E402
from models.normalized_trade import NormalizedTrade  # noqa: E402


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def load_manifest() -> dict:
    entries = json.loads((FIXTURES_DIR / "manifest.json").read_text())
    return {entry["file"]: entry for entry in entries}


MANIFEST = load_manifest()


def make_fixture_resolver(token_registry: dict) -> ep.TokenResolver:
    registry = {k.lower(): v for k, v in token_registry.items()}

    def resolver(address: str) -> ep.ResolvedToken:
        entry = registry.get(address.lower())
        if entry is None:
            return ep.ResolvedToken(symbol=None, decimals=None)
        return ep.ResolvedToken(symbol=entry.get("symbol"), decimals=entry.get("decimals"))

    return resolver


def interpret_fixture(filename: str, **kwargs) -> NormalizedTrade:
    entry = MANIFEST[filename]
    fixture = load_fixture(filename)
    resolver = make_fixture_resolver(entry.get("token_registry", {}))
    return ep.interpret_transaction(
        fixture["tx"],
        fixture["receipt"],
        entry["wallet"],
        block_timestamp=fixture.get("block_timestamp"),
        resolver=resolver,
        **kwargs,
    )


class TestManifestFixtures(unittest.TestCase):
    def test_all_manifest_entries(self):
        for filename, entry in MANIFEST.items():
            with self.subTest(fixture=filename):
                event = interpret_fixture(filename)
                self.assertEqual(
                    event.action, entry["expected_action"],
                    f"{filename}: accion esperada {entry['expected_action']}, "
                    f"obtenida {event.action} (notes={event.notes!r})",
                )
                self.assertEqual(
                    event.protocol, entry["expected_protocol"],
                    f"{filename}: protocolo esperado {entry['expected_protocol']!r}, "
                    f"obtenido {event.protocol!r}",
                )
                self.assertEqual(event.chain, "robinhood")
                self.assertGreaterEqual(event.confidence, 0.0)
                self.assertLessEqual(event.confidence, 1.0)
                if event.action == "UNKNOWN":
                    self.assertIsNone(event.token_in)
                    self.assertIsNone(event.token_out)
                    self.assertIsNone(event.token_in_amount)
                    self.assertIsNone(event.token_out_amount)


class TestUniswapV3Buy(unittest.TestCase):
    FILE = "uniswap_v3_buy_usdg_to_token.json"

    def setUp(self):
        self.event = interpret_fixture(self.FILE)

    def test_amounts_and_symbols(self):
        self.assertEqual(self.event.action, "BUY")
        self.assertEqual(self.event.token_in_symbol, "USDG")
        self.assertEqual(self.event.token_out_symbol, "MEME")
        self.assertAlmostEqual(self.event.token_in_amount, 100.0, places=6)
        self.assertAlmostEqual(self.event.token_out_amount, 250000.0, places=6)

    def test_usd_value_from_stablecoin_leg(self):
        self.assertAlmostEqual(self.event.usd_value, 100.0, places=6)

    def test_confidence_high_when_protocol_and_symbols_resolved(self):
        self.assertGreaterEqual(self.event.confidence, 0.85)


class TestUniswapV2Sell(unittest.TestCase):
    FILE = "uniswap_v2_sell_token_to_weth.json"

    def setUp(self):
        self.event = interpret_fixture(self.FILE)

    def test_action_and_amounts(self):
        self.assertEqual(self.event.action, "SELL")
        self.assertAlmostEqual(self.event.token_in_amount, 50.0, places=6)
        self.assertAlmostEqual(self.event.token_out_amount, 2.0, places=6)

    def test_no_usd_value_without_price_oracle(self):
        # WETH no es stablecoin; sin native_usd_price no se inventa el valor.
        self.assertIsNone(self.event.usd_value)

    def test_usd_value_with_provided_eth_price(self):
        event_priced = interpret_fixture(self.FILE, native_usd_price=3000.0)
        self.assertAlmostEqual(event_priced.usd_value, 2.0 * 3000.0, places=4)


class TestNativeEthBuy(unittest.TestCase):
    def test_tx_value_detected_as_native_leg(self):
        event = interpret_fixture("buy_with_native_eth.json")
        self.assertEqual(event.action, "BUY")
        self.assertEqual(event.token_in, ep.NATIVE_ETH_PSEUDO)
        self.assertEqual(event.token_in_symbol, "ETH")
        self.assertAlmostEqual(event.token_in_amount, 0.5, places=6)
        self.assertAlmostEqual(event.token_out_amount, 750000.0, places=6)


class TestFailedTx(unittest.TestCase):
    def test_failed_status_is_unknown_zero_confidence(self):
        event = interpret_fixture("failed_tx.json")
        self.assertEqual(event.action, "UNKNOWN")
        self.assertEqual(event.confidence, 0.0)
        self.assertIn("revirtio", event.notes.lower())


class TestSimpleTransferIsNotASwap(unittest.TestCase):
    def test_single_leg_is_unknown(self):
        event = interpret_fixture("simple_erc20_transfer.json")
        self.assertEqual(event.action, "UNKNOWN")
        self.assertLess(event.confidence, 0.5)
        self.assertIsNone(event.protocol)


class TestMultihopAmbiguous(unittest.TestCase):
    def test_three_legs_is_unknown_not_guessed(self):
        event = interpret_fixture("multihop_ambiguous.json")
        self.assertEqual(event.action, "UNKNOWN")
        self.assertEqual(event.protocol, "Uniswap V3 (o fork compatible)")
        self.assertIsNone(event.token_in)


class TestErc4337Detection(unittest.TestCase):
    def setUp(self):
        self.event = interpret_fixture("erc4337_userop_buy.json")

    def test_action_still_detected_through_entrypoint_wrapper(self):
        self.assertEqual(self.event.action, "BUY")
        self.assertEqual(self.event.token_in_symbol, "USDG")

    def test_entrypoint_mentioned_in_notes(self):
        self.assertIn("EntryPoint", self.event.notes)

    def test_confidence_penalized_for_unresolved_output_symbol(self):
        # El token de salida no esta en el token_registry (a proposito):
        # debe bajar la confianza vs. un BUY limpio con ambos simbolos resueltos.
        self.assertIsNone(self.event.token_out_symbol)
        self.assertLess(self.event.confidence, 0.90)


class TestHelperFunctions(unittest.TestCase):
    ADDR = "0x" + ("1" * 39 + "a")  # 40 hex chars, generado para evitar errores de conteo manual

    def setUp(self):
        self.assertEqual(len(self.ADDR) - 2, 40, "direccion de prueba mal formada")

    def _topic(self, address: str) -> str:
        return "0x" + address[2:].lower().rjust(64, "0")

    def test_topic_to_address(self):
        topic = self._topic(self.ADDR)
        self.assertEqual(len(topic) - 2, 64)
        self.assertEqual(ep._topic_to_address(topic), self.ADDR.lower())

    def test_decode_transfer_log_ignores_non_transfer_events(self):
        log = {
            "address": "0xf0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0",
            "topics": [ep.UNISWAP_V3_SWAP_TOPIC0, self._topic(self.ADDR), self._topic(self.ADDR)],
            "data": "0x00",
        }
        self.assertIsNone(ep._decode_transfer_log(log))

    def test_decode_transfer_log_decodes_standard_transfer(self):
        token = "0x" + "a" * 40
        recipient = "0x" + "f001" * 10
        log = {
            "address": token,
            "topics": [ep.TRANSFER_EVENT_TOPIC0, self._topic(self.ADDR), self._topic(recipient)],
            "data": "0x64",  # 100 en hex
        }
        decoded = ep._decode_transfer_log(log)
        self.assertIsNotNone(decoded)
        decoded_token, from_addr, to_addr, raw_value = decoded
        self.assertEqual(decoded_token, token)
        self.assertEqual(from_addr, self.ADDR.lower())
        self.assertEqual(to_addr, recipient.lower())
        self.assertEqual(raw_value, 100)

    def test_usd_value_of_stablecoin_leg(self):
        from decimal import Decimal
        self.assertEqual(ep._usd_value_of_leg("USDG", Decimal("42"), None), Decimal("42"))

    def test_usd_value_of_eth_requires_external_price(self):
        from decimal import Decimal
        self.assertIsNone(ep._usd_value_of_leg("ETH", Decimal("2"), None))
        self.assertEqual(ep._usd_value_of_leg("ETH", Decimal("2"), 3000.0), Decimal("6000.0"))

    def test_usd_value_of_unresolved_symbol_is_none(self):
        from decimal import Decimal
        self.assertIsNone(ep._usd_value_of_leg(None, Decimal("10"), 3000.0))


if __name__ == "__main__":
    unittest.main()
