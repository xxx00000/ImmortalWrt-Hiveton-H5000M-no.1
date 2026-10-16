import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'files/usr/lib/at-webserver'))
from qmodem_control import QModemControl
from shared_at import SharedATError

class Controls(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls=[]
        self.extra=''
        async def run(*argv, **kwargs):
            self.calls.append(argv)
            if argv[:3] == ('uci', '-q', 'show'):
                return "qmodem.usb1=modem-device\nqmodem.usb1.pdp_index='1'\nqmodem.usb1.enable_dial='1'\n" + self.extra
            return ''
        self.control=QModemControl(run=run)

    async def test_read_command_goes_to_shared_at(self):
        self.assertIsNone(await self.control('AT+CGDCONT?', 'usb1'))
        self.assertEqual(self.calls, [])

    async def test_apn_changes_qmodem_then_requests_redial(self):
        self.assertIn('OK', await self.control('AT+CGDCONT=1,"IPV4V6","cmnet"', 'usb1'))
        self.assertIn(('uci','-q','set','qmodem.usb1.apn=cmnet'),self.calls)
        self.assertEqual(self.calls[-1],('/etc/init.d/qmodem_network','redial','usb1'))

    async def test_disable_updates_owner_and_hangs_up(self):
        await self.control('AT^SETAUTODIAL=0', 'usb1')
        self.assertIn(('uci','-q','set','qmodem.usb1.enable_dial=0'),self.calls)
        self.assertEqual(self.calls[-1],('/etc/init.d/qmodem_network','hang','usb1'))

    async def test_auto_dial_query_reflects_qmodem_owner_configuration(self):
        self.extra = "qmodem.usb1.apn='cmnet'\nqmodem.usb1.pdp_type='ipv4v6'\n"
        response = await self.control('AT^SETAUTODIAL?', 'usb1')
        self.assertIn('^SETAUTODIAL:1,2,"IPV4V6","cmnet","","",0', response)
        self.assertFalse(any('set' in call for call in self.calls))

    async def test_global_disable_and_second_sim_profiles_fail_before_mutation(self):
        for extra in ["qmodem.main.enable_dial='0'\n", "qmodem.usb1.apn2='other-sim'\n"]:
            self.extra = extra
            self.calls.clear()
            with self.assertRaises(SharedATError):
                await self.control('AT^SETAUTODIAL=1,2,"IP","cmnet","","",0', 'usb1')
            self.assertFalse(any('set' in call for call in self.calls))

    async def test_unsupported_dial_mode_does_not_claim_success(self):
        with self.assertRaises(SharedATError):
            await self.control('AT^SETAUTODIAL=1,4','usb1')
        self.assertFalse(any('set' in call for call in self.calls))

    async def test_invalid_or_secondary_context_is_not_reported_success(self):
        for command in ['AT+CGDCONT=2,"IP","apn"', 'AT+CGACT=1,2','AT^SETAUTODIAL=1,2,"IP","x;bad"']:
            self.calls.clear()
            with self.assertRaises(SharedATError):
                await self.control(command,'usb1')
            self.assertFalse(any('set' in call for call in self.calls))
