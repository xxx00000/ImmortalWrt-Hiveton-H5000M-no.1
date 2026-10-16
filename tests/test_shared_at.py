import asyncio
import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / 'files/usr/lib/at-webserver/shared_at.py'
spec = importlib.util.spec_from_file_location('shared_at', MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FakeDaemon:
    def __init__(self):
        self.owner = None
        self.commands = []
        self.acquisitions = 0
        self.releases = 0
        self.fail = False

    async def call(self, method, params):
        await asyncio.sleep(0)
        if method == 'acquire':
            if self.owner:
                return {'status': 'busy'}
            self.owner = params['owner']
            self.acquisitions += 1
            return {'status': 'success', 'port': params['at_port']}
        if method == 'release':
            assert params['owner'] == self.owner
            self.owner = None
            self.releases += 1
            return {'status': 'success'}
        assert params['owner'] == self.owner
        command = params.get('at_cmd', params.get('raw_at_content'))
        self.commands.append(command)
        if self.fail:
            return {'status': 'timeout', 'partial_response': 'partial'}
        await asyncio.sleep(.005)
        if command.startswith('AT+CMGS='):
            return {'status': 'success', 'response': '\r\n> ', 'end_flag_matched': '>'}
        return {'status': 'success', 'response': '\r\nOK\r\n'}


class ResolveTests(unittest.TestCase):
    def test_port_comes_from_selected_qmodem_and_override_wins(self):
        text = "qmodem.usb1=modem-device\nqmodem.usb1.at_port='/dev/ttyUSB2'\nqmodem.usb1.override_at_port='/dev/ttyUSB3'\n"
        self.assertEqual(m.resolve_modem(text, ''), ('usb1', '/dev/ttyUSB3'))

    def test_missing_or_multiple_modems_fail_without_guess(self):
        for text in ['', "qmodem.a=modem-device\nqmodem.a.at_port='/dev/ttyUSB1'\nqmodem.b=modem-device\nqmodem.b.at_port='/dev/ttyUSB2'"]:
            with self.assertRaises(m.SharedATError):
                m.resolve_modem(text, '')

    def test_selected_missing_device_does_not_fallback(self):
        with self.assertRaises(m.SharedATError):
            m.resolve_modem("qmodem.a=modem-device\nqmodem.a.at_port='/dev/ttyUSB1'", 'b')


class SharedATTests(unittest.IsolatedAsyncioTestCase):
    def connection(self, daemon):
        return m.SharedATConnection(bus=daemon, resolver=lambda: ('usb1', '/dev/ttyUSB2'))

    async def test_notification_setup_uses_shared_lease_without_global_sms_mode_write(self):
        d = FakeDaemon()
        await self.connection(d).configure_notifications()
        self.assertEqual(d.commands, ['AT+CNMI=2,1,0,2,0', 'AT+CLIP=1'])
        self.assertEqual((d.acquisitions, d.releases), (1, 1))

    async def test_notification_transport_failure_marks_disconnected(self):
        d = FakeDaemon(); d.fail = True
        connection = self.connection(d); connection.is_connected = True
        with self.assertRaises(m.SharedATError):
            await connection.configure_notifications()
        self.assertFalse(connection.is_connected)
        self.assertIsNone(d.owner)

    async def test_alias_resolution_preserves_canonical_notification_port(self):
        class Aliased(FakeDaemon):
            async def call(self, method, params):
                result = await super().call(method, params)
                if method == 'acquire':
                    result['port'] = '/dev/ttyUSB2'
                return result
        async def control(command, section):
            return '\r\nOK\r\n'
        connection = m.SharedATConnection(bus=Aliased(), resolver=lambda: ('usb1', '/dev/modem-alias'), control=control)
        await connection.configure_notifications()
        self.assertEqual(connection.port, '/dev/ttyUSB2')
        await connection.send_command('AT^SETAUTODIAL?')
        self.assertEqual(connection.port, '/dev/ttyUSB2')

    async def test_unsupported_notifications_do_not_prevent_other_at_commands(self):
        class Unsupported(FakeDaemon):
            async def call(self, method, params):
                result = await super().call(method, params)
                if method == 'sendat' and params.get('at_cmd') == 'AT+CNMI=2,1,0,2,0':
                    return {'status': 'error', 'response': '\r\nERROR\r\n'}
                return result
        d = Unsupported()
        await self.connection(d).configure_notifications()
        self.assertEqual(d.commands[-1], 'AT+CLIP=1')

    async def test_sms_and_polling_cannot_interleave(self):
        d = FakeDaemon()
        web, qmodem = self.connection(d), self.connection(d)
        # SMSC length=0; TPDU=0102, length=2. Upstream sends literal backslash-r.
        sms = asyncio.create_task(web.send_command('AT+CMGS=2\\r000102'))
        await asyncio.sleep(.001)
        poll = asyncio.create_task(qmodem.send_command('AT+CSQ'))
        await asyncio.gather(sms, poll)
        self.assertEqual(d.commands, ['AT+CMGF=0', 'AT+CMGS=2', '3030303130321a', 'AT+CSQ'])
        self.assertEqual(d.acquisitions, 2)
        self.assertEqual(d.releases, 2)

    async def test_failure_is_not_empty_success_and_releases(self):
        d = FakeDaemon(); d.fail = True
        with self.assertRaises(m.SharedATError):
            await self.connection(d).send_command('AT+CSQ')
        self.assertIsNone(d.owner)

    async def test_invalid_sms_never_sends(self):
        d = FakeDaemon()
        for command in ['AT+CMGS=2', 'AT+CMGS=3\\r000102', 'AT+CMGS=2\\r00ZZ02', 'AT+CSQ\rAT+CFUN=0', 'AT+CSQ;+CFUN=0']:
            with self.assertRaises(m.SharedATError):
                await self.connection(d).send_command(command)
        self.assertEqual(d.commands, [])

    async def test_cancellation_releases_lease(self):
        d = FakeDaemon()
        task = asyncio.create_task(self.connection(d).send_command('AT+CSQ'))
        await asyncio.sleep(.001)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(d.owner)

    async def test_sms_read_sets_pdu_mode_inside_same_lease(self):
        d = FakeDaemon()
        await self.connection(d).send_command('AT+CMGL=4')
        self.assertEqual(d.commands, ['AT+CMGF=0', 'AT+CMGL=4'])
        self.assertEqual(d.acquisitions, 1)

    async def test_busy_deadline_does_not_open_direct_transport(self):
        d = FakeDaemon(); d.owner = 'other'
        with self.assertRaises(m.SharedATError):
            async with m.ATLease(d, '/dev/ttyUSB2', wait_timeout=.01):
                self.fail('must not acquire')
        self.assertEqual(d.commands, [])


class EventTests(unittest.TestCase):
    def test_filters_other_ports_and_responses_but_accepts_known_urc(self):
        f = m.LineEvents('/dev/ttyUSB2')
        event = {'port': '/dev/ttyUSB2', 'restart_epoch': 1, 'sequence': 1, 'raw_line': '+CSQ: 20,99', 'correlation': 'response'}
        self.assertIsNone(f.consume(event))
        event.update(sequence=2, raw_line='+CMTI: "SM",1', correlation='ambiguous')
        self.assertEqual(f.consume(event), '+CMTI: "SM",1')
        self.assertIsNone(f.consume(event))
        event.update(port='/dev/ttyUSB3', sequence=3, correlation='idle')
        self.assertIsNone(f.consume(event))


if __name__ == '__main__':
    unittest.main()
