#!/usr/bin/env python3
"""
Tests para transaction_parser.py (Fase 2).

Corre 100% offline contra los fixtures de tests/fixtures/ — no abre
ninguna conexion de red, no requiere credenciales, no ejecuta operaciones.

Uso:
    python -m unittest discover -s research/fomo-monitor/tests -v
o, si hay pytest instalado:
    pytest research/fomo-monitor/tests -v
"""

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROTOTYPE_DIR = Path(__file__).resolve().parent.parent / "prototype"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(PROTOTYPE_DIR))

import transaction_parser as tp  # noqa: E402


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


class TestManifestFixtures(unittest.TestCase):
    """Corre cada fixture del manifest.json y verifica la accion/protocolo
    esperados, tal como se documentan en tests/fixtures/manifest.json."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((FIXTURES_DIR / "manifest.json").read_text())

    def test_all_manifest_entries(self):
        for entry in self.manifest:
            with self.subTest(fixture=entry["file"]):
                tx = load_fixture(entry["file"])
                event = tp.interpret_transaction(tx, entry["wallet"])
                self.assertEqual(
                    event.action,
                    entry["expected_action"],
                    f"{entry['file']}: accion esperada {entry['expected_action']}, "
                    f"obtenida {event.action} (notes={event.notes!r})",
                )
                self.assertEqual(
                    event.protocol,
                    entry["expected_protocol"],
                    f"{entry['file']}: protocolo esperado {entry['expected_protocol']!r}, "
                    f"obtenido {event.protocol!r}",
                )
                # Toda respuesta debe traer una confidence valida en [0,1]
                self.assertGreaterEqual(event.confidence, 0.0)
                self.assertLessEqual(event.confidence, 1.0)
                # Un evento UNKNOWN nunca debe inventar montos/tokens
                if event.action == "UNKNOWN":
                    self.assertIsNone(event.token_in)
                    self.assertIsNone(event.token_out)
                    self.assertIsNone(event.token_in_amount)
                    self.assertIsNone(event.token_out_amount)


class TestJupiterBuyDetails(unittest.TestCase):
    """Verifica los numeros exactos del caso BUY limpio (Jupiter -> Raydium)."""

    def setUp(self):
        self.tx = load_fixture("jupiter_buy_sol_to_token.json")
        self.event = tp.interpret_transaction(
            self.tx, "DemoWalletJupiterBuyerAAAAAAAAAAAAAAAAAAAAA"
        )

    def test_action_and_protocol(self):
        self.assertEqual(self.event.action, "BUY")
        self.assertEqual(self.event.protocol, "Jupiter Aggregator v6")

    def test_tokens(self):
        self.assertEqual(self.event.token_in, tp.WRAPPED_SOL_MINT)
        self.assertEqual(
            self.event.token_out, "DemoMemecoinMintOneHHHHHHHHHHHHHHHHHHHHHHHH"
        )
        self.assertEqual(self.event.token_out_amount, 1_000_000.0)
        # 1.5 SOL de swap + 0.00203928 SOL de rent de la nueva ATA, ver
        # _fixture_notes del propio fixture.
        self.assertAlmostEqual(self.event.token_in_amount, 1.50203928, places=8)

    def test_confidence_is_high_for_recognized_protocol(self):
        self.assertGreaterEqual(self.event.confidence, 0.9)

    def test_usd_value_is_none_without_external_sol_price(self):
        # Sin sol_usd_price no debe inventarse un valor en USD.
        self.assertIsNone(self.event.estimated_usd_value)

    def test_usd_value_uses_provided_sol_price(self):
        event_with_price = tp.interpret_transaction(
            self.tx,
            "DemoWalletJupiterBuyerAAAAAAAAAAAAAAAAAAAAA",
            sol_usd_price=150.0,
        )
        self.assertIsNotNone(event_with_price.estimated_usd_value)
        self.assertAlmostEqual(
            event_with_price.estimated_usd_value, 1.50203928 * 150.0, places=4
        )


class TestRaydiumSellDetails(unittest.TestCase):
    def setUp(self):
        self.tx = load_fixture("raydium_sell_token_to_usdc.json")
        self.event = tp.interpret_transaction(
            self.tx, "DemoWalletRaydiumSellerBBBBBBBBBBBBBBBBBBBB"
        )

    def test_action_and_amounts(self):
        self.assertEqual(self.event.action, "SELL")
        self.assertEqual(self.event.token_in_amount, 500000.0)
        self.assertEqual(self.event.token_out_amount, 75.0)

    def test_usd_value_from_stablecoin_leg(self):
        # USDC se trata como ~1:1 con USD sin necesitar oraculo externo.
        self.assertEqual(self.event.estimated_usd_value, 75.0)

    def test_price_per_token(self):
        self.assertAlmostEqual(self.event.estimated_price, 75.0 / 500000.0, places=10)


class TestOrcaTokenToTokenSwap(unittest.TestCase):
    def setUp(self):
        self.tx = load_fixture("orca_swap_token_to_token.json")
        self.event = tp.interpret_transaction(
            self.tx, "DemoWalletOrcaSwapperCCCCCCCCCCCCCCCCCCCCCC"
        )

    def test_action_is_swap_not_buy_or_sell(self):
        # Ninguna de las dos patas es un quote asset (SOL/USDC/USDT):
        # no hay forma no arbitraria de decidir BUY vs SELL.
        self.assertEqual(self.event.action, "SWAP")

    def test_no_usd_value_without_quote_leg(self):
        self.assertIsNone(self.event.estimated_usd_value)


class TestFailedTransaction(unittest.TestCase):
    def test_failed_tx_is_unknown_with_zero_confidence(self):
        tx = load_fixture("failed_transaction.json")
        event = tp.interpret_transaction(tx, "DemoWalletFailedTxDDDDDDDDDDDDDDDDDDDDDDDDD")
        self.assertEqual(event.action, "UNKNOWN")
        self.assertEqual(event.confidence, 0.0)
        self.assertIn("fallo", event.notes.lower())


class TestSimpleTransferIsNotASwap(unittest.TestCase):
    def test_single_leg_is_unknown(self):
        tx = load_fixture("simple_sol_transfer.json")
        event = tp.interpret_transaction(
            tx, "DemoWalletSimpleTransferEEEEEEEEEEEEEEEEEEE"
        )
        self.assertEqual(event.action, "UNKNOWN")
        self.assertLess(event.confidence, 0.5)
        self.assertIsNone(event.protocol)  # System Program es infraestructura


class TestMultihopAmbiguousIsNotGuessed(unittest.TestCase):
    def test_three_legs_is_unknown_not_a_guess(self):
        tx = load_fixture("multihop_ambiguous.json")
        event = tp.interpret_transaction(tx, "DemoWalletMultihopGGGGGGGGGGGGGGGGGGGGGGGGG")
        self.assertEqual(event.action, "UNKNOWN")
        # El protocolo SI se reporta (se detecto Jupiter) aunque la accion
        # quede en UNKNOWN -- no se inventa CUAL token es "la compra".
        self.assertEqual(event.protocol, "Jupiter Aggregator v6")
        self.assertIsNone(event.token_in)
        self.assertIsNone(event.token_out)


class TestPumpFunBuy(unittest.TestCase):
    def test_bonding_curve_buy_detected(self):
        tx = load_fixture("pumpfun_buy_sol_to_newcoin.json")
        event = tp.interpret_transaction(tx, "DemoWalletPumpFunBuyerFFFFFFFFFFFFFFFFFFFFF")
        self.assertEqual(event.action, "BUY")
        self.assertEqual(event.protocol, "Pump.fun (bonding curve)")
        self.assertEqual(event.token_out_amount, 5_000_000.0)


class TestHelperFunctions(unittest.TestCase):
    """Unit tests de las piezas internas, independientes de los fixtures completos."""

    def test_ui_amount_decimal_uses_raw_amount_and_decimals(self):
        entry = {"uiTokenAmount": {"amount": "1234500", "decimals": 4}}
        self.assertEqual(tp._ui_amount_decimal(entry), Decimal("123.4500"))

    def test_ui_amount_decimal_falls_back_to_ui_amount_string(self):
        entry = {"uiTokenAmount": {"uiAmountString": "42.5"}}
        self.assertEqual(tp._ui_amount_decimal(entry), Decimal("42.5"))

    def test_token_deltas_sums_multiple_accounts_same_mint(self):
        meta = {
            "preTokenBalances": [
                {"accountIndex": 1, "owner": "W", "mint": "M",
                 "uiTokenAmount": {"amount": "100", "decimals": 0}},
                {"accountIndex": 2, "owner": "W", "mint": "M",
                 "uiTokenAmount": {"amount": "50", "decimals": 0}},
            ],
            "postTokenBalances": [
                {"accountIndex": 1, "owner": "W", "mint": "M",
                 "uiTokenAmount": {"amount": "60", "decimals": 0}},
                {"accountIndex": 2, "owner": "W", "mint": "M",
                 "uiTokenAmount": {"amount": "50", "decimals": 0}},
            ],
        }
        deltas = tp._token_deltas_for_owner(meta, "W")
        # 100+50=150 antes, 60+50=110 despues => delta -40, sumando ambas cuentas.
        self.assertEqual(deltas, {"M": Decimal("-40")})

    def test_resolve_account_keys_appends_loaded_addresses(self):
        tx = {
            "transaction": {
                "message": {
                    "accountKeys": [
                        {"pubkey": "Static1"},
                        {"pubkey": "Static2"},
                    ]
                }
            },
            "meta": {
                "loadedAddresses": {
                    "writable": ["Loaded1"],
                    "readonly": ["Loaded2"],
                }
            },
        }
        self.assertEqual(
            tp._resolve_account_keys(tx), ["Static1", "Static2", "Loaded1", "Loaded2"]
        )

    def test_detect_protocol_prefers_aggregator_over_inner_amm(self):
        program_ids = [
            "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium (inner)
            "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter (top-level)
        ]
        self.assertEqual(tp.detect_protocol(program_ids), "Jupiter Aggregator v6")

    def test_detect_protocol_none_when_unrecognized(self):
        self.assertIsNone(tp.detect_protocol(["SomeRandomUnknownProgramId1111111111111111"]))

    def test_usd_value_of_stablecoin_leg(self):
        self.assertEqual(
            tp._usd_value_of_leg(tp.USDC_MINT, Decimal("42"), None), Decimal("42")
        )

    def test_usd_value_of_sol_leg_requires_external_price(self):
        self.assertIsNone(tp._usd_value_of_leg(tp.WRAPPED_SOL_MINT, Decimal("2"), None))
        self.assertEqual(
            tp._usd_value_of_leg(tp.WRAPPED_SOL_MINT, Decimal("2"), 150.0),
            Decimal("300.0"),
        )

    def test_usd_value_of_arbitrary_token_is_none(self):
        self.assertIsNone(tp._usd_value_of_leg("SomeRandomMint1111111111111111111111111111", Decimal("10"), 150.0))


if __name__ == "__main__":
    unittest.main()
