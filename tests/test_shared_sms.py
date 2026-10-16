import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'files/usr/lib/at-webserver'))
from shared_sms import text_pdus
from shared_at import parse_command, SharedATError

class SMSPduTests(unittest.TestCase):
    def test_unicode_and_phone_encoded_with_correct_tpdu_length(self):
        size, pdu = text_pdus('+8613800138000', '测试', reference=1)[0]
        self.assertEqual(pdu, '0011000D91683108108300F00008AA046D4B8BD5')
        self.assertTrue(pdu.endswith('6D4B8BD5'))
        self.assertEqual(parse_command(f'AT+CMGS={size}\\r{pdu}')[1], (size, pdu))

    def test_long_message_has_concat_header_for_each_part(self):
        pdus = text_pdus('13800138000', '中' * 71, reference=42)
        self.assertEqual(len(pdus), 2)
        for index, (size, pdu) in enumerate(pdus, 1):
            self.assertTrue(pdu.startswith('0051'))
            self.assertIn(f'0500032A02{index:02X}', pdu)
            parse_command(f'AT+CMGS={size}\\r{pdu}')

    def test_invalid_phone_empty_and_non_ucs2_are_rejected(self):
        for number, content in [('123;AT', 'test'), ('12345', ''), ('12345', '😀')]:
            with self.assertRaises(SharedATError):
                text_pdus(number, content)
