"""
test_auth_api.py — Testes unitários do motor de autenticação sem senha
(Magic OTP de 6 dígitos) do Nexus PlayTV.

Cobre:
  - geração do OTP (formato, aleatoriedade)
  - request_otp: criação de sessão, rate limiting, validação de contato
  - verify_otp: sucesso, código errado, expiração por tentativas (3x),
    expiração por tempo (10 min), sessão inexistente, sessão já usada
  - criação e reaproveitamento de carteira (web_user_wallets)
  - get_wallet: por wallet_id e por session_token

Roda 100% contra um SQLite temporário (sem tocar o banco de produção) e
faz mock dos disparos externos (Evolution API / Resend) — nenhuma chamada
de rede real é feita.

Uso:
    python3 -m unittest test_auth_api.py -v
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auth_api


class AuthApiTestCase(unittest.TestCase):
    def setUp(self):
        # Banco SQLite isolado por teste.
        self.tmp_fd, self.tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_fd)
        os.remove(self.tmp_path)  # sqlite cria o arquivo do zero
        auth_api.DB_PATH = self.tmp_path
        auth_api.ensure_schema()

        # Nunca deixamos um teste disparar rede de verdade.
        self._patch_wa = mock.patch.object(auth_api, "send_whatsapp_otp", return_value=True)
        self._patch_email = mock.patch.object(auth_api, "send_email_otp", return_value=True)
        self.mock_wa = self._patch_wa.start()
        self.mock_email = self._patch_email.start()
        self.addCleanup(self._patch_wa.stop)
        self.addCleanup(self._patch_email.stop)

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.remove(self.tmp_path)

    # -- helpers ------------------------------------------------------
    def _raw_otp_for_session(self, session_token):
        conn = sqlite3.connect(self.tmp_path)
        c = conn.cursor()
        c.execute("SELECT otp_code FROM web_auth_sessions WHERE session_token = ?", (session_token,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def _force_expire(self, session_token):
        conn = sqlite3.connect(self.tmp_path)
        c = conn.cursor()
        c.execute(
            "UPDATE web_auth_sessions SET expires_at = datetime('now', '-1 minute') WHERE session_token = ?",
            (session_token,),
        )
        conn.commit()
        conn.close()

    # -- geração do OTP -------------------------------------------------
    def test_generate_otp_is_six_digits(self):
        for _ in range(50):
            code = auth_api.generate_otp()
            self.assertEqual(len(code), 6)
            self.assertTrue(code.isdigit())

    def test_generate_otp_has_variance(self):
        codes = {auth_api.generate_otp() for _ in range(30)}
        self.assertGreater(len(codes), 1, "OTPs gerados não deveriam ser todos iguais")

    # -- request_otp -----------------------------------------------------
    def test_request_otp_whatsapp_creates_pending_session(self):
        result = auth_api.request_otp("whatsapp", "11987654321", fingerprint="fp1", ip="1.2.3.4")
        self.assertTrue(result["ok"])
        self.assertTrue(result["session_token"].startswith("SESS_"))
        self.mock_wa.assert_called_once()

        conn = sqlite3.connect(self.tmp_path)
        c = conn.cursor()
        c.execute("SELECT status, attempts, contact_type, contact_val FROM web_auth_sessions WHERE session_token = ?",
                   (result["session_token"],))
        row = c.fetchone()
        conn.close()
        self.assertEqual(row, ("pending", 0, "whatsapp", "5511987654321"))

    def test_request_otp_email_dispatches_via_resend_mock(self):
        result = auth_api.request_otp("email", "cliente@example.com", fingerprint="fp2", ip="9.9.9.9")
        self.assertTrue(result["ok"])
        self.mock_email.assert_called_once()
        self.assertEqual(self.mock_email.call_args[0][0], "cliente@example.com")

    def test_request_otp_rejects_invalid_email(self):
        with self.assertRaises(auth_api.AuthError):
            auth_api.request_otp("email", "nao-e-email", fingerprint="fp3", ip="1.1.1.1")

    def test_request_otp_rejects_invalid_contact_type(self):
        with self.assertRaises(auth_api.AuthError):
            auth_api.request_otp("sms", "11987654321", fingerprint="fp4", ip="1.1.1.1")

    def test_request_otp_rate_limits_after_threshold(self):
        for _ in range(auth_api.RATE_LIMIT_MAX_REQUESTS):
            auth_api.request_otp("whatsapp", "11987654321", fingerprint="fp-rate", ip="8.8.8.8")
        with self.assertRaises(auth_api.AuthError) as ctx:
            auth_api.request_otp("whatsapp", "11987654321", fingerprint="fp-rate", ip="8.8.8.8")
        self.assertEqual(ctx.exception.status, 429)

    # -- verify_otp: sucesso ----------------------------------------------
    def test_verify_otp_success_creates_wallet(self):
        req = auth_api.request_otp("whatsapp", "11987654321", fingerprint="fp5", ip="1.2.3.4")
        code = self._raw_otp_for_session(req["session_token"])

        result = auth_api.verify_otp(req["session_token"], code)
        self.assertTrue(result["ok"])
        wallet = result["wallet"]
        self.assertTrue(wallet["wallet_id"].startswith("WLT_"))
        self.assertEqual(wallet["contact_val"], "5511987654321")
        self.assertFalse(wallet["trial_claimed"])
        self.assertTrue(wallet["referral_code"].startswith("NX"))

    def test_verify_otp_reuses_existing_wallet_for_same_contact(self):
        req1 = auth_api.request_otp("whatsapp", "11987654321", fingerprint="fp6", ip="1.2.3.4")
        code1 = self._raw_otp_for_session(req1["session_token"])
        wallet1 = auth_api.verify_otp(req1["session_token"], code1)["wallet"]

        req2 = auth_api.request_otp("whatsapp", "11987654321", fingerprint="fp6-b", ip="1.2.3.4")
        code2 = self._raw_otp_for_session(req2["session_token"])
        wallet2 = auth_api.verify_otp(req2["session_token"], code2)["wallet"]

        self.assertEqual(wallet1["wallet_id"], wallet2["wallet_id"])

    # -- verify_otp: código incorreto / tentativas -------------------------
    def test_verify_otp_wrong_code_increments_attempts(self):
        req = auth_api.request_otp("whatsapp", "11987654321", fingerprint="fp7", ip="1.2.3.4")

        with self.assertRaises(auth_api.AuthError) as ctx:
            auth_api.verify_otp(req["session_token"], "000000")
        self.assertEqual(ctx.exception.status, 400)

        conn = sqlite3.connect(self.tmp_path)
        c = conn.cursor()
        c.execute("SELECT attempts FROM web_auth_sessions WHERE session_token = ?", (req["session_token"],))
        attempts = c.fetchone()[0]
        conn.close()
        self.assertEqual(attempts, 1)

    def test_verify_otp_expires_after_max_attempts(self):
        req = auth_api.request_otp("whatsapp", "11987654321", fingerprint="fp8", ip="1.2.3.4")

        for _ in range(auth_api.MAX_ATTEMPTS):
            with self.assertRaises(auth_api.AuthError):
                auth_api.verify_otp(req["session_token"], "000000")

        # Mesmo com o código certo, a sessão já expirou por excesso de tentativas.
        code = self._raw_otp_for_session(req["session_token"])
        with self.assertRaises(auth_api.AuthError) as ctx:
            auth_api.verify_otp(req["session_token"], code)
        self.assertIn(ctx.exception.status, (410, 429))

        conn = sqlite3.connect(self.tmp_path)
        c = conn.cursor()
        c.execute("SELECT status FROM web_auth_sessions WHERE session_token = ?", (req["session_token"],))
        status = c.fetchone()[0]
        conn.close()
        self.assertEqual(status, "expired")

    # -- verify_otp: expiração por tempo (10 minutos) ----------------------
    def test_verify_otp_expires_after_ttl(self):
        req = auth_api.request_otp("whatsapp", "11987654321", fingerprint="fp9", ip="1.2.3.4")
        code = self._raw_otp_for_session(req["session_token"])
        self._force_expire(req["session_token"])

        with self.assertRaises(auth_api.AuthError) as ctx:
            auth_api.verify_otp(req["session_token"], code)
        self.assertEqual(ctx.exception.status, 410)

    # -- verify_otp: sessão inexistente / reutilizada ----------------------
    def test_verify_otp_unknown_session(self):
        with self.assertRaises(auth_api.AuthError) as ctx:
            auth_api.verify_otp("SESS_nao_existe", "123456")
        self.assertEqual(ctx.exception.status, 404)

    def test_verify_otp_cannot_be_reused_after_success(self):
        req = auth_api.request_otp("whatsapp", "11987654321", fingerprint="fp10", ip="1.2.3.4")
        code = self._raw_otp_for_session(req["session_token"])
        auth_api.verify_otp(req["session_token"], code)

        with self.assertRaises(auth_api.AuthError) as ctx:
            auth_api.verify_otp(req["session_token"], code)
        self.assertEqual(ctx.exception.status, 410)

    def test_verify_otp_missing_params(self):
        with self.assertRaises(auth_api.AuthError):
            auth_api.verify_otp("", "123456")
        with self.assertRaises(auth_api.AuthError):
            auth_api.verify_otp("SESS_x", "")

    # -- get_wallet ----------------------------------------------------
    def test_get_wallet_by_wallet_id(self):
        req = auth_api.request_otp("email", "cliente2@example.com", fingerprint="fp11", ip="1.2.3.4")
        code = self._raw_otp_for_session(req["session_token"])
        wallet = auth_api.verify_otp(req["session_token"], code)["wallet"]

        result = auth_api.get_wallet(wallet_id=wallet["wallet_id"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["wallet"]["wallet_id"], wallet["wallet_id"])
        self.assertEqual(result["wallet"]["contact_val"], "cliente2@example.com")

    def test_get_wallet_by_session_token_after_verification(self):
        req = auth_api.request_otp("email", "cliente3@example.com", fingerprint="fp12", ip="1.2.3.4")
        code = self._raw_otp_for_session(req["session_token"])
        auth_api.verify_otp(req["session_token"], code)

        result = auth_api.get_wallet(session_token=req["session_token"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["wallet"]["contact_val"], "cliente3@example.com")

    def test_get_wallet_rejects_unverified_session(self):
        req = auth_api.request_otp("email", "cliente4@example.com", fingerprint="fp13", ip="1.2.3.4")
        with self.assertRaises(auth_api.AuthError) as ctx:
            auth_api.get_wallet(session_token=req["session_token"])
        self.assertEqual(ctx.exception.status, 403)

    def test_get_wallet_not_found(self):
        with self.assertRaises(auth_api.AuthError) as ctx:
            auth_api.get_wallet(wallet_id="WLT_INEXISTENTE")
        self.assertEqual(ctx.exception.status, 404)

    def test_get_wallet_requires_identifier(self):
        with self.assertRaises(auth_api.AuthError):
            auth_api.get_wallet()


if __name__ == "__main__":
    unittest.main(verbosity=2)
